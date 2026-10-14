"""Local TaxML candidates with explicit caller bindings; no whole-return import.

This adapter never decrypts a container and never writes an original .tax file.
Registry bytes and the wire profile are supplied by the user for each inspection.
Unknown facts stay blocking. The federal engine receives only reviewed W-2 rows.
"""
import base64
import hashlib
import json
import re

import taxml_wire as wire

BOX_KEYS = {1: 'wages', 2: 'federal_withholding', 3: 'social_security_wages',
            4: 'social_security_withholding', 5: 'medicare_wages', 6: 'medicare_withholding'}
HASH = re.compile(r'^[0-9a-f]{64}$')


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def decode_blob(value, maximum):
    if not isinstance(value, str) or len(value) > ((maximum + 2) // 3) * 4:
        raise ValueError('Choose a local file within the import size limit.')
    try:
        data = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError('Invalid local file bytes.') from error
    if len(data) > maximum:
        raise ValueError('Choose a local file within the import size limit.')
    return data


def validate_profile(profile):
    keys = {'format', 'tax_year', 'root_qname', 'namespace_profile', 'templates'}
    if not isinstance(profile, dict) or set(profile) != keys:
        raise ValueError('Choose an explicit Tax Reborn TaxML wire-profile JSON file.')
    if profile['format'] != 'tax-reborn-taxml-wire-profile-v1' or type(profile['tax_year']) is not int or profile['tax_year'] != 2025:
        raise ValueError('This import requires an explicit tax-year 2025 wire profile.')
    root = profile['root_qname']
    if not isinstance(root, str) or not root or len(root) > 512 or re.search(r'[\x00-\x20\x7f]', root):
        raise ValueError('The wire profile must bind the document root QName.')
    namespaces = profile['namespace_profile']
    if not isinstance(namespaces, dict) or set(namespaces) != {'formset', 'form', 'field'}:
        raise ValueError('The wire profile must explicitly bind formset, form and field namespaces.')
    for values in namespaces.values():
        if not isinstance(values, list) or not 1 <= len(values) <= 8 or any(not isinstance(v, str) or len(v) > 512 for v in values) or len(set(values)) != len(values):
            raise ValueError('Invalid explicit namespace binding.')
    templates = profile['templates']
    if not isinstance(templates, list) or not 1 <= len(templates) <= 100:
        raise ValueError('Select one or more exact caller-owned template identities.')
    selected = {}
    for item in templates:
        if not isinstance(item, dict) or set(item) != {'formset_id', 'form_id', 'carrier_sha256', 'resource_id'}:
            raise ValueError('Invalid template profile identity.')
        if any(not isinstance(item[k], str) or not item[k] or len(item[k]) > 128 for k in ('formset_id', 'form_id')):
            raise ValueError('Invalid template form identity.')
        if not isinstance(item['carrier_sha256'], str) or not HASH.fullmatch(item['carrier_sha256']) or type(item['resource_id']) is not int or not 0 <= item['resource_id'] <= 65535:
            raise ValueError('Invalid template carrier identity.')
        key = item['formset_id'], item['form_id']
        if key in selected:
            raise ValueError('Ambiguous duplicate template profile identity.')
        selected[key] = item['carrier_sha256'], item['resource_id']
    return selected, {k: tuple(v) for k, v in namespaces.items()}


def inspect_request(request):
    if not isinstance(request, dict) or set(request) != {'base64', 'container', 'profile', 'carriers', 'profile_acknowledged'}:
        raise ValueError('Invalid local TaxML inspection request.')
    if request['profile_acknowledged'] is not True:
        raise ValueError('Review and acknowledge the selected wire profile before inspection.')
    selected, namespaces = validate_profile(request['profile'])
    data = decode_blob(request['base64'], 10 * 1024 * 1024)
    supplied = request['carriers']
    if not isinstance(supplied, list) or not 1 <= len(supplied) <= 8:
        raise ValueError('Choose caller-owned XPRF registry files for this wire profile.')
    carriers, seen = [], set()
    for carrier in supplied:
        if not isinstance(carrier, dict) or set(carrier) != {'base64', 'sha256'} or not isinstance(carrier['sha256'], str) or not HASH.fullmatch(carrier['sha256']):
            raise ValueError('Every registry file requires its explicit SHA-256 identity.')
        if carrier['sha256'] in seen:
            raise ValueError('Duplicate registry file identity.')
        seen.add(carrier['sha256'])
        carriers.append((decode_blob(carrier['base64'], 32 * 1024 * 1024), carrier['sha256']))
    if {identity[0] for identity in selected.values()} != seen:
        raise ValueError('Selected wire-profile identities must exactly match the supplied registry files.')
    registry = wire.Registry.from_xprf(carriers)
    for key, identity in selected.items():
        registry.resolve(*key, identity)
    archive_member = None
    if request['container'] == 'plaintext_xml':
        payload = data
    elif request['container'] == 'declared_plaintext_zip':
        archive = wire.read_archive(data, declared_plaintext=True)
        documents = [d for d in archive.documents if d['taxml_type']]
        if len(documents) != 1 or len(archive.documents) != 1:
            raise ValueError('A plaintext ZIP must have exactly one unambiguous TaxML document; other document facts cannot be imported.')
        archive_member = documents[0]['member']
        payload = archive.members[archive_member]
    else:
        raise ValueError('Select plaintext XML or explicitly declared plaintext ZIP. Encrypted or unknown containers are unsupported.')
    document = wire.read_taxml(payload, registry, profiles=selected,
        namespace_profile=namespaces, root_qname=request['profile']['root_qname'])
    unresolved = list(document.unresolved)
    if document.root.attrib:
        unresolved.append({'path': '', 'code': 'unmapped_root_metadata', 'detail': sorted(document.root.attrib)})
    if document.root.text and document.root.text.strip():
        unresolved.append({'path': '', 'code': 'unmapped_root_text', 'detail': 'Source root contains text outside supported fields.'})
    allowed = {field for _, field in wire.BOX_FIELDS} | {'NAME', 'CA', 'CA2', 'SSTIPS', 'DCB'}
    # Even known decoded values may have facts the current W-2 row cannot hold.
    # Do not hide those values behind a superficially successful import.
    for value in document.values:
        if value['form_id'] != 'FW2' or value['copy_number'] == 0 or value['field_id'] not in allowed:
            unresolved.append({'path': value['key'], 'code': 'unmapped_source_fact', 'detail': value['field_id']})
        elif (value['field_id'] in {'NAME', 'CA', 'CA2'} and value['kind'] != 7) or (
                value['field_id'] in {'SSTIPS', 'DCB'} and
                (value['kind'] != 11 or value['scalar'].get('scale') != 2)):
            unresolved.append({'path': value['key'], 'code': 'unsupported_w2_semantic_type',
                'detail': value['field_id']})
    candidates = []
    profile_hash = canonical_hash(request['profile'])
    source_hash = wire.digest(data)
    for candidate in wire.w2_candidates(document):
        values = [v for v in document.values if v['key'].rsplit('/', 2)[0] == candidate['form_path']]
        first = values[0]
        fields = {v['field_id']: v for v in values}
        employer_parts = [fields[name]['scalar']['text'] for name in ('CA', 'CA2')
            if name in fields and fields[name]['kind'] == 7 and 'text' in fields[name]['scalar']]
        amounts = {BOX_KEYS[b['box']]: b['amount'] for b in candidate['boxes']}
        sources = {BOX_KEYS[b['box']]: {'wire_text': b['source_text'], 'field_id': b['field_id'],
            'key': b['source_value_key'], 'value_flags': b['source_value_flags'],
            'specific_flags': b['source_specific_flags']} for b in candidate['boxes']}
        optional_missing = []
        for name, field_id in (('social_security_tips', 'SSTIPS'), ('dependent_care_benefits', 'DCB')):
            value = fields.get(field_id)
            if value is not None and value['kind'] == 11 and value['scalar'].get('scale') == 2:
                amounts[name] = value['scalar']['decimal']
                sources[name] = {'wire_text': value['source_text'], 'field_id': field_id,
                    'key': value['key'], 'value_flags': value['source_value_flags'], 'specific_flags': value['source_specific_flags']}
            else:
                optional_missing.append(name)
        receipt = {'source_sha256': source_hash, 'wire_profile_sha256': profile_hash,
            'template_carrier_sha256': first['template_carrier_sha256'],
            'template_resource_id': first['template_resource_id'],
            'form_path': candidate['form_path'], 'archive_member': archive_member,
            'candidate_sha256': canonical_hash({'wire_candidate': candidate, 'mapped_amounts': amounts,
                'mapped_sources': sources, 'employer_parts': employer_parts, 'missing_manual_fields': optional_missing})}
        candidates.append({'employer': ' '.join(employer_parts) or None, 'owner': None,
            'amounts': amounts, 'sources': sources,
            'missing_boxes': candidate['unresolved_boxes'], 'receipt': receipt,
            'can_review': not unresolved and not candidate['unresolved_boxes'],
            'requires_manual_fields': ['owner', *optional_missing]})
    return {'format': 'tax-reborn-taxml-candidates-v1', 'tax_year': 2025,
        'source_sha256': source_hash, 'wire_profile_sha256': profile_hash,
        'root_qname_bound': document.root_qname_bound, 'candidates': candidates,
        'unresolved_facts': unresolved, 'tax_values_imported': False,
        'full_return_imported': False, 'original_program_acceptance_verified': False,
        'warnings': ['The selected wire profile is supplied by you. Original TurboTax loading and recalculation are unverified.',
            'Only supported W-2 box candidates are offered. This is not a complete .tax return import.',
            'Select the owner and enter Boxes 7 and 10 explicitly. Missing values never establish zero.',
            'Check tax year 2025 and every amount against the original W-2 before adding a record.']}
