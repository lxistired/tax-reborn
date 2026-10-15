"""Local TaxML candidates with explicit caller bindings; no whole-return import.

This adapter never decrypts a container. Selected cleartext source copies retain
the complete archive; original-program acceptance remains unverified.
Registry bytes and the wire profile are supplied by the user for each inspection.
Unknown facts stay blocking. The federal engine receives only reviewed rows.
"""
import base64
import hashlib
import json
import re
from decimal import Decimal
import uuid

import taxml_wire as wire
import taxml_native as native
from taxml_xml_edit import patch_text_nodes

BOX_KEYS = {1: 'wages', 2: 'federal_withholding', 3: 'social_security_wages',
            4: 'social_security_withholding', 5: 'medicare_wages', 6: 'medicare_withholding'}
INTEREST_FIELDS = ((1, 'L1', 'interest_income'), (3, 'L3', 'treasury_interest'),
                   (8, 'EXINT', 'tax_exempt_interest'), (4, 'L4', 'federal_withholding'))
DIVIDEND_FIELDS = (('1a', 'L1B', 'ordinary'), ('1b', 'QDIV', 'qualified'),
                   ('2a', 'L1C', 'capital_gain_distributions'),
                   ('2b', 'L2C', 'unrecaptured_1250_gain'),
                   ('2d', 'L1CTX', 'collectibles_gain'), ('4', 'L2', 'federal_withholding'))
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


def validate_native_profile(profile):
    version = profile.get('format') if isinstance(profile, dict) else None
    multiple = version == 'tax-reborn-taxml-native-windows-profile-v2'
    keys = {'format', 'tax_year', 'entity_name', 'formset_name', 'formset_headers', 'templates' if multiple else 'template'}
    if not isinstance(profile, dict) or set(profile) != keys or version not in ('tax-reborn-taxml-native-windows-profile-v1', 'tax-reborn-taxml-native-windows-profile-v2'):
        raise ValueError('Choose an explicit current Windows TaxML profile.')
    if type(profile['tax_year']) is not int or profile['tax_year'] != 2025:
        raise ValueError('This import requires tax year 2025.')
    for key in ('entity_name', 'formset_name'):
        native.qname(profile[key])
    headers = profile['formset_headers']
    if not isinstance(headers, dict) or any(not isinstance(k, str) or not isinstance(v, str) or len(v) > 512 for k, v in headers.items()):
        raise ValueError('Bind exact current Windows formset headers.')
    # Reuse strict identity validation, without confusing internal formset IDs
    # with the independently supplied XML formset name.
    selected, _ = validate_profile({'format': 'tax-reborn-taxml-wire-profile-v1', 'tax_year': 2025,
        'root_qname': native.ROOT, 'namespace_profile': {k: [''] for k in ('formset', 'form', 'field')},
        'templates': profile['templates'] if multiple else [profile['template']]})
    if multiple and (len(selected)>3 or len({key[0] for key in selected})!=1 or any(key[1] not in {'FW2','F1099I','F1099D'} for key in selected)):
        raise ValueError('A mixed profile must bind supported income forms in one internal formset.')
    return selected


def _inspect(request):
    if isinstance(request, dict) and request.get('container') == 'binary_entity':
        import binary_tax
        return binary_tax.inspect_request(request), None, {}
    if not isinstance(request, dict) or set(request) != {'base64', 'container', 'profile', 'carriers', 'profile_acknowledged'}:
        raise ValueError('Invalid local TaxML inspection request.')
    if request['profile_acknowledged'] is not True:
        raise ValueError('Review and acknowledge the selected wire profile before inspection.')
    modern = isinstance(request['profile'], dict) and request['profile'].get('format') in ('tax-reborn-taxml-native-windows-profile-v1','tax-reborn-taxml-native-windows-profile-v2')
    if modern:
        selected, namespaces = validate_native_profile(request['profile']), None
    else:
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
    container_report = None
    if request['container'] == 'plaintext_xml':
        payload = data
    elif request['container'] == 'cleartext_persistence_container':
        import taxml_container
        payload, archive_member, container_report = taxml_container.inspect_source(data)
    elif request['container'] == 'declared_plaintext_zip':
        archive = wire.read_archive(data, declared_plaintext=True)
        documents = [d for d in archive.documents if d['taxml_type']]
        if len(documents) != 1 or len(archive.documents) != 1:
            raise ValueError('A plaintext ZIP must have exactly one unambiguous TaxML document; other document facts cannot be imported.')
        archive_member = documents[0]['member']
        payload = archive.members[archive_member]
    else:
        raise ValueError('Select plaintext XML or explicitly declared plaintext ZIP. Encrypted or unknown containers are unsupported.')
    if modern:
        result, payload, leaves = _inspect_native(request, data, payload, archive_member, registry, selected)
        _attach_container_scope(result, container_report)
        return result, payload, leaves
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
    result = {'format': 'tax-reborn-taxml-candidates-v1', 'tax_year': 2025,
        'source_sha256': source_hash, 'wire_profile_sha256': profile_hash,
        'root_qname_bound': document.root_qname_bound, 'candidates': candidates,
        'unresolved_facts': unresolved, 'tax_values_imported': False,
        'full_return_imported': False, 'original_program_acceptance_verified': False,
        'warnings': ['The selected wire profile is supplied by you. Original TurboTax loading and recalculation are unverified.',
            'Only supported W-2 box candidates are offered. This is not a complete .tax return import.',
            'Select the owner and enter Boxes 7 and 10 explicitly. Missing values never establish zero.',
            'Check tax year 2025 and every amount against the original W-2 before adding a record.']}
    leaves = {value['key']: {'qname': document.elements[value['key']][0].tag,
        'text': value['source_text']} for value in document.values}
    _attach_container_scope(result, container_report)
    return result, payload, leaves


def _attach_container_scope(result, report):
    if report is None:
        return
    result['container_report'] = report
    result['source_container'] = 'cleartext_persistence_container'
    result['warnings'].append('Only explicitly cleartext containers are supported. Other stored documents remain unexamined source content; the native default encrypted format is unsupported.')
    result['unresolved_facts'].extend(report['blocking_metadata_facts'])
    for candidate in result['candidates']:
        candidate['source_format'] = 'cleartext_persistence_container'
        if not report['manifest_metadata_edit_authorized']:
            candidate['can_review'] = False
            candidate['can_edit_source'] = False


def _inspect_native(request, source, payload, archive_member, registry, selected):
    profile = request['profile']
    native_profiles, form_identities = [], {}
    for key, identity in selected.items():
        template = registry.resolve(*key, identity)
        bindings = []
        for field in template.fields:
            binding = native.FieldBinding(field.field_id, field.kind, field.format)
            try:
                binding.expected_headers()
            except native.NativeWireError:
                continue  # A present unsupported field still blocks the reader.
            if not field.hidden and not field.is_array:
                bindings.append(binding)
        native_profiles.append(native.Profile(profile['entity_name'], 2025, profile['formset_name'],
            tuple(profile['formset_headers'].items()), key[1], tuple(bindings), identity[0]).validate())
        form_identities[key[1]] = identity
    document = native.read_native_taxml_profiles(payload, native_profiles)
    root = wire.xml(payload)
    leaves, paths = {}, {}
    for ei, entity in enumerate(root):
        if not isinstance(entity.tag, str) or 'uuid' not in entity.attrib:
            continue
        try:
            uid = str(uuid.UUID(entity.attrib['uuid']))
        except ValueError:
            continue
        for si, formset in enumerate(entity):
            for fi, form in enumerate(formset):
                if not isinstance(form.tag, str):
                    continue
                try:
                    owner = (uid, wire.qname(formset.tag)[1], wire.qname(form.tag)[1], str(int(form.attrib.get('copyNum', '0'))),
                        str(int(form.attrib.get('fileCopyNum', '0'))), str(int(form.attrib.get('porIndex', '0'))))
                except ValueError:
                    continue
                form_path = f'{ei}/{si}/{fi}'
                paths[owner] = form_path
                for vi, field in enumerate(form):
                    if not isinstance(field.tag, str):
                        continue
                    value = list(field)
                    if len(value) == 1 and value[0].tag == '{' + native.TD + '}value':
                        path = f'{form_path}/{vi}/0'
                        leaves[path] = {'qname': value[0].tag, 'text': value[0].text or ''}
    unresolved = [{'path': '', 'code': code, 'detail': 'Current Windows TaxML source context is unresolved.'} for code in document.unresolved]
    candidates = []
    w2_allowed = {name for _, name in native.BOX_FIELDS} | {'NAME', 'CA', 'CA2', 'SSTIPS', 'DCB'}
    profile_hash, source_hash = canonical_hash(profile), wire.digest(source)
    for form in document.forms:
        owner = dict(form.owner)
        form_path = paths.get((owner['entity_uuid'], owner['formset_name'], owner['form_name'], owner['copyNum'], owner['fileCopyNum'], owner['porIndex']), '')
        identity = form_identities[owner['form_name']]
        fields = {f.field_name: f for f in form.fields}
        problems = list(form.unresolved)
        is_interest = owner['form_name'] == 'F1099I'
        is_dividend = owner['form_name'] == 'F1099D'
        is_w2 = owner['form_name'] == 'FW2'
        mapped_fields = DIVIDEND_FIELDS if is_dividend else INTEREST_FIELDS if is_interest else tuple((box, field, BOX_KEYS[box]) for box, field in native.BOX_FIELDS)
        allowed = {field for _, field, _ in mapped_fields} if not is_w2 else w2_allowed
        # The native loader separately checks its actual form factory's
        # IsMulticopy flag. XPRF field metadata does not establish that flag.
        # FW2 factory multicopy is source-verified; F1099I copy-zero acceptance
        # is not established. Keep both zero-copy cases out of the App adapter.
        if (is_w2 or is_interest or is_dividend) and owner['copyNum'] == '0':
            problems.append('unverified_multicopy_factory_binding')
        for fact in form.fields:
            problems.extend(fact.unresolved)
            if fact.field_name not in allowed or not (is_w2 or is_interest or is_dividend):
                problems.append('unmapped_source_fact')
            if is_w2 and fact.field_name in {'NAME', 'CA', 'CA2'} and fact.metadata_kind != 7:
                problems.append('unsupported_w2_semantic_type')
            if is_w2 and fact.field_name in {'SSTIPS', 'DCB'} and (fact.metadata_kind != 11 or fact.metadata_format != 0):
                problems.append('unsupported_w2_semantic_type')
            if (is_interest or is_dividend) and fact.field_name in allowed and (fact.metadata_kind != 11 or fact.metadata_format != 0):
                problems.append('unsupported_dividend_semantic_type' if is_dividend else 'unsupported_interest_semantic_type')
            if (is_interest or is_dividend) and fact.parsed_decimal is not None and (fact.parsed_decimal < 0 or fact.parsed_decimal > 1000000000):
                problems.append('unsupported_dividend_amount' if is_dividend else 'unsupported_interest_amount')
        unresolved.extend({'path': form_path, 'code': code, 'detail': owner['form_name']} for code in dict.fromkeys(problems))
        if not (is_w2 or is_interest or is_dividend):
            continue
        amounts, sources, missing, optional_missing = {}, {}, [], []
        for box, field_id, name in mapped_fields:
            fact = fields.get(field_id)
            if fact is None or fact.unresolved or fact.metadata_kind != 11 or fact.parsed_decimal is None:
                missing.append(box)
                continue
            amounts[name] = str(fact.parsed_decimal)
            field_node = next((i for i, e in enumerate(root[int(form_path.split('/')[0])][int(form_path.split('/')[1])][int(form_path.split('/')[2])])
                if isinstance(e.tag, str) and wire.qname(e.tag)[1] == field_id), None)
            sources[name] = {'wire_text': fact.wire_text, 'field_id': field_id,
                'key': f'{form_path}/{field_node}/0', 'value_flags': dict(fact.raw_value_attrs),
                'specific_flags': {}, 'field_headers': dict(fact.raw_field_attrs)}
        if is_dividend and not missing:
            if Decimal(amounts['qualified']) > Decimal(amounts['ordinary']) or Decimal(amounts['unrecaptured_1250_gain']) + Decimal(amounts['collectibles_gain']) > Decimal(amounts['capital_gain_distributions']):
                unresolved.append({'path': form_path, 'code': 'invalid_dividend_box_subsets', 'detail': 'Boxes 1b, 2b and 2d must fit inside their source totals.'})
        for name, field_id in (() if not is_w2 else (('social_security_tips', 'SSTIPS'), ('dependent_care_benefits', 'DCB'))):
            fact = fields.get(field_id)
            if fact is None or fact.unresolved or fact.metadata_kind != 11 or fact.parsed_decimal is None:
                optional_missing.append(name)
            else:
                amounts[name] = str(fact.parsed_decimal)
        employer = [fields[n].wire_text for n in ('CA', 'CA2') if is_w2 and n in fields and fields[n].metadata_kind == 7]
        candidate_hash = canonical_hash({'owner': owner, 'amounts': amounts, 'sources': sources,
            'employer': employer, 'missing_boxes': missing, 'manual': optional_missing})
        candidates.append({'record_type': 'dividends' if is_dividend else 'interest' if is_interest else 'w2',
            'payer': None, 'employer': ' '.join(employer) or None, 'owner': None, 'amounts': amounts,
            'sources': sources, 'missing_boxes': missing,
            'receipt': {'source_sha256': source_hash, 'wire_profile_sha256': profile_hash,
                'template_carrier_sha256': identity[0], 'template_resource_id': identity[1],
                'form_path': form_path, 'archive_member': archive_member, 'candidate_sha256': candidate_hash},
            'source_owner': owner, 'can_review': False,
            'requires_manual_fields': ['payer', 'supported_dividend_scope', 'qualified_dividend_eligibility'] if is_dividend else ['payer', 'supported_interest_scope'] if is_interest else ['owner', *optional_missing]})
    # An unsupported sibling blocks every candidate, not just that sibling.
    for candidate in candidates:
        candidate['can_review'] = not unresolved and not candidate['missing_boxes']
    result = {'format': 'tax-reborn-taxml-candidates-v1', 'tax_year': 2025,
        'source_sha256': source_hash, 'wire_profile_sha256': profile_hash,
        'root_qname_bound': not document.unresolved, 'candidates': candidates, 'unresolved_facts': unresolved,
        'tax_values_imported': False, 'full_return_imported': False,
        'original_program_acceptance_verified': False,
        'warnings': ['Current Windows XML names and types are inspected with your explicitly bound, byte-validated XPRF registry.',
            'Only supported W-2, 1099-INT or 1099-DIV boxes are offered for review. This is not a complete .tax return import.',
            'Missing amounts never establish zero. Review payer or employer and the supported tax situation explicitly.',
            'Original TurboTax loading and recalculation are unverified. Check the original document before adding a record.']}
    return result, payload, leaves


def inspect_request(request):
    return _inspect(request)[0]


def export_request(request):
    if isinstance(request, dict) and isinstance(request.get('inspection'), dict) and request['inspection'].get('container') == 'binary_entity':
        import binary_tax
        return binary_tax.export_request(request)
    if not isinstance(request, dict) or set(request) != {'inspection', 'expected_candidate_sha256', 'amounts', 'confirmed'}:
        raise ValueError('Invalid corrected XML export request.')
    if request['confirmed'] is not True:
        raise ValueError('Review and confirm the corrected document amounts first.')
    inspected, payload, leaves = _inspect(request['inspection'])
    candidates = [c for c in inspected['candidates'] if c['receipt']['candidate_sha256'] == request['expected_candidate_sha256']]
    if len(candidates) != 1 or not candidates[0]['can_review']:
        raise ValueError('The reviewed candidate is missing, ambiguous or unresolved.')
    candidate = candidates[0]
    amounts = request['amounts']
    names = [name for _, _, name in DIVIDEND_FIELDS] if candidate.get('record_type') == 'dividends' else [name for _, _, name in INTEREST_FIELDS] if candidate.get('record_type') == 'interest' else list(BOX_KEYS.values())
    if not isinstance(amounts, dict) or set(amounts) != set(names):
        raise ValueError('Corrected XML requires exactly the supported source box amounts.')
    edits, normalized = {}, {}
    for name, value in amounts.items():
        if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,13}(?:\.[0-9]{1,2})?', value) or Decimal(value) > 1000000000:
            raise ValueError('Enter nonnegative amounts with at most two decimal places, within the supported limit.')
        normalized[name] = format(Decimal(value), '.2f')
        path = candidate['sources'][name]['key']
        if path not in leaves:
            raise ValueError('The reviewed source field is missing.')
        edits[path] = {**leaves[path], 'replacement': normalized[name]}
    corrected = patch_text_nodes(payload, edits)
    next_request = {**request['inspection'], 'base64': base64.b64encode(corrected).decode(), 'container': 'plaintext_xml'}
    readback = inspect_request(next_request)
    matching = [c for c in readback['candidates'] if c['receipt']['form_path'] == candidate['receipt']['form_path']]
    if len(matching) != 1 or not matching[0]['can_review'] or any(Decimal(matching[0]['amounts'][n]) != Decimal(v) for n, v in normalized.items()):
        raise ValueError('Corrected XML did not pass field readback.')
    if request['inspection']['container'] == 'cleartext_persistence_container':
        import taxml_container
        source = decode_blob(request['inspection']['base64'], 10 * 1024 * 1024)
        output, report = taxml_container.corrected_container(source, candidate['receipt']['archive_member'], corrected)
        full_readback = inspect_request({**request['inspection'], 'base64': base64.b64encode(output).decode()})
        if full_readback['unresolved_facts'] or len(full_readback['candidates']) != len(inspected['candidates']):
            raise ValueError('The complete corrected container failed candidate readback.')
        expected = {c['receipt']['form_path']: c for c in inspected['candidates']}
        for current in full_readback['candidates']:
            original = expected.get(current['receipt']['form_path'])
            if original is None or not current['can_review']:
                raise ValueError('A corrected container candidate changed ownership.')
            wanted = {**original['amounts'], **normalized} if current['receipt']['form_path'] == candidate['receipt']['form_path'] else original['amounts']
            if set(current['amounts']) != set(wanted) or any(Decimal(current['amounts'][key]) != Decimal(value) for key, value in wanted.items()):
                raise ValueError('The complete corrected container changed other source amounts.')
        return {'format': 'tax-reborn-corrected-container-v1', 'base64': base64.b64encode(output).decode(),
            'mime': 'application/zip', 'source_sha256': inspected['source_sha256'],
            'output_sha256': wire.digest(output), 'edited_fields': names,
            'full_return_recalculated': False, 'original_program_acceptance_verified': False,
            'export_container': 'cleartext_persistence_container', 'container_report': report,
            'original_source_retained': True}
    return {'format': 'tax-reborn-corrected-taxml-v1', 'base64': base64.b64encode(corrected).decode(),
        'mime': 'application/xml', 'source_sha256': inspected['source_sha256'],
        'output_sha256': wire.digest(corrected), 'edited_fields': names,
        'full_return_recalculated': False, 'original_program_acceptance_verified': False,
        'export_container': 'plaintext_xml', 'original_source_retained': True}
