"""Local binary tax-data inspection and loss-checked source corrections.

Only the explicitly reconstructed native stream profile is accepted. Templates
are caller-owned and independently byte-validated; the original source stays
immutable. No vendor engine, resource, account or activation is used.
"""
import base64
from dataclasses import fields, is_dataclass, replace
from decimal import Decimal
import re

import taxml_wire as wire
import taxml_preparation as prep
from interop.form_core.cx_string_wire_reference import Buffers, initialize
from interop.form_core.native_amount import decode_amount
from interop.form_core.document_semantics_reference import document_semantic_snapshot
from interop.form_core.native_document_reference import (
    TemplateContext, load_document_bytes, store_document_bytes,
    walk_forms, replace_form,
)
from interop.form_core.string_wire_reference import read as read_string

PROFILE = 'tax-reborn-binary-entity-profile-v1'
MAX_BYTES = 10 * 1024 * 1024


class OwnedTableIDs(dict):
    """Allocate this App's registry IDs, independently of saved native IDs."""
    def get(self, key, default=None):
        if key not in self:
            if len(self) >= 4096:
                raise ValueError('Too many independent string tables.')
            self[key] = len(self) + 1
        return self[key]


def _buffers():
    # Successful-allocation tokens for the independent codec, not real pointers.
    return initialize(Buffers(), prepared_compressed_pointer=1000,
                      prepared_scratch_pointer=2000).buffers


def _context(request):
    if not isinstance(request, dict) or set(request) != {
        'base64', 'container', 'profile', 'carriers', 'profile_acknowledged'
    } or request['container'] != 'binary_entity':
        raise ValueError('Invalid local binary tax-data request.')
    if request['profile_acknowledged'] is not True:
        raise ValueError('Review and acknowledge the selected data profile.')
    profile = request['profile']
    if not isinstance(profile, dict) or set(profile) != {
        'format', 'tax_year', 'templates', 'template_versions'
    } or profile['format'] != PROFILE or profile['tax_year'] != 2025:
        raise ValueError('Choose an explicit supported 2025 binary data profile.')
    selected, _ = prep.validate_profile({
        'format': 'tax-reborn-taxml-wire-profile-v1', 'tax_year': 2025,
        'root_qname': 'independent-binary-profile',
        'namespace_profile': {key: [''] for key in ('formset', 'form', 'field')},
        'templates': profile['templates'],
    })
    versions = profile['template_versions']
    if not isinstance(versions, dict) or set(versions) != {key[0] for key in selected}:
        raise ValueError('Bind a template version for each selected formset.')
    if any(type(v) is not int or not 0 <= v <= 0xffffffff for v in versions.values()):
        raise ValueError('Invalid explicit template version.')
    supplied = request['carriers']
    if not isinstance(supplied, list) or not 1 <= len(supplied) <= 8:
        raise ValueError('Choose the caller-owned registry files for this profile.')
    carriers, seen = [], set()
    for item in supplied:
        if not isinstance(item, dict) or set(item) != {'base64', 'sha256'}:
            raise ValueError('Invalid registry binding.')
        if not isinstance(item['sha256'], str) or not prep.HASH.fullmatch(item['sha256']):
            raise ValueError('Every registry requires a SHA-256 binding.')
        if item['sha256'] in seen:
            raise ValueError('Duplicate registry identity.')
        seen.add(item['sha256'])
        carriers.append((prep.decode_blob(item['base64'], 32 * 1024 * 1024), item['sha256']))
    if seen != {identity[0] for identity in selected.values()}:
        raise ValueError('Selected templates must exactly match the registry files.')
    registry = wire.Registry.from_xprf(carriers)
    ids = {}
    for key, identity in selected.items():
        template = registry.resolve(*key, identity)
        ids[(key[0].encode('ascii'), key[1].encode('ascii'))] = {
            field.ordinal: field.field_id.encode('ascii') for field in template.fields
        }
    context = TemplateContext(
        template_versions={key.encode('ascii'): val for key, val in versions.items()},
        field_ids=ids, current_table_ids=OwnedTableIDs(),
        preserve_unresolved_links=True,
    )
    source = prep.decode_blob(request['base64'], MAX_BYTES)
    buffers = _buffers()
    document = load_document_bytes(source, buffers, template_context=context)
    return document, buffers, context, registry, selected, source


def _text(raw):
    return raw.decode('ascii', errors='backslashreplace') if isinstance(raw, bytes) else str(raw)


def _template(document, path, form, registry, selected):
    fsid = _text(document.formsets[path[0]].header.identifier)
    key = fsid, _text(form.header.identifier)
    if key not in selected:
        return fsid, None, None
    return fsid, registry.resolve(*key, selected[key]), selected[key]


def _field_fact(form, node, spec):
    fact = {'ordinal': node.field_index, 'element': node.element_index,
            'kind': node.kind_byte, 'raw64': str(node.raw),
            'value_header': node.header, 'specific_attributes': node.specific_attributes,
            'exponent_byte': node.exponent_byte, 'field_id': spec.field_id if spec else None,
            'text': None, 'status': 'unbound_metadata', 'editable': False}
    if spec is None or spec.kind != node.kind_byte:
        return fact
    if spec.is_array or node.element_index != 0 or spec.format != 0:
        fact['status'] = 'unsupported_field_profile'
        return fact
    if node.kind_byte in (11, 12):
        value = decode_amount(kind_byte=node.kind_byte, raw64=node.raw,
            exponent_byte=node.exponent_byte, fv_attributes=node.specific_attributes,
            value_header=node.header)
        fact.update(status=value.status, text=None if value.value is None else format(value.value, 'f'),
                    editable=value.status == 'value')
    elif node.kind_byte == 7:
        if not node.specific_attributes & 1:
            fact['status'] = 'unused'
        elif node.header & 0x80:
            fact['status'] = 'diagnostic_header'
        elif node.raw & 65535 != form.table_id:
            fact['status'] = 'unresolved_string_table'
        else:
            fact.update(status='text', text=_text(read_string(form.string_table, (node.raw >> 16) & 65535)))
    else:
        fact['status'] = 'raw_type_preserved'
    return fact


def _inspect(request):
    document, buffers, context, registry, selected, source = _context(request)
    source_hash, profile_hash = wire.digest(source), prep.canonical_hash(request['profile'])
    candidates, unresolved, archive_forms = [], [], []
    per_set = {}
    for path, form in walk_forms(document):
        fsid, template, identity = _template(document, path, form, registry, selected)
        ordinal = per_set.get(path[0], 0)
        per_set[path[0]] = ordinal + 1
        form_path = f'0/{path[0]}/{ordinal}'
        specs = {field.ordinal: field for field in template.fields} if template else {}
        facts = [_field_fact(form, node, specs.get(node.field_index))
                 for buffer in form.hash_state.buffers for node in buffer.nodes]
        archive_forms.append({'path': list(path), 'form_path': form_path,
            'formset_id': fsid, 'form_id': _text(form.header.identifier),
            'file_copy': form.header.file_copy, 'fields': facts,
            'tables': len(form.tables), 'children': len(form.children),
            'links': [{'form_id': _text(link.form_id), 'file_copy': link.file_copy,
                       'field_id': _text(link.field_id), 'element': link.element_index,
                       'resolved': link.resolved} for link in form.links]})
        # Unknown values stay preserved in the source editor and block claims of
        # importing a complete return. They never silently become ordinary tax.
        unknown = [fact for fact in facts if fact['specific_attributes'] & 1 and
                   fact['status'] not in ('value', 'text')]
        unresolved.extend({'path': form_path, 'code': fact['status'],
                           'detail': fact['field_id'] or str(fact['ordinal'])}
                          for fact in unknown)
        name = _text(form.header.identifier)
        if not template or name not in ('FW2', 'F1099I', 'F1099D'):
            if any(fact['specific_attributes'] & 1 for fact in facts):
                unresolved.append({'path': form_path, 'code': 'unmapped_tax_form', 'detail': name})
            continue
        mappings = (prep.DIVIDEND_FIELDS if name == 'F1099D' else prep.INTEREST_FIELDS
                    if name == 'F1099I' else tuple((box, field, prep.BOX_KEYS[box]) for box, field in wire.BOX_FIELDS))
        named = {}
        for fact in facts:
            if fact['field_id'] in named:
                raise ValueError('Ambiguous repeated scalar field in the binary source.')
            if fact['field_id']:
                named[fact['field_id']] = fact
        amounts, sources, missing = {}, {}, []
        for box, field_id, destination in mappings:
            fact = named.get(field_id)
            if not fact or fact['status'] != 'value' or fact['kind'] != 11:
                missing.append(box)
                continue
            number = Decimal(fact['text'])
            if not 0 <= number <= 1000000000:
                missing.append(box)
                continue
            amounts[destination] = format(number, '.2f')
            sources[destination] = {'field_id': field_id, 'wire_text': fact['text'],
                'key': f'{form_path}/{fact["ordinal"]}', 'ordinal': fact['ordinal'],
                'binary_path': list(path), 'element': fact['element'],
                'value_flags': {'raw_header': fact['value_header']},
                'specific_flags': {'raw_attributes': fact['specific_attributes']}}
        if name == 'F1099D' and not missing and (
            Decimal(amounts['qualified']) > Decimal(amounts['ordinary']) or
            Decimal(amounts['unrecaptured_1250_gain']) + Decimal(amounts['collectibles_gain']) > Decimal(amounts['capital_gain_distributions'])
        ):
            unresolved.append({'path': form_path, 'code': 'invalid_dividend_box_subsets', 'detail': name})
        optional_missing = []
        if name == 'FW2':
            for destination, field_id in [('social_security_tips', 'SSTIPS'), ('dependent_care_benefits', 'DCB')]:
                fact = named.get(field_id)
                if fact and fact['status'] == 'value' and fact['kind'] == 11:
                    amounts[destination] = fact['text']
                else:
                    optional_missing.append(destination)
        employer = ' '.join(named[key]['text'] for key in ('CA', 'CA2')
                            if key in named and named[key]['status'] == 'text') or None
        owner = {'formset_id': fsid, 'form_name': name,
                 'fileCopyNum': str(form.header.file_copy), 'binary_path': list(path)}
        digest = prep.canonical_hash({'owner': owner, 'amounts': amounts, 'sources': sources, 'missing': missing})
        candidates.append({'record_type': 'dividends' if name == 'F1099D' else 'interest' if name == 'F1099I' else 'w2',
            'source_format': 'binary_entity', 'payer': None, 'employer': employer, 'owner': None,
            'amounts': amounts, 'sources': sources, 'missing_boxes': missing,
            'receipt': {'source_sha256': source_hash, 'wire_profile_sha256': profile_hash,
                'template_carrier_sha256': identity[0], 'template_resource_id': identity[1],
                'form_path': form_path, 'archive_member': None, 'candidate_sha256': digest},
            'source_owner': owner, 'can_review': not missing and not unknown,
            'can_edit_source': not missing,
            'requires_manual_fields': ['owner', *optional_missing] if name == 'FW2' else
                ['payer', 'supported_interest_scope'] if name == 'F1099I' else
                ['payer', 'supported_dividend_scope', 'qualified_dividend_eligibility']})
    # Preserve the existing conservative import boundary across unknown siblings.
    for candidate in candidates:
        candidate['can_review'] = candidate['can_review'] and not unresolved
    result = {'format': 'tax-reborn-taxml-candidates-v1', 'source_format': 'binary_entity',
        'tax_year': 2025, 'source_sha256': source_hash, 'wire_profile_sha256': profile_hash,
        'root_qname_bound': True, 'candidates': candidates, 'unresolved_facts': unresolved,
        'tax_values_imported': False, 'full_return_imported': False,
        'original_program_acceptance_verified': False,
        'binary_archive': {'forms': archive_forms, 'formsets': len(document.formsets),
                           'all_source_bytes_retained': True},
        'warnings': ['Binary source fields and nonempty supported structures are retained locally.',
            'Only explicitly bound supported income records can enter this App after review.',
            'Corrected binary copies do not run the original tax engine or update its derived totals.',
            'This supported stream profile has not been verified against an original saved .tax return.']}
    return result, document, buffers, context


def inspect_request(request):
    return _inspect(request)[0]


def _snapshot(value):
    if is_dataclass(value):
        result = {field.name: _snapshot(getattr(value, field.name)) for field in fields(value)
                  if field.name not in {'metadata', 'source_bytes', 'source_table_id', 'resolved'}}
        if hasattr(value, 'metadata'):
            # These carry serialized bits not represented by ordinary typed
            # fields. Byte positions and runtime flags may legitimately differ.
            retained = {'source_header_wire', 'source_wire', 'source_description', 'source_element_u32'}
            result['retained_wire_metadata'] = {key: _snapshot(item) for key, item in value.metadata.items() if key in retained}
        return result
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (tuple, list)):
        return [_snapshot(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _snapshot(item) for key, item in value.items()}
    return value


def _rewrite(inspection, expected_source, changes, confirmed):
    if confirmed is not True:
        raise ValueError('Review and confirm the changed source amounts first.')
    result, document, buffers, context = _inspect(inspection)
    if expected_source != result['source_sha256']:
        raise ValueError('The binary source changed; inspect it again.')
    if not isinstance(changes, list) or not 1 <= len(changes) <= 1024:
        raise ValueError('Choose one or more supported amount corrections.')
    forms = {tuple(path): form for path, form in walk_forms(document)}
    facts = {(tuple(form['path']), field['ordinal'], field['element']): field
             for form in result['binary_archive']['forms'] for field in form['fields']}
    seen = set()
    for change in changes:
        if not isinstance(change, dict) or set(change) != {'path', 'ordinal', 'element', 'value'}:
            raise ValueError('Invalid source correction.')
        if not isinstance(change['path'], list) or not change['path'] or any(type(v) is not int for v in change['path']):
            raise ValueError('Invalid binary form path.')
        if any(type(change[key]) is not int or not 0 <= change[key] <= 65535 for key in ('ordinal', 'element')):
            raise ValueError('Invalid binary field address.')
        key = tuple(change['path']), change['ordinal'], change['element']
        fact = facts.get(key)
        if key in seen or not fact or not fact['editable']:
            raise ValueError('The source field is duplicate, unused or unsupported.')
        seen.add(key)
        text = change['value']
        if not isinstance(text, str) or not re.fullmatch(r'-?[0-9]{1,13}(?:\.[0-9]{1,2})?', text):
            raise ValueError('Enter a supported amount with at most two decimal places.')
        number = Decimal(text)
        scale = 2 if fact['kind'] == 11 else 0
        scaled = number.scaleb(scale)
        if scaled != scaled.to_integral_value() or not -(1 << 63) < scaled < (1 << 63) - 1:
            raise ValueError('Amount exceeds this field’s precision or range.')
        bits = int(scaled) & ((1 << 64) - 1)
        check = decode_amount(kind_byte=fact['kind'], raw64=bits, exponent_byte=fact['exponent_byte'],
            fv_attributes=fact['specific_attributes'], value_header=fact['value_header'])
        if check.status != 'value':
            raise ValueError('The corrected value is reserved, unused or outside the supported range.')
        form = forms[key[0]]
        hits = sum(node.field_index == key[1] and node.element_index == key[2]
                   for buffer in form.hash_state.buffers for node in buffer.nodes)
        if hits != 1:
            raise ValueError('The binary field address is ambiguous.')
        updated = replace(form, hash_state=replace(form.hash_state, buffers=tuple(
            replace(buffer, nodes=tuple(replace(node, raw=bits)
                if node.field_index == key[1] and node.element_index == key[2] else node
                for node in buffer.nodes)) for buffer in form.hash_state.buffers)))
        forms[key[0]] = updated
        document = replace_form(document, key[0], updated)
    expected = document_semantic_snapshot(document)
    corrected = store_document_bytes(document, buffers, template_context=context)
    reread = load_document_bytes(corrected, buffers, template_context=context)
    if document_semantic_snapshot(reread) != expected:
        raise ValueError('Corrected copy failed full structure and value readback; no copy was exported.')
    return {'format': 'tax-reborn-corrected-binary-v1', 'base64': base64.b64encode(corrected).decode(),
        'mime': 'application/octet-stream', 'source_sha256': expected_source,
        'output_sha256': wire.digest(corrected), 'changed_fields': len(changes),
        'all_other_parsed_facts_preserved': True, 'binary_roundtrip_verified': True,
        'full_return_recalculated': False, 'original_program_acceptance_verified': False}


def edit_request(request):
    if not isinstance(request, dict) or set(request) != {'inspection', 'expected_source_sha256', 'changes', 'confirmed'}:
        raise ValueError('Invalid binary source edit request.')
    return _rewrite(request['inspection'], request['expected_source_sha256'], request['changes'], request['confirmed'])


def export_request(request):
    if not isinstance(request, dict) or set(request) != {'inspection', 'expected_candidate_sha256', 'amounts', 'confirmed'}:
        raise ValueError('Invalid corrected binary request.')
    result = inspect_request(request['inspection'])
    choices = [candidate for candidate in result['candidates']
               if candidate['receipt']['candidate_sha256'] == request['expected_candidate_sha256']]
    if len(choices) != 1 or not choices[0]['can_edit_source']:
        raise ValueError('The binary candidate is missing, ambiguous or incomplete.')
    candidate = choices[0]
    names = [name for _, _, name in prep.DIVIDEND_FIELDS] if candidate['record_type'] == 'dividends' else [name for _, _, name in prep.INTEREST_FIELDS] if candidate['record_type'] == 'interest' else list(prep.BOX_KEYS.values())
    amounts = request['amounts']
    if not isinstance(amounts, dict) or set(amounts) != set(names):
        raise ValueError('Correct every supported source box explicitly.')
    changes = []
    for name in names:
        text = amounts[name]
        if not isinstance(text, str) or not re.fullmatch(r'[0-9]{1,13}(?:\.[0-9]{1,2})?', text) or Decimal(text) > 1000000000:
            raise ValueError('Enter explicit nonnegative source amounts within the supported range.')
        fact = candidate['sources'][name]
        changes.append({'path': fact['binary_path'], 'ordinal': fact['ordinal'],
                        'element': fact['element'], 'value': text})
    output = _rewrite(request['inspection'], result['source_sha256'], changes, request['confirmed'])
    reread = inspect_request({**request['inspection'], 'base64': output['base64']})
    matches = [item for item in reread['candidates'] if item['receipt']['form_path'] == candidate['receipt']['form_path']]
    if len(matches) != 1 or any(Decimal(matches[0]['amounts'][key]) != Decimal(val) for key, val in amounts.items()):
        raise ValueError('Corrected binary income boxes failed readback.')
    return output
