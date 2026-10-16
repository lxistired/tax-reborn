"""Document-level normalized-store for a narrow, source-proven reference graph.

This companion to ``normalized_store_reference`` keeps the wire-normalization
boundary explicit.  It supports already parsed parent/child headers, E1 table
headers, D7 descriptors and a constrained kind22 value only.  It preserves
unknown bytes and refuses any reference whose exact rewrite/preservation rule
is not present below.  It is not native Load, Resolve, SetLinkedForm, or
FixupFields.
"""
from dataclasses import dataclass, replace
import hashlib
import struct

from field_template_reference import UnsupportedProfile
from interop.derived_form import source_bound_value_document_reference as wire
from interop.derived_form.source_bound_document_reference import _bindings, load_source_bound_document_bytes
from interop.derived_form.value_form_tail_reference import load_value_form_tail
from interop.derived_form.value_hash_wire_reference import hash_for_nodes
from interop.derived_form.string_wire_reference import read as read_stored_string
from interop.derived_form.persistent_uuid_body_reference import has_untyped_objects
from interop.form_core.hash_structure_reference import validate_document_hashes, validate_hash_structure

from normalized_store_reference import (
    NormalizedStoreRejected, _complete_context, _current_map, _full, _rebuild_tail,
)


@dataclass(frozen=True)
class ReferenceNormalizedStoreResult:
    wire: bytes
    original: object
    readback: object
    source_sha256: str
    output_sha256: str
    parent_remaps: tuple
    node_remaps: tuple
    preserved_E1: int
    e1_range_remaps: tuple
    preserved_D7: int
    preserved_kind22: int
    preserved_stored_strings: int
    preserved_calculated_numeric: int
    preserved_array_elements: int
    mode: str = 'document normalized-store; not native Load/Resolve/SetLinkedForm/FixupFields'
    native_Load_executed: bool = False
    native_FixupFields_executed: bool = False
    native_Resolve_executed: bool = False
    native_SetLinkedForm_executed: bool = False
    original_execution_count: int = 0


def _reject(message):
    raise NormalizedStoreRejected(message)


def _header_parent_index_offset(raw):
    """Locate the sole parent U16 index without reserializing unknown header bytes."""
    if type(raw) is not bytes or not raw.startswith(b'\xc4'):
        _reject('complete raw C4 header required for parent patch')
    cursor = 1
    def identifier():
        nonlocal cursor
        if cursor + 2 > len(raw):
            _reject('truncated header ID')
        size = int.from_bytes(raw[cursor:cursor + 2], 'big'); cursor += 2
        if size > 32 or cursor + size > len(raw):
            _reject('invalid header ID boundary')
        value = raw[cursor:cursor + size]; cursor += size
        return value
    identifier()
    if cursor + 13 > len(raw):
        _reject('truncated fixed header words')
    cursor += 12
    if raw[cursor] != 0xcb:
        _reject('missing CB parent marker')
    present = raw[cursor + 1]; cursor += 2
    if present not in (0, 1):
        _reject('noncanonical parent-present byte')
    if not present:
        if cursor != len(raw):
            _reject('unexpected raw bytes after parentless header')
        return None
    identifier()
    if cursor + 6 > len(raw):
        _reject('truncated parent file/copy words')
    cursor += 6
    identifier()
    offset = cursor
    if cursor + 4 != len(raw):
        _reject('unexpected trailing parent header bytes')
    return offset


def _current_by_form(bound, current_fields):
    result = {}
    for path, form in wire.walk_forms(bound.document):
        fsid = bound.document.formsets[path[0]].header.identifier
        key = (fsid, form.header.identifier)
        values = current_fields.get(key)
        if values is None:
            _reject('every document form requires a complete current registry')
        result[path] = _current_map(values)
    return result


def _source_d2(form, current):
    if form.derived_tail is None:
        _reject('complete ValueForm D2 tail required')
    if has_untyped_objects(form.derived_tail) or any(form.derived_tail.groups[1:]):
        _reject('unknown or record/value tail attachments remain outside this mode')
    source = {}
    for entry in form.derived_tail.field_map.entries:
        full = _full(entry.identifier); ordinal = entry.source_field_index
        if type(ordinal) is not int or not 1 <= ordinal < 65535 or ordinal in source or full in source.values():
            _reject('D2 must be a one-to-one nonzero source ordinal inventory')
        if full not in current:
            _reject('D2 field is absent from its complete current registry')
        source[ordinal] = full
    if not source:
        _reject('empty D2 cannot identify document hash keys')
    return source


def _kind22_is_link_proven(full, node, validated_link_fields, form):
    """D7 uses full IDs; kind22 low16 is only checked against proven owner word7c.

    The upper 48 raw bits remain opaque and are retained byte-for-byte.  This
    is a preservation rule, not a permission to Resolve or SetLinkedValue.
    """
    if node.element_index != 0 or (node.raw & 0xffff) != form.header.word7c:
        return False
    return full in validated_link_fields


def _normalize_form(form, current, validated_link_fields, bindings):
    """Rekey only source-bound nodes whose stored payload is independently retained.

    This is persistence, not a native lifecycle.  In particular a calculated
    numeric node stays byte-identical here; no value is recomputed, cleared, or
    presented as an original Load/Fixup result.  The binding list comes from
    the complete source-bound loader and is used to prove declared arrays.
    """
    source = _source_d2(form, current)
    validate_hash_structure(form.hash_state)
    if any(len(block.nodes) != block.capacity for block in form.hash_state.buffers):
        _reject('hash spare allocation bytes cannot be reconstructed')
    if type(bindings) is not tuple:
        _reject('complete source-bound node bindings required')
    binding_by_key = {(value.source_field_index, value.element_index): value for value in bindings}
    if len(binding_by_key) != len(bindings):
        _reject('ambiguous source-bound node bindings')
    nodes, changes, kind22, strings, calculated, array_values = [], [], 0, 0, 0, 0
    for block in form.hash_state.buffers:
        for node in block.nodes:
            full = source.get(node.field_index)
            binding = binding_by_key.get((node.field_index, node.element_index))
            if full is None or binding is None or binding.field_id != full:
                _reject('hash node has no complete D2/source-bound identity')
            target = current[full]
            if binding.current_field_index != target.ordinal:
                _reject('source-bound current ordinal does not match complete registry')
            if node.header:
                _reject('headered/error-bearing node needs native lifecycle semantics')
            if node.specific_attributes & ~0x0003:
                _reject('override or unproved specific-attribute bits need native lifecycle semantics')
            if (node.kind_byte, node.flag10) != (target.kind, target.format):
                _reject('kind/format conversion is outside document normalized-store')
            if node.kind_byte in (10, 12, 13):
                if node.element_index != 0:
                    _reject('array-element normalization is not proved for this value kind')
            elif node.kind_byte == 11:
                # A ValueTable persists record scalars as ordinary FormValue
                # hash entries keyed by (field ordinal, element ordinal).  This
                # mode retains one already-present ordinary Used numeric value;
                # it never allocates a record, changes row presence, or applies
                # an original Store/Load lifecycle.  The source-bound binding
                # must establish both the compiled-array membership and its
                # finite element limit.  Attribute bit2 remains outside the
                # proved persistence policy, whether scalar or array-backed.
                if node.specific_attributes & 2:
                    _reject('calculated kind11 persistence needs Store/Load evidence')
                if node.specific_attributes != 1:
                    _reject('only ordinary Used kind11 storage is proved')
                if node.element_index:
                    if (binding.native_action != 'requires_additional_scalar_codec' or
                            not binding.array_index or binding.element_limit is None or
                            node.element_index > binding.element_limit):
                        _reject('array element lacks complete declared array identity')
                    array_values += 1
            elif node.kind_byte == 7:
                if node.element_index or node.specific_attributes != 1:
                    _reject('only ordinary Used scalar kind7 storage is proved')
                if node.raw >> 32 or (node.raw & 0xffff) != form.table_id:
                    _reject('kind7 raw table/handle packing is not a local stored-string reference')
                try:
                    read_stored_string(form.string_table, (node.raw >> 16) & 0xffff)
                except Exception as error:
                    raise NormalizedStoreRejected('kind7 string handle is not a valid stored string') from error
                strings += 1
            elif node.kind_byte == 22:
                if not _kind22_is_link_proven(full, node, validated_link_fields, form):
                    _reject('kind22 needs a same-form D7 full-ID owner proof')
                kind22 += 1
            else:
                _reject('string, box, and unproved node kinds remain refused')
            nodes.append(replace(node, next_index=0xffffffff, field_index=target.ordinal))
            changes.append((full, node.field_index, target.ordinal, node.kind_byte, node.element_index))
    if len({(node.field_index, node.element_index) for node in nodes}) != len(nodes):
        _reject('current key collision would merge distinct source cells')
    rebuilt = hash_for_nodes(tuple(nodes), bucket_count=len(form.hash_state.heads))
    if tuple(block.capacity for block in rebuilt.buffers) != tuple(block.capacity for block in form.hash_state.buffers):
        _reject('physical hash buffer layout changed')
    entries = tuple((entry.identifier, current[_full(entry.identifier)].ordinal)
                    for entry in form.derived_tail.field_map.entries)
    tail = _rebuild_tail(form.derived_tail, entries)
    if len(tail.source_wire) != len(form.derived_tail.source_wire):
        _reject('D2 rewrite changed derived-tail length')
    return replace(form, hash_state=rebuilt, derived_tail=tail), tuple(changes), kind22, strings, calculated, array_values


def _patch_parent(form, current_by_path, form_by_copy):
    header = form.header
    if header.parent is None:
        if header.parent_field_index or header.parent_field_id:
            _reject('parentless header has a parent field reference')
        return form, None
    parent_path = form_by_copy.get(header.parent.file_copy)
    if parent_path is None:
        _reject('child parent is not an earlier same-FormSet document form')
    parent_current = current_by_path[parent_path]
    full = _full(header.parent_field_id)
    if not header.parent_field_index or full not in parent_current:
        _reject('child parent field must have a full-ID current mapping')
    target = parent_current[full].ordinal
    raw = form.metadata.get('source_header_wire')
    offset = _header_parent_index_offset(raw)
    if offset is None or int.from_bytes(raw[offset:offset + 2], 'big') != header.parent_field_index:
        _reject('raw/typed parent field index mismatch')
    patched = raw[:offset] + target.to_bytes(2, 'big') + raw[offset + 2:]
    updated_header = replace(header, parent_field_index=target)
    updated = replace(form, header=updated_header,
                      metadata={**form.metadata, 'source_header': updated_header, 'source_header_wire': patched})
    return updated, (header.parent.file_copy, full, header.parent_field_index, target)


def _migrate_e1_ranges(form, current):
    """Translate the proved inclusive E1 table-field interval through D2.

    The two E1 U16s are not opaque: the source-bound ValueTable lifecycle
    reads ``+0x28`` as the first field ordinal and ``+0x2a`` as its inclusive
    last ordinal.  An E1 record contains no full field IDs, so this mode only
    admits a range for which every source ordinal is present in the owning
    form's complete D2, and whose current ordinals remain one increasing,
    gap-free interval.  Anything else needs table-specific lifecycle work.
    """
    if not form.tables:
        return form, ()
    source = _source_d2(form, current)
    migrated, remaps = [], []
    for table_index, table in enumerate(form.tables):
        first, last = table.word28, table.word2a
        if type(first) is not int or type(last) is not int or not 1 <= first <= last < 65535:
            _reject('E1 table field interval must be a nonzero ordered U16 range')
        source_ordinals = tuple(range(first, last + 1))
        if any(ordinal not in source for ordinal in source_ordinals):
            _reject('E1 field interval has no complete owning D2 identity')
        targets = tuple(current[source[ordinal]].ordinal for ordinal in source_ordinals)
        if targets != tuple(range(targets[0], targets[0] + len(targets))):
            _reject('E1 field interval does not remain a contiguous increasing current range')
        raw = table.metadata.get('source_wire')
        if type(raw) is not bytes:
            _reject('complete E1 source bytes required for range migration')
        cursor = 3 + len(table.identifier)
        source_stored = wire._table_store(table, entity_schema=18, table_kind='value_table')
        if source_stored != raw or len(raw) != cursor + 6:
            _reject('E1 source typed header/raw bytes mismatch')
        rewritten = raw[:cursor] + struct.pack('>HH', targets[0], targets[-1]) + raw[cursor + 4:]
        updated = replace(table, word28=targets[0], word2a=targets[-1])
        stored = wire._table_store(updated, entity_schema=18, table_kind='value_table')
        if stored != rewritten:
            _reject('E1 migration would change bytes outside the proved U16 interval')
        migrated.append(updated)
        remaps.append((table_index, table.identifier, first, last, targets[0], targets[-1],
                       tuple((ordinal, source[ordinal]) for ordinal in source_ordinals)))
    return replace(form, tables=tuple(migrated)), tuple(remaps)


def _validate_link_target(link, registry, target_current_by_copy):
    """Require D7's target identity and full field to resolve before storage.

    Raw descriptor round-trip alone says nothing about the target selected by
    the copy number.  This is a narrow own validation rule, not a native link
    resolution call; it simply permits byte preservation after all four wire
    identity components have a same-document, same-registry target.
    """
    parent = registry.get(link.file_copy)
    if parent is None or parent.identifier != link.form_id:
        _reject('D7 target form_id/file_copy has no same-document target')
    current = target_current_by_copy.get(link.file_copy)
    full = _full(link.field_id)
    if current is None or full not in current:
        _reject('D7 target full field ID is absent from its target registry')
    if link.element_index != 0:
        _reject('D7 array-element target remains outside this mode')
    return full


def _check_tables_and_links(form, fsid, registry, target_current_by_copy, context):
    e1 = 0
    for table in form.tables:
        raw = table.metadata.get('source_wire')
        stored = wire._table_store(table, entity_schema=18,
                                   table_kind=wire._factory(context, fsid, form.header.identifier)[1])
        cursor = 3 + len(table.identifier)
        if (type(raw) is not bytes or len(raw) != len(stored) or
                raw[:cursor] != stored[:cursor] or raw[cursor + 4:] != stored[cursor + 4:]):
            _reject('E1 migration must preserve every byte outside its proved U16 interval')
        e1 += 1
    d7 = 0
    validated = set()
    for link in form.links:
        validated.add(_validate_link_target(link, registry, target_current_by_copy))
        raw = link.metadata.get('source_wire')
        stored = wire._link_store(link, fsid, registry, context)
        if type(raw) is not bytes or stored != raw:
            _reject('D7 descriptor must retain exact full-ID source bytes')
        d7 += 1
    return e1, d7, frozenset(validated)


def _resolved_link_context(checked_context, current_fields):
    """Restore unpadded registered IDs for the frozen writer's resolver.

    `_complete_context` validates mappings with 32-byte identity keys, while
    the frozen D7 resolver compares a descriptor's on-wire short ID directly.
    These two representations are equivalent only after this explicit
    conversion.  The map is still complete and is separately cross-checked by
    `_complete_context` before this point.
    """
    field_ids = dict(checked_context.field_ids)
    for key, fields in current_fields.items():
        field_ids[key] = {field.ordinal: field.identifier.rstrip(b' ') for field in fields}
    return replace(checked_context, field_ids=field_ids, preserve_unresolved_links=False)


def _serialize(doc, buffers, context):
    if doc.persistent_objects is not None:
        _reject('entity persistent objects remain outside this mode')
    registries, used_ids = {}, set()
    for fs in doc.formsets:
        wire._formset(fs.header, context)
        if fs.persistent_attributes is not None:
            _reject('FormSet persistent attributes remain outside this mode')
        registry = {}
        def prepare(forms):
            for form in forms:
                h = form.header
                if h.file_copy in registry or form.table_id in used_ids:
                    _reject('duplicate file copy or StringTable ID')
                if h.parent is not None:
                    parent = registry.get(h.parent.file_copy)
                    if parent is None or parent.identifier != h.parent.identifier:
                        _reject('parent must precede child in the same FormSet')
                if context.current_table_ids.get((fs.header.identifier, h.file_copy), form.table_id) != form.table_id:
                    _reject('StringTable remap is outside this mode')
                registry[h.file_copy] = wire.Parent(h.identifier, h.file_copy, h.word7c)
                used_ids.add(form.table_id)
                prepare(form.children)
        prepare(fs.forms); registries[fs.header.identifier] = registry
    entity = wire.store_entity_header(doc.header); base = len(entity)
    fs_base = base + 5 + 4 * (len(doc.formsets) + 1); parts = []
    def store_form(form, form_base, fsid):
        raw_header = form.metadata.get('source_header_wire')
        if type(raw_header) is not bytes:
            _reject('source header bytes required')
        wire._validate_header_wire(raw_header, form.header, tuple(registries[fsid].values()))
        hashed = wire.store_hash(form.hash_state, buffers, version=18); wire._error(hashed.code, 'normalized Hash')
        strings = wire.store_selected_section(form.string_table, buffers, table_id=form.table_id,
                                              requested_share=0, actual_share=0)
        pos = form_base + len(raw_header) + 2
        mapping = wire.store_map(wire.new_map(0xc9, 4), pos).mapping; value_start = pos + 21
        for at in (value_start, value_start + len(hashed.wire), value_start + len(hashed.wire),
                   value_start + len(hashed.wire) + len(strings.string_section)):
            mapping = wire.append_position(mapping, at).mapping
        data = bytearray(raw_header + strings.table_id_wire + wire.store_map(mapping, pos).wire +
                         hashed.wire + strings.string_section)
        table_kind = wire._factory(context, fsid, form.header.identifier)[1]
        table_bytes = tuple(wire._table_store(table, entity_schema=doc.header.schema, table_kind=table_kind)
                            for table in form.tables)
        data.extend(wire._write_index(0xe0, form_base + len(data), table_bytes))
        child_base = form_base + len(data); child_cursor = child_base + 5 + 4 * (len(form.children) + 1)
        children = []
        for child in form.children:
            value = store_form(child, child_cursor, fsid); children.append(value); child_cursor += len(value)
        data.extend(wire._write_index(0xc8, child_base, tuple(children)))
        links = tuple(wire._link_store(link, fsid, registries[fsid], context) for link in form.links)
        data.extend(wire._write_index(0xd7, form_base + len(data), links))
        data.extend(form.derived_tail.source_wire)
        return bytes(data)
    for fs in doc.formsets:
        fs_header = wire.store_formset_header(fs.header); form_base = fs_base + len(fs_header) + 5 + 4 * (len(fs.forms) + 1)
        forms = []
        for form in fs.forms:
            value = store_form(form, form_base, fs.header.identifier); forms.append(value); form_base += len(value)
        part = fs_header + wire._write_index(0xc8, fs_base + len(fs_header), tuple(forms))
        parts.append(part); fs_base += len(part)
    return entity + wire._write_index(0xc7, base, tuple(parts))


def normalize_document_store_bytes(wire_bytes, buffers, *, template_context, current_fields, arrays):
    """Normalize a proven parent/E1/D7/kind22 document graph and fully reload it."""
    if type(wire_bytes) is not bytes or type(current_fields) is not dict or type(arrays) is not dict:
        _reject('immutable source bytes and complete registry maps required')
    original = load_source_bound_document_bytes(wire_bytes, buffers, template_context=template_context,
                                                current_fields=current_fields, arrays=arrays)
    validate_document_hashes(original.document)
    context = _resolved_link_context(_complete_context(original.context, current_fields), current_fields)
    current_by_path = _current_by_form(original, current_fields)
    doc, parent_remaps, node_remaps, e1_remaps, e1, d7, kind22, strings, calculated, array_values = original.document, [], [], [], 0, 0, 0, 0, 0, 0
    for formset_index, fs in enumerate(original.document.formsets):
        form_by_copy = {}
        target_current_by_copy = {}
        registry = {}
        paths = tuple((path, form) for path, form in wire.walk_forms(original.document) if path[0] == formset_index)
        for path, form in paths:
            copy = form.header.file_copy
            if copy in registry:
                _reject('duplicate file copy prevents D7 target identity validation')
            registry[copy] = wire.Parent(form.header.identifier, copy, form.header.word7c)
            target_current_by_copy[copy] = current_by_path[path]
        validated_links = {}
        for path, form in paths:
            validated_links[path] = frozenset(_validate_link_target(link, registry, target_current_by_copy)
                                              for link in form.links)
        for path, form in wire.walk_forms(original.document):
            if path[0] != formset_index:
                continue
            e1_migrated, e1_rows = _migrate_e1_ranges(form, current_by_path[path])
            patched, parent = _patch_parent(e1_migrated, current_by_path, form_by_copy)
            normalized, nodes, count22, count_strings, count_calculated, count_arrays = _normalize_form(patched, current_by_path[path], validated_links[path], original.bindings.get(path))
            doc = wire.replace_form(doc, path, normalized)
            if parent is not None: parent_remaps.append((path,) + parent)
            node_remaps.extend((path,) + row for row in nodes); kind22 += count22; strings += count_strings; calculated += count_calculated; array_values += count_arrays
            e1_remaps.extend((path,) + row for row in e1_rows)
            form_by_copy[normalized.header.file_copy] = path
        for path, form in wire.walk_forms(doc):
            if path[0] == formset_index:
                tables, links, checked = _check_tables_and_links(form, fs.header.identifier, registry,
                                                                 target_current_by_copy, context)
                if checked != validated_links[path]:
                    _reject('D7 target identity changed during normalized serialization')
                e1 += tables; d7 += links
    normalized = replace(original, document=doc, context=context, bindings=_bindings(doc, current_fields, arrays))
    output = _serialize(normalized.document, buffers, context)
    readback = load_source_bound_document_bytes(output, buffers, template_context=context,
                                                current_fields=current_fields, arrays=arrays)
    validate_document_hashes(readback.document)
    if len(tuple(wire.walk_forms(readback.document))) != len(tuple(wire.walk_forms(original.document))):
        _reject('full document form count changed during serialization')
    original_forms, output_forms = dict(wire.walk_forms(original.document)), dict(wire.walk_forms(readback.document))
    for path, before in original_forms.items():
        after = output_forms[path]
        if before.string_table != after.string_table:
            _reject('stored-string table changed during normalized serialization')
        source = _source_d2(before, current_by_path[path])
        after_nodes = {(node.field_index, node.element_index): node
                       for block in after.hash_state.buffers for node in block.nodes}
        for block in before.hash_state.buffers:
            for node in block.nodes:
                if node.kind_byte not in (7, 11) and not node.element_index:
                    continue
                full = source[node.field_index]; target = current_by_path[path][full].ordinal
                landed = after_nodes.get((target, node.element_index))
                if landed is None or (landed.kind_byte, landed.raw, landed.element_index, landed.exponent_byte,
                                      landed.specific_attributes, landed.header, landed.flag10, landed.flag11) != (
                                      node.kind_byte, node.raw, node.element_index, node.exponent_byte,
                                      node.specific_attributes, node.header, node.flag10, node.flag11):
                    _reject('stored string/numeric payload changed during normalized serialization')
    return ReferenceNormalizedStoreResult(output, original, readback, hashlib.sha256(wire_bytes).hexdigest(),
                                          hashlib.sha256(output).hexdigest(), tuple(parent_remaps), tuple(node_remaps),
                                          e1, tuple(e1_remaps), d7, kind22, strings, calculated, array_values)
