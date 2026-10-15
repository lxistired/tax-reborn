"""Reviewed monetary Mac TaxML sources; stored copies, not native inventory.

One verified complete resource registration supplies every name/kind/CID.
The profile separately binds expected FormSet headers. Source copy headers
remain stored facts. Only explicitly cleartext documents may be edited.
"""
import base64
import re
import uuid
from decimal import Decimal

import taxml_wire as wire
from interop.form_core import effective_registry_fields_reference as core
from interop.form_core import native_taxml_names_reference as names
from interop.form_core import native_mac_taxml_money_reference as money

PROFILE = 'tax-reborn-taxml-native-mac-profile-v1'
SCALAR_PROFILE = 'tax-reborn-taxml-native-mac-profile-v2'
DATE_PROFILE = 'tax-reborn-taxml-native-mac-profile-v3'
HEADERS = {'checksum', 'dataVersion', 'sharedForAllDataVersion',
           'sharedForFSDataVersion', 'formsetAttribute', 'showSmartWorksheets',
           'implementationVersion'}
REQUIRED_HEADERS = {'checksum', 'dataVersion', 'formsetAttribute',
                    'showSmartWorksheets', 'implementationVersion'}


def is_request(request):
    return (isinstance(request, dict) and isinstance(request.get('profile'), dict)
            and request['profile'].get('format') in (PROFILE, SCALAR_PROFILE, DATE_PROFILE))


def _uuid(value):
    # This validates syntax only. It does not certify original RecordUUID or
    # equate the stored source identity with a live native instance.
    try:
        if not isinstance(value, str) or str(uuid.UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError):
        raise ValueError('An exact lowercase stored UUID is required.') from None


def _context(request):
    from taxml_preparation import decode_blob, HASH
    if not isinstance(request, dict) or set(request) != {
            'base64', 'container', 'profile', 'carriers', 'profile_acknowledged'}:
        raise ValueError('Invalid Mac TaxML inspection request.')
    if request['profile_acknowledged'] is not True:
        raise ValueError('Review and acknowledge the selected Mac source profile.')
    profile = request['profile']
    keys = {'format', 'tax_year', 'registry_order', 'entity_name', 'formsets'}
    if isinstance(profile, dict) and profile.get('format') in (SCALAR_PROFILE, DATE_PROFILE):
        keys.add('filter_profile')
    if not isinstance(profile, dict) or set(profile) != keys:
        raise ValueError('Invalid Mac TaxML profile.')
    if profile['format'] not in (PROFILE, SCALAR_PROFILE, DATE_PROFILE) or type(profile['tax_year']) is not int or profile['tax_year'] != 2025:
        raise ValueError('Only the explicitly bound 2025 Mac TaxML profile is supported.')
    filter_profile = profile.get('filter_profile', 'null_filter')
    if type(filter_profile) is not str or filter_profile not in ('null_filter', 'controller_filter'):
        raise ValueError('Choose an explicit null_filter or controller_filter source mode.')
    if profile['entity_name'] != 'USIndividualTaxReturn':
        raise ValueError('Only the selected individual-return source envelope is supported.')
    supplied = request['carriers']
    order = profile['registry_order']
    if not isinstance(supplied, list) or not 1 <= len(supplied) <= 8:
        raise ValueError('Choose 1 to 8 complete caller-owned XPRF files.')
    if not isinstance(order, list) or len(order) != len(supplied) or any(
            not isinstance(s, str) or not HASH.fullmatch(s) for s in order) or len(set(order)) != len(order):
        raise ValueError('The profile must bind each carrier exactly once in explicit order.')
    carriers = {}
    for supplied_carrier in supplied:
        if not isinstance(supplied_carrier, dict) or set(supplied_carrier) != {'base64', 'sha256'}:
            raise ValueError('Every complete carrier needs its SHA-256 identity.')
        sha = supplied_carrier['sha256']
        if not isinstance(sha, str) or not HASH.fullmatch(sha) or sha in carriers:
            raise ValueError('Invalid or duplicate carrier identity.')
        blob = decode_blob(supplied_carrier['base64'], 32 * 1024 * 1024)
        carriers[sha] = core.Carrier(bytes.fromhex(sha), wire.read_xprf_resources(blob, sha))
    if set(carriers) != set(order):
        raise ValueError('Profile carrier identities differ from the complete source files.')
    registry = core.register_records(tuple(carriers[sha] for sha in order))
    selected = profile['formsets']
    if not isinstance(selected, list) or not 1 <= len(selected) <= 8:
        raise ValueError('Bind the expected source FormSet headers explicitly.')
    profiles = {}
    for item in selected:
        if not isinstance(item, dict) or set(item) != {'formset_id', 'expected_headers', 'forms'}:
            raise ValueError('Invalid Mac source FormSet binding.')
        identifier = item['formset_id']
        if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]{0,31}', identifier):
            raise ValueError('An exact ordinary full FormSet ID is required.')
        matches = [fs for fs in registry.formsets if fs.identifier == core.fixed_id(identifier.encode('ascii'))]
        if len(matches) != 1:
            raise ValueError('The complete registry did not uniquely supply the FormSet.')
        fs = matches[0]
        fsnames = names.formset_names(registry, fs)
        qname = fsnames.namespace + ' ' + fsnames.element_name
        if qname in profiles:
            raise ValueError('Ambiguous Mac source FormSet XML name.')
        expected = item['expected_headers']
        if not isinstance(expected, dict) or not REQUIRED_HEADERS <= expected.keys() or not expected.keys() <= HEADERS or any(
                not isinstance(v, str) or '\0' in v for v in expected.values()):
            raise ValueError('Bind exact expected FormSet headers, including the checksum; do not infer them from XML.')
        wanted = item['forms']
        if not isinstance(wanted, list) or not wanted or len(wanted) > 3 or any(
                not isinstance(f, str) or f not in ('FW2', 'F1099I', 'F1099D') for f in wanted) or len(set(wanted)) != len(wanted):
            raise ValueError('Only explicit W-2, 1099-INT and 1099-DIV source forms are supported.')
        forms = {}
        for token in wanted:
            matches = [f for f in fs.forms if f.identifier == core.fixed_id(token.encode('ascii'))]
            if len(matches) != 1:
                raise ValueError('A selected source form is missing or ambiguous.')
            form = matches[0]
            template, _ = core.field_template(registry, form)
            fields = {}
            for field in template.fields:
                label = names.ordinary_xml_id(field.identifier)
                if label in fields:
                    raise ValueError('Ambiguous complete field identity in selected metadata.')
                fields[label] = field
            forms[token] = (form, fields)
        profiles[qname] = (fs, fsnames, expected, forms)
    data = decode_blob(request['base64'], 10 * 1024 * 1024)
    report = None
    member = None
    if request['container'] == 'plaintext_xml':
        payload = data
    elif request['container'] == 'cleartext_persistence_container':
        import taxml_container
        payload, member, report = taxml_container.inspect_source(data)
    else:
        raise ValueError('Choose plaintext XML or an explicitly cleartext persistence container.')
    # Preserve comments outside value text, but do not silently execute or
    # normalize processing instructions in this finite source-edit profile.
    text = payload.decode('utf-8-sig')
    if re.search(r'<\?(?!xml\s)', text):
        raise ValueError('Processing instructions are outside this finite source profile.')
    root = money._parse(payload)
    contexts = []
    for entity in root.children:
        local = profile['entity_name']
        if entity.name != names.BASE_URL + local + ' ' + local or entity.attrs.get('taxYear') != '2025':
            raise ValueError('The stored entity name or tax year differs from the selected profile.')
        _uuid(entity.attrs.get('uuid'))
        sets = []
        for fsnode in entity.children:
            if fsnode.name not in profiles:
                raise ValueError('An unbound source FormSet remains in the document.')
            fs, fsnames, expected, forms = profiles[fsnode.name]
            stored_headers = {k: v for k, v in fsnode.attrs.items()
                              if k not in ('tpsType', 'tpsPrefix', 'cidFormSet', 'uuid')}
            if stored_headers != expected:
                raise ValueError('Stored FormSet headers differ from the independently selected profile.')
            if 'uuid' in fsnode.attrs:
                _uuid(fsnode.attrs['uuid'])
            copies = []
            for formnode in fsnode.children:
                prefix = fsnames.namespace + ' '
                local = formnode.name.removeprefix(prefix)
                if formnode.name != prefix + local or local not in forms:
                    raise ValueError('An unbound form or namespace remains in the source.')
                form, fields = forms[local]
                attrs = {k: v for k, v in formnode.attrs.items() if k != 'tpsType'}
                if 'uuid' in attrs:
                    _uuid(attrs['uuid'])
                # Current factory/default-copy decisions have not been run.
                # Only an explicit nonzero stored copy is offered for review.
                if attrs.get('copyNum') in (None, '0'):
                    raise ValueError('A nonzero explicit stored copyNum is required; native factory acceptance is unverified.')
                present = []
                for fieldnode in formnode.children:
                    label = fieldnode.name.removeprefix(prefix)
                    if fieldnode.name != prefix + label or label not in fields:
                        raise ValueError('An unbound full field ID or namespace remains in the source.')
                    if profile['format'] == PROFILE and fields[label].kind == 13:
                        raise ValueError('Decimal source fields require the explicit Mac scalar v2 profile.')
                    if fields[label].kind in (4, 5, 6) and profile['format'] != DATE_PROFILE:
                        raise ValueError('Date source fields require the explicit Mac source v3 profile.')
                    if fields[label].attributes != 0:
                        raise ValueError('Nonordinary compiled field attributes require separate semantics.')
                    present.append(fields[label].identifier)
                copies.append(money.FormContext(form, tuple(attrs.items()), tuple(present)))
            header_pairs = tuple((k, v) for k, v in fsnode.attrs.items()
                                 if k not in ('tpsType', 'tpsPrefix', 'cidFormSet'))
            sets.append(money.FormSetContext(fs, header_pairs, tuple(copies)))
        contexts.append(money.EntityContext(profile['entity_name'], tuple(entity.attrs.items()), tuple(sets)))
    document = money.load_money_document(payload, registry, tuple(contexts), filter_profile=filter_profile)
    return data, payload, member, report, registry, document


def inspect_context(request):
    from taxml_preparation import (canonical_hash, BOX_KEYS, INTEREST_FIELDS,
                                  DIVIDEND_FIELDS, _attach_container_scope)
    source, payload, member, report, registry, document = _context(request)
    source_sha, profile_sha = wire.digest(source), canonical_hash(request['profile'])
    unresolved, candidates, groups, inventory = [], [], {}, {}
    for ei, entity in enumerate(document.contexts):
        entity_uuid = dict(entity.attributes)['uuid']
        for si, fs in enumerate(entity.formsets):
            for fi, form in enumerate(fs.forms):
                attrs = dict(form.attributes)
                identity = (entity_uuid, fs.compiled_formset.identifier,
                            form.compiled_form.identifier, int(attrs['fileCopyNum']))
                inventory[identity] = (f'{ei}/{si}/{fi}', attrs, form.compiled_form)
                groups[identity] = []
    for field in document.fields:
        if request['profile']['format'] in (SCALAR_PROFILE, DATE_PROFILE) and field.kind in (4, 5, 6, 13):
            continue  # Known stored decimal facts stay outside income amounts.
        groups.setdefault(field.key[:4], []).append(field)
    for identity, fields in groups.items():
        entity_uuid, fsid, fid, copy = identity
        form_name = names.ordinary_xml_id(fid)
        mapped = (INTEREST_FIELDS if form_name == 'F1099I' else DIVIDEND_FIELDS
                  if form_name == 'F1099D' else tuple((box, field, BOX_KEYS[box]) for box, field in (
                      (1, 'WAGES'), (2, 'FEDTAX'), (3, 'SSWAGES'), (4, 'SSTAX'), (5, 'MEDWAGES'), (6, 'MEDTAX'))))
        by_id = {names.ordinary_xml_id(f.key[4]): f for f in fields}
        allowed = {field for _, field, _ in mapped}
        optional = {'SSTIPS': 'social_security_tips', 'DCB': 'dependent_care_benefits'} if form_name == 'FW2' else {}
        problems = []
        for label, field in by_id.items():
            if label not in allowed | optional.keys():
                problems.append('unmapped_source_fact')
            if field.kind != 11 or not field.can_edit or field.unresolved or field.amount < 0:
                problems.append('unsupported_or_unused_source_amount')
        amounts, sources, missing = {}, {}, []
        form_path, stored_form_headers, compiled_form = inventory[identity]
        for box, label, name in mapped:
            field = by_id.get(label)
            if field is None or field.kind != 11 or not field.can_edit or field.unresolved or field.amount < 0:
                missing.append(box)
            else:
                amounts[name] = format(field.amount, '.2f')
                sources[name] = {'wire_text': field.text, 'field_id': label,
                                 'key': [entity_uuid, fsid.hex(), fid.hex(), copy, field.key[4].hex()],
                                 'current_ordinal': field.current_ordinal,
                                 'value_flags': dict(field.value_attributes),
                                 'specific_flags': {}, 'field_headers': dict(field.attributes)}
        optional_missing = []
        for label, name in optional.items():
            if label in by_id and by_id[label].can_edit and by_id[label].kind == 11:
                amounts[name] = format(by_id[label].amount, '.2f')
            else:
                optional_missing.append(name)
        if form_name == 'F1099D' and not missing and (
                Decimal(amounts['qualified']) > Decimal(amounts['ordinary']) or
                Decimal(amounts['unrecaptured_1250_gain']) + Decimal(amounts['collectibles_gain']) > Decimal(amounts['capital_gain_distributions'])):
            problems.append('invalid_dividend_box_subsets')
        unresolved.extend({'path': form_path, 'code': p, 'detail': form_name} for p in dict.fromkeys(problems))
        first = fields[0].field_metadata_source if fields else compiled_form.homes[0].source
        owner = {'entity_uuid': entity_uuid, 'formset_name': names.ordinary_xml_id(fsid),
                 'form_name': form_name, 'fileCopyNum': str(copy),
                 'copyNum': stored_form_headers['copyNum'], 'porIndex': stored_form_headers['porIndex']}
        candidates.append({'record_type': 'interest' if form_name == 'F1099I' else 'dividends' if form_name == 'F1099D' else 'w2',
            'payer': None, 'employer': None, 'owner': None, 'amounts': amounts, 'sources': sources,
            'missing_boxes': missing, 'source_owner': owner, 'can_review': False,
            'receipt': {'source_sha256': source_sha, 'wire_profile_sha256': profile_sha,
                        'template_carrier_sha256': first.carrier_key.hex(), 'template_resource_id': first.resource_id,
                        'form_path': form_path, 'archive_member': member,
                        'candidate_sha256': canonical_hash({'source_sha256': source_sha,
                            'wire_profile_sha256': profile_sha, 'owner': owner,
                            'fields': sources, 'amounts': amounts, 'missing': missing})},
            'requires_manual_fields': ['payer', 'supported_interest_scope'] if form_name == 'F1099I' else
                ['payer', 'supported_dividend_scope', 'qualified_dividend_eligibility'] if form_name == 'F1099D' else
                ['owner', 'employer', *optional_missing]})
    for candidate in candidates:
        candidate['can_review'] = not unresolved and not candidate['missing_boxes']
    result = {'format': 'tax-reborn-taxml-candidates-v1', 'tax_year': 2025,
        'source_sha256': source_sha, 'wire_profile_sha256': profile_sha,
        'root_qname_bound': True, 'candidates': candidates, 'unresolved_facts': unresolved,
        'tax_values_imported': False, 'full_return_imported': False,
        'original_program_acceptance_verified': False,
        'source_inventory': 'stored XML entities and copies; not a native current inventory',
        'warnings': ['Mac monetary XML names, kinds and CID data come from the same complete caller-owned XPRF registration.',
            'Source entities and copies are stored facts. Native form factories, defaults and recalculation are unverified.',
            'Review only the supported W-2, 1099-INT and 1099-DIV boxes. Enter owner and employer or payer explicitly.',
            'Unknown objects, flags or source amounts block review. Missing amounts never establish zero.']}
    _attach_container_scope(result, report)
    if request['profile']['format'] in (SCALAR_PROFILE, DATE_PROFILE):
        from interop.form_core.native_taxml_decimal_reference import parse_dec1
        result['source_filter_profile'] = document.filter_profile
        result['scalar_fields'] = []
        for field in document.fields:
            if field.kind != 13:
                continue
            key = [field.key[0], field.key[1].hex(), field.key[2].hex(), field.key[3], field.key[4].hex()]
            fact = {'key': key, 'field_id': names.ordinary_xml_id(field.key[4]),
                'form_id': names.ordinary_xml_id(field.key[2]), 'file_copy': field.key[3],
                'entity_uuid': field.key[0], 'current_ordinal': field.current_ordinal,
                'kind': 13, 'number_kind': 'decimal_coefficient', 'fraction_digits': 1,
                'text': field.text, 'coefficient': str(parse_dec1(field.text)),
                'attributes': dict(field.attributes), 'value_attributes': dict(field.value_attributes),
                'field_metadata_source': {'carrier_sha256': field.field_metadata_source.carrier_key.hex(),
                    'resource_id': field.field_metadata_source.resource_id, 'metadata_type': field.field_metadata_source.metadata_type},
                'mapping_source': field.mapping_source, 'can_review': False,
                'can_edit_source': bool(field.can_edit and not field.unresolved and not result['unresolved_facts']
                    and (report is None or report['manifest_metadata_edit_authorized']))}
            fact['receipt'] = {'source_sha256': source_sha, 'wire_profile_sha256': profile_sha,
                'field_sha256': canonical_hash({'source_sha256': source_sha, 'profile_sha256': profile_sha,
                    'key': key, 'ordinal': field.current_ordinal, 'kind': field.kind, 'text': field.text,
                    'attributes': fact['attributes'], 'value_attributes': fact['value_attributes']})}
            result['scalar_fields'].append(fact)
        result['warnings'].append('Decimal source fields are stored coefficients with one fractional digit. They are not imported as money or used in the App tax calculation.')
    if request['profile']['format'] == DATE_PROFILE:
        result['date_fields'] = []
        for field in document.fields:
            if field.kind not in (4, 5, 6):
                continue
            key = [field.key[0], field.key[1].hex(), field.key[2].hex(), field.key[3], field.key[4].hex()]
            fact = {'key': key, 'field_id': names.ordinary_xml_id(field.key[4]),
                'form_id': names.ordinary_xml_id(field.key[2]), 'file_copy': field.key[3],
                'entity_uuid': field.key[0], 'current_ordinal': field.current_ordinal,
                'kind': field.kind, 'text_kind': {4: 'date', 5: 'day', 6: 'month'}[field.kind],
                'text_format': {4: 'MM/DD/YYYY', 5: 'MM-DD', 6: 'YYYY-MM'}[field.kind],
                'text': field.text, 'attributes': dict(field.attributes),
                'value_attributes': dict(field.value_attributes),
                'field_metadata_source': {'carrier_sha256': field.field_metadata_source.carrier_key.hex(),
                    'resource_id': field.field_metadata_source.resource_id, 'metadata_type': field.field_metadata_source.metadata_type},
                'mapping_source': field.mapping_source, 'can_review': False,
                'can_edit_source': bool(field.can_edit and not field.unresolved and not result['unresolved_facts']
                    and (report is None or report['manifest_metadata_edit_authorized']))}
            fact['receipt'] = {'source_sha256': source_sha, 'wire_profile_sha256': profile_sha,
                'field_sha256': canonical_hash({'source_sha256': source_sha, 'profile_sha256': profile_sha,
                    'key': key, 'ordinal': field.current_ordinal, 'kind': field.kind, 'text': field.text,
                    'attributes': fact['attributes'], 'value_attributes': fact['value_attributes']})}
            result['date_fields'].append(fact)
        result['warnings'].append('Date, day and month source fields remain separate from money and the current return. A corrected source copy does not verify original-program loading or recalculation.')
    return result, payload, document


def inspect_request(request):
    return inspect_context(request)[0]


def export_request(request):
    if isinstance(request, dict) and 'expected_date_sha256' in request:
        return export_date_request(request)
    if isinstance(request, dict) and 'expected_scalar_sha256' in request:
        return export_scalar_request(request)
    from taxml_preparation import decode_blob, BOX_KEYS, INTEREST_FIELDS, DIVIDEND_FIELDS
    if not isinstance(request, dict) or set(request) != {'inspection', 'expected_candidate_sha256', 'amounts', 'confirmed'} or request['confirmed'] is not True:
        raise ValueError('Review and confirm the exact corrected Mac source amounts first.')
    inspected, payload, document = inspect_context(request['inspection'])
    matches = [c for c in inspected['candidates'] if c['receipt']['candidate_sha256'] == request['expected_candidate_sha256']]
    if len(matches) != 1 or not matches[0]['can_review']:
        raise ValueError('The reviewed Mac source candidate is missing, stale or unresolved.')
    candidate = matches[0]
    fields = INTEREST_FIELDS if candidate['record_type'] == 'interest' else DIVIDEND_FIELDS if candidate['record_type'] == 'dividends' else tuple((b, '', n) for b, n in BOX_KEYS.items())
    wanted = [name for _, _, name in fields]
    amounts = request['amounts']
    if not isinstance(amounts, dict) or set(amounts) != set(wanted):
        raise ValueError('Correct exactly the supported existing source box amounts.')
    normalized = {}
    for name in wanted:
        value = amounts[name]
        if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,13}(?:\.[0-9]{1,2})?', value) or Decimal(value) > 1000000000:
            raise ValueError('Enter nonnegative source amounts with at most two decimal places, within the supported limit.')
        normalized[name] = format(Decimal(value), '.2f')
        encoded = candidate['sources'][name]['key']
        key = (encoded[0], bytes.fromhex(encoded[1]), bytes.fromhex(encoded[2]), encoded[3], bytes.fromhex(encoded[4]))
        payload, document = money.patch_money_document(document, key, int(Decimal(value) * 100))
    check = inspect_request({**request['inspection'], 'container': 'plaintext_xml', 'base64': base64.b64encode(payload).decode()})
    previous = {c['receipt']['form_path']: c for c in inspected['candidates']}
    def verify(readback):
        if readback['unresolved_facts'] or len(readback['candidates']) != len(previous):
            raise ValueError('The complete corrected Mac document failed readback.')
        for c in readback['candidates']:
            old = previous.get(c['receipt']['form_path'])
            if old is None or not c['can_review'] or old['source_owner'] != c['source_owner']:
                raise ValueError('A corrected source candidate changed ownership.')
            expected = {**old['amounts'], **normalized} if c['receipt']['form_path'] == candidate['receipt']['form_path'] else old['amounts']
            if c['amounts'] != expected:
                raise ValueError('Complete source readback changed another amount.')
    verify(check)
    report = None
    output, export_container, mime = payload, 'plaintext_xml', 'application/xml'
    if request['inspection']['container'] == 'cleartext_persistence_container':
        import taxml_container
        original = decode_blob(request['inspection']['base64'], 10 * 1024 * 1024)
        output, report = taxml_container.corrected_container(original, candidate['receipt']['archive_member'], payload)
        verify(inspect_request({**request['inspection'], 'base64': base64.b64encode(output).decode()}))
        export_container, mime = 'cleartext_persistence_container', 'application/zip'
    result = {'format': 'tax-reborn-corrected-container-v1' if report else 'tax-reborn-corrected-taxml-v1',
        'base64': base64.b64encode(output).decode(), 'mime': mime,
        'source_sha256': inspected['source_sha256'], 'output_sha256': wire.digest(output),
        'edited_fields': wanted, 'full_return_recalculated': False,
        'original_program_acceptance_verified': False,
        'export_container': export_container, 'original_source_retained': True}
    if report is not None:
        result['container_report'] = report
    return result


def export_scalar_request(request):
    """One existing dec1 text value, whole-source preservation and full readback."""
    from taxml_preparation import decode_blob
    from interop.form_core.native_taxml_decimal_reference import parse_dec1
    if not isinstance(request, dict) or set(request) != {'inspection', 'expected_scalar_sha256', 'value', 'confirmed'} or request['confirmed'] is not True:
        raise ValueError('Review and confirm the exact decimal source field first.')
    inspection = request['inspection']
    if not is_request(inspection) or inspection['profile']['format'] not in (SCALAR_PROFILE, DATE_PROFILE):
        raise ValueError('Decimal source edits require the explicit Mac scalar v2 profile.')
    result, payload, document = inspect_context(inspection)
    matches = [f for f in result['scalar_fields'] if f['receipt']['field_sha256'] == request['expected_scalar_sha256']]
    if len(matches) != 1 or not matches[0]['can_edit_source']:
        raise ValueError('The decimal source field is stale, read only or unresolved.')
    selected = matches[0]
    coefficient = parse_dec1(request['value'])
    encoded = selected['key']
    key = (encoded[0], bytes.fromhex(encoded[1]), bytes.fromhex(encoded[2]), encoded[3], bytes.fromhex(encoded[4]))
    before = [(f.key, f.current_ordinal, f.kind, f.text, f.attributes, f.value_attributes) for f in document.fields]
    payload, corrected = money.patch_money_document(document, key, coefficient)
    expected = [(k, o, t, request['value'] if k == key else text, a, v) for k, o, t, text, a, v in before]
    def verify(loaded):
        actual = [(f.key, f.current_ordinal, f.kind, f.text, f.attributes, f.value_attributes) for f in loaded.fields]
        if actual != expected:
            raise ValueError('Complete source readback changed another field or stored identity.')
    verify(corrected)
    output, container, mime, report = payload, 'plaintext_xml', 'application/xml', None
    if inspection['container'] == 'cleartext_persistence_container':
        import taxml_container
        original = decode_blob(inspection['base64'], 10 * 1024 * 1024)
        output, report = taxml_container.corrected_container(original, result['container_report']['selected_taxml_member'], payload)
        _, _, _, _, _, reopened = _context({**inspection, 'base64': base64.b64encode(output).decode()})
        verify(reopened)
        container, mime = 'cleartext_persistence_container', 'application/zip'
    return {'format': 'tax-reborn-corrected-container-v1' if report else 'tax-reborn-corrected-taxml-v1',
        'base64': base64.b64encode(output).decode(), 'mime': mime,
        'source_sha256': result['source_sha256'], 'output_sha256': wire.digest(output),
        'edited_fields': [selected['field_id']], 'edited_scalar_key': selected['key'],
        'number_kind': 'decimal_coefficient', 'fraction_digits': 1,
        'full_return_recalculated': False, 'tax_values_imported': False,
        'original_program_acceptance_verified': False, 'export_container': container,
        'original_source_retained': True, **({'container_report': report} if report is not None else {})}


def export_date_request(request):
    """Correct one bound source date, preserving all other parsed and ZIP facts.

    This edits serialized source text. Native date loading, default StringTable
    allocation, SetValue, callbacks and tax recalculation are not executed.
    """
    from taxml_preparation import decode_blob
    from interop.form_core.native_taxml_date_reference import patch_date_document
    if not isinstance(request, dict) or set(request) != {'inspection', 'expected_date_sha256', 'value', 'confirmed'} or request['confirmed'] is not True:
        raise ValueError('Review and confirm the exact date source field first.')
    inspection = request['inspection']
    if not is_request(inspection) or inspection['profile']['format'] != DATE_PROFILE:
        raise ValueError('Date source edits require the explicit Mac source v3 profile.')
    result, payload, document = inspect_context(inspection)
    matches = [f for f in result['date_fields'] if f['receipt']['field_sha256'] == request['expected_date_sha256']]
    if len(matches) != 1 or not matches[0]['can_edit_source']:
        raise ValueError('The date source field is stale, read only or unresolved.')
    selected = matches[0]
    encoded = selected['key']
    key = (encoded[0], bytes.fromhex(encoded[1]), bytes.fromhex(encoded[2]), encoded[3], bytes.fromhex(encoded[4]))
    before = [(f.key, f.current_ordinal, f.kind, f.text, f.attributes, f.value_attributes) for f in document.fields]
    payload, corrected = patch_date_document(document, key, request['value'])
    expected = [(k, o, t, request['value'] if k == key else text, a, v) for k, o, t, text, a, v in before]
    def verify(loaded):
        actual = [(f.key, f.current_ordinal, f.kind, f.text, f.attributes, f.value_attributes) for f in loaded.fields]
        if actual != expected:
            raise ValueError('Complete source readback changed another field or stored identity.')
    verify(corrected)
    output, container, mime, report = payload, 'plaintext_xml', 'application/xml', None
    if inspection['container'] == 'cleartext_persistence_container':
        import taxml_container
        original = decode_blob(inspection['base64'], 10 * 1024 * 1024)
        output, report = taxml_container.corrected_container(original, result['container_report']['selected_taxml_member'], payload)
        _, _, _, _, _, reopened = _context({**inspection, 'base64': base64.b64encode(output).decode()})
        verify(reopened)
        container, mime = 'cleartext_persistence_container', 'application/zip'
    return {'format': 'tax-reborn-corrected-container-v1' if report else 'tax-reborn-corrected-taxml-v1',
        'base64': base64.b64encode(output).decode(), 'mime': mime,
        'source_sha256': result['source_sha256'], 'output_sha256': wire.digest(output),
        'edited_fields': [selected['field_id']], 'edited_date_key': selected['key'],
        'text_kind': selected['text_kind'], 'text_format': selected['text_format'],
        'full_return_recalculated': False, 'tax_values_imported': False,
        'original_program_acceptance_verified': False, 'native_date_load_executed': False,
        'export_container': container, 'original_source_retained': True,
        **({'container_report': report} if report is not None else {})}
