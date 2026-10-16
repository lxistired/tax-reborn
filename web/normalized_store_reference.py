"""Fail-closed whole-document wire normalization for an owned finite profile.

This is deliberately an independent ``normalized-store`` mode.  It is not a
claim that native Load or FixupFields ran: it does not synthesize CC/error,
calculation-retention, ChangeData, validation, or persistent-object effects.

The accepted domain is intentionally small.  Each ValueForm must have a full
D2 identity inventory, an explicit complete current registry view, and only
ordinary scalar nodes.  Headers, table IDs, tables, children, links, kind22/D7
references, and persistent object attachments are retained only when absent;
otherwise the input is rejected before output bytes are produced.
"""
from dataclasses import dataclass, replace
import hashlib

from field_template_reference import UnsupportedProfile
from interop.derived_form import source_bound_value_document_reference as wire
from interop.derived_form.source_bound_document_reference import (
    BoundDocument, _bindings, load_source_bound_document_bytes,
)
from interop.derived_form.value_form_tail_reference import load_value_form_tail
from interop.derived_form.value_hash_wire_reference import hash_for_nodes
from interop.form_core.hash_structure_reference import validate_document_hashes, validate_hash_structure


class NormalizedStoreRejected(UnsupportedProfile):
    """The source contains a reference whose normalized wire role is unproved."""


@dataclass(frozen=True)
class NormalizedStoreResult:
    wire: bytes
    original: BoundDocument
    readback: BoundDocument
    source_sha256: str
    output_sha256: str
    remapped_nodes: tuple
    d2_entries: tuple
    mode: str = 'explicit normalized-store; not native FixupFields or Load'
    native_Load_executed: bool = False
    native_FixupFields_executed: bool = False
    native_StoreFieldTable_executed: bool = False
    original_execution_count: int = 0
    original_taxpayer_fixture_count: int = 0


def _reject(message):
    raise NormalizedStoreRejected(message)


def _full(value):
    if type(value) is not bytes or not 1 <= len(value) <= 32:
        _reject('complete nonempty field ID is required')
    return value.ljust(32, b' ')


def _current_map(values):
    if type(values) is not tuple:
        _reject('complete immutable current field tuple is required')
    by_id = {}
    ordinals = set()
    for field in values:
        full = _full(field.identifier)
        if type(field.ordinal) is not int or not 1 <= field.ordinal < 65535:
            _reject('current field ordinal must be a nonzero U16')
        if full in by_id or field.ordinal in ordinals:
            _reject('current registry has duplicate full ID or ordinal')
        by_id[full] = field
        ordinals.add(field.ordinal)
    if not by_id:
        _reject('empty current registry is not a normalized-store profile')
    return by_id


def _complete_context(context, current_fields):
    """Return a current-key context only after its whole registry is checked."""
    if type(context) is not wire.TemplateContext:
        _reject('exact finite TemplateContext is required')
    if type(context.field_ids) is not dict:
        _reject('explicit complete template field map is required')
    ids = dict(context.field_ids)
    for key, values in current_fields.items():
        expected = _current_map(values)
        supplied = ids.get(key)
        if type(supplied) is not dict:
            _reject('every normalized ValueForm needs current template IDs')
        normalized = {}
        for ordinal, identifier in supplied.items():
            if type(ordinal) is not int or ordinal <= 0 or ordinal >= 65535:
                _reject('template ordinal must be a nonzero U16')
            normalized[ordinal] = _full(identifier)
        if normalized != {field.ordinal: full for full, field in expected.items()}:
            _reject('current field tuple and complete template registry disagree')
        ids[key] = normalized
    return replace(context, field_ids=ids, preserve_source_ordinals=False)


def _rebuild_tail(old, entries):
    """Replace only D2 ordinals; preserve the exact D1/DE/DF suffix bytes."""
    payload = b''.join(b'\xff' + identifier + ordinal.to_bytes(2, 'little')
                       for identifier, ordinal in entries)
    chunks = tuple(payload[p:p + 65000] for p in range(0, len(payload), 65000))
    d2 = b'\xd2' + len(entries).to_bytes(2, 'big')
    if entries:
        d2 += len(payload).to_bytes(4, 'big')
        d2 += b''.join(b'\x0f' + len(chunk).to_bytes(4, 'big') + chunk for chunk in chunks)
    return load_value_form_tail(
        d2 + old.source_wire[len(old.field_map.source_wire):],
        base_position=old.source_base_position,
    )


def _assert_reference_free(doc):
    """Inventory every known serialized reference category before key movement."""
    if doc.persistent_objects is not None:
        _reject('entity persistent objects may contain unproved numeric references')
    for formset_index, fs in enumerate(doc.formsets):
        if fs.persistent_attributes is not None:
            _reject('FormSet persistent attributes may contain unproved numeric references')
        for path, form in wire.walk_forms(doc):
            if path[0] != formset_index:
                continue
            if form.header.parent is not None or form.header.parent_field_index or form.header.parent_field_id:
                _reject('child-parent header references are outside normalized-store')
            if form.tables:
                _reject('E1 table references are outside normalized-store')
            if form.children:
                _reject('child Form graph is outside normalized-store')
            if form.links:
                _reject('D7/kind22 links are outside normalized-store')
            if form.derived_tail is None:
                _reject('complete ValueForm D2 tail is required')
            if any(form.derived_tail.groups):
                _reject('form/record/value attachment references are outside normalized-store')
            if form.source_table_id is not None and form.source_table_id != form.table_id:
                _reject('StringTable relocation is outside normalized-store')
            if form.metadata.get('source_header') != form.header or type(form.metadata.get('source_header_wire')) is not bytes:
                _reject('unchanged raw source header is required')


def _normalize_form(bound, path, form, current_fields):
    fs = bound.document.formsets[path[0]]
    key = (fs.header.identifier, form.header.identifier)
    if key not in current_fields:
        _reject('missing full current registry for a selected ValueForm')
    current = _current_map(current_fields[key])
    entries = form.derived_tail.field_map.entries
    source = {}
    for entry in entries:
        full = _full(entry.identifier)
        if type(entry.source_field_index) is not int or not 1 <= entry.source_field_index < 65535:
            _reject('D2 source ordinal must be a nonzero U16')
        if entry.source_field_index in source or full in source.values():
            _reject('D2 source identity must be one-to-one')
        if full not in current:
            _reject('D2 full ID is absent from the same complete current registry')
        source[entry.source_field_index] = full
    if not source:
        _reject('empty D2 cannot prove source identity for a normalized hash')
    validate_hash_structure(form.hash_state)
    if any(len(block.nodes) != block.capacity for block in form.hash_state.buffers):
        _reject('hash spare allocation bytes are not safe to reconstruct')
    remapped = []
    details = []
    for block in form.hash_state.buffers:
        for node in block.nodes:
            full = source.get(node.field_index)
            if full is None:
                _reject('hash node has no D2 full-ID identity')
            target = current[full]
            if node.element_index != 0:
                _reject('array-element remapping is outside normalized-store')
            if node.header or node.specific_attributes & 0x0a:
                _reject('headered/computed/error-bearing node needs native lifecycle semantics')
            if (node.kind_byte, node.flag10) != (target.kind, target.format):
                _reject('kind/format conversion is outside normalized-store')
            if node.kind_byte not in (10, 12, 13):
                _reject('string, box, and unproved scalar encodings are outside normalized-store')
            remapped.append(replace(node, next_index=0xffffffff, field_index=target.ordinal))
            details.append((path, full, node.field_index, target.ordinal, node.element_index))
    if len({(node.field_index, node.element_index) for node in remapped}) != len(remapped):
        _reject('current-key collision would merge distinct source cells')
    rebuilt = hash_for_nodes(tuple(remapped), bucket_count=len(form.hash_state.heads))
    if tuple(block.capacity for block in rebuilt.buffers) != tuple(block.capacity for block in form.hash_state.buffers):
        _reject('physical buffer layout changed while rebuilding hash chains')
    d2 = tuple((entry.identifier, current[_full(entry.identifier)].ordinal) for entry in entries)
    new_tail = _rebuild_tail(form.derived_tail, d2)
    if len(new_tail.source_wire) != len(form.derived_tail.source_wire):
        _reject('D2 rewrite unexpectedly changed tail length')
    return replace(form, hash_state=rebuilt, derived_tail=new_tail), tuple(details), d2


def _serialize_reference_free(doc, buffers, context):
    """Whole-document writer whose only mutation-capable field is D2/key state."""
    wire._entity(doc.entity_header)
    if doc.persistent_objects is not None:
        _reject('entity attachment writer is deliberately unavailable')
    used_ids, registries, seen = set(), {}, set()
    for fs in doc.formsets:
        wire._formset(fs.header, context)
        fsid = fs.header.identifier
        if fsid in seen or fs.persistent_attributes is not None:
            _reject('unique reference-free FormSet is required')
        seen.add(fsid); registry = {}
        for form in fs.forms:
            if form.children or form.links or form.tables or form.header.parent is not None:
                _reject('reference-free root Form inventory required')
            if form.header.file_copy in registry or form.table_id in used_ids:
                _reject('unique Form/file-copy/StringTable identities required')
            if context.current_table_ids.get((fsid, form.header.file_copy), form.table_id) != form.table_id:
                _reject('current StringTable ID must remain unchanged')
            registry[form.header.file_copy] = wire.Parent(form.header.identifier, form.header.file_copy, form.header.word7c)
            used_ids.add(form.table_id)
        registries[fsid] = registry
    header = wire.store_entity_header(doc.header)
    base, formset_base, formset_parts = len(header), len(header) + 5 + 4 * (len(doc.formsets) + 1), []
    for fs in doc.formsets:
        fs_header = wire.store_formset_header(fs.header)
        form_base = formset_base + len(fs_header) + 5 + 4 * (len(fs.forms) + 1)
        forms = []
        for form in fs.forms:
            form_header = form.metadata['source_header_wire']
            wire._validate_header_wire(form_header, form.header, tuple(registries[fs.header.identifier].values()))
            hash_wire = wire.store_hash(form.hash_state, buffers, version=18)
            wire._error(hash_wire.code, 'normalized Hash')
            strings = wire.store_selected_section(form.string_table, buffers, table_id=form.table_id,
                                                  requested_share=0, actual_share=0)
            pos = form_base + len(form_header) + 2
            mapping = wire.store_map(wire.new_map(0xc9, 4), pos).mapping
            value_start = pos + 21
            for at in (value_start, value_start + len(hash_wire.wire), value_start + len(hash_wire.wire),
                       value_start + len(hash_wire.wire) + len(strings.string_section)):
                mapping = wire.append_position(mapping, at).mapping
            data = bytearray(form_header + strings.table_id_wire + wire.store_map(mapping, pos).wire +
                             hash_wire.wire + strings.string_section)
            data.extend(wire._write_index(0xe0, form_base + len(data), ()))
            child_base = form_base + len(data)
            data.extend(wire._write_index(0xc8, child_base, ()))
            data.extend(wire._write_index(0xd7, form_base + len(data), ()))
            # A changed packed Hash can change its encoded-frame length.  The
            # accepted tail has no D1/DE/DF objects, so it has no retained
            # position-sensitive attachment body to relocate.  The reader
            # derives the new absolute tail position from this complete wire.
            data.extend(form.derived_tail.source_wire)
            forms.append(bytes(data)); form_base += len(data)
        part = fs_header + wire._write_index(0xc8, formset_base + len(fs_header), tuple(forms))
        formset_parts.append(part); formset_base += len(part)
    return header + wire._write_index(0xc7, base, tuple(formset_parts))


def normalize_store_bytes(wire_bytes, buffers, *, template_context, current_fields, arrays):
    """Re-key D2 and physical hash chains from source full IDs to current IDs.

    ``current_fields`` and ``arrays`` must be the caller's complete same-registry
    view for each ValueForm.  This function creates no fields, assigns no free
    saved ID, and accepts no caller-supplied edited document or success flag.
    """
    if type(wire_bytes) is not bytes or type(current_fields) is not dict or type(arrays) is not dict:
        _reject('immutable source bytes and explicit complete registry maps are required')
    original = load_source_bound_document_bytes(wire_bytes, buffers, template_context=template_context,
                                                current_fields=current_fields, arrays=arrays)
    validate_document_hashes(original.document)
    _assert_reference_free(original.document)
    context = _complete_context(original.context, current_fields)
    document, all_nodes, all_d2 = original.document, [], []
    for path, form in tuple(wire.walk_forms(original.document)):
        updated, nodes, d2 = _normalize_form(original, path, form, current_fields)
        document = wire.replace_form(document, path, updated)
        all_nodes.extend(nodes); all_d2.extend((path, identifier, ordinal) for identifier, ordinal in d2)
    normalized = replace(original, document=document, context=context,
                         bindings=_bindings(document, current_fields, arrays))
    output = _serialize_reference_free(normalized.document, buffers, context)
    readback = load_source_bound_document_bytes(output, buffers, template_context=context,
                                                current_fields=current_fields, arrays=arrays)
    validate_document_hashes(readback.document)
    for path, identifier, ordinal in all_d2:
        actual = dict((entry.identifier, entry.source_field_index)
                      for entry in dict(wire.walk_forms(readback.document))[path].derived_tail.field_map.entries)
        if actual.get(identifier) != ordinal:
            _reject('full-document D2 readback did not retain the exact current key')
    return NormalizedStoreResult(output, original, readback, hashlib.sha256(wire_bytes).hexdigest(),
                                 hashlib.sha256(output).hexdigest(), tuple(all_nodes), tuple(all_d2))
