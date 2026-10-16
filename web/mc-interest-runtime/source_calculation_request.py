"""Private App candidate: binary current source + reviewed context -> source run.

Callers inject the existing strict App binary loader and numeric adapter. The
request selects a profile ID from trusted App authority; it cannot upload its
own reviewed claims. This module does not read paths, write the source, commit
proposed changes, call the IRS engine, or execute the original application.
"""
import base64
import struct
from dataclasses import asdict, is_dataclass
from decimal import Decimal as D
from source_node_binding_reference import source_node
from hash_structure_reference import validate_document_hashes
import normal_wage_projection_reference as wages
import source_calculation_reference as chain

FORBIDDEN_REVIEW_TARGETS = {
    'F1040': {'L7', 'L8A', 'L8B', 'L9', 'L22', 'L32', 'L33', 'HL39', 'L39', 'TEMPL40A',
        'L40A', 'L40D', 'L40', 'L41', 'ADDLTAX', 'L42', 'L50', 'L51', 'TOTHTX', 'L57', 'L65', 'L69'},
    'FW2SUM': {'TP1A', 'SP1A'}, 'FINFOWKS': {'FS', 'FS2'}}


def _text(value):
    if type(value) is not bytes: raise ValueError('Decoded binary identifiers required')
    return value.rstrip(b' ').decode('ascii').upper()


def _json(value):
    if is_dataclass(value): return _json(asdict(value))
    if isinstance(value, D): return str(value)
    if isinstance(value, dict): return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)): return [_json(item) for item in value]
    return value


def calculate_request(request, *, approved_profiles, binary_loader, amount_decoder):
    """Return JSON-safe proposed results and provenance; no write or commit.

    binary_loader is the already validated App binary_tax._context equivalent.
    amount_decoder is the already reviewed native_amount.decode_amount.
    Their returned Document/profile bindings remain independent prerequisites.
    """
    keys = {'source', 'expected_source_sha256', 'source_profile_id', 'calculation_carriers', 'reviewed_context'}
    if type(request) is not dict or set(request) != keys: raise ValueError('Complete explicit source calculation request required')
    if (type(request['source']) is not dict or type(request['source'].get('profile')) is not dict
            or request['source']['profile'].get('format') not in ('tax-reborn-binary-entity-profile-v1', 'tax-reborn-binary-entity-profile-v2', 'tax-reborn-binary-entity-profile-v3', 'tax-reborn-binary-entity-profile-v4', 'tax-reborn-binary-entity-profile-v5', 'tax-reborn-binary-entity-profile-v6')):
        raise ValueError('Selected source adapter requires explicit reviewed binary profilesv1..v5')
    source_format = request['source']['profile']['format']
    profile_id = request['source_profile_id']
    if type(profile_id) is not str or profile_id not in approved_profiles: raise ValueError('Select an independently approved local calculation profile')
    authority = approved_profiles[profile_id]
    if type(authority) is not dict or set(authority) != {'chain_claim', 'wage_claim'}: raise ValueError('Trusted App profile authority required')
    supplied = request['calculation_carriers']
    if type(supplied) is not list or not 1 <= len(supplied) <= 32: raise ValueError('Complete bounded local calculation resource selection required')
    carriers = []; total_bytes = 0
    for row in supplied:
        if type(row) is not dict or set(row) != {'name', 'base64', 'sha256'}: raise ValueError('Local calculation file bytes and fixed content identity required')
        if type(row['base64']) is not str or len(row['base64']) > 128 * 1024 * 1024: raise ValueError('Calculation resource exceeds selected byte limit')
        try: wire = base64.b64decode(row['base64'], validate=True)
        except Exception as error: raise ValueError('Invalid calculation resource encoding') from error
        total_bytes += len(wire)
        if total_bytes > 192 * 1024 * 1024: raise ValueError('Complete calculation resource selection exceeds finite byte limit')
        carriers.append(chain.CarrierBytes(row['name'], wire, row['sha256']))
    # Authority registry_order and per-record identities, not uploaded row hashes,
    # choose which complete file contents the algorithm is allowed to consume.
    if [row.expected_sha256 for row in carriers] != authority['chain_claim']['registry_order']:
        raise ValueError('Selected local resource files differ from approved fixed identities/order')
    profile = wages.prepare_profile(tuple(carriers), authority['chain_claim'], authority['wage_claim'])
    document, buffers, template_context, registry, selected, source = binary_loader(request['source'])
    hash_validation = validate_document_hashes(document)
    source_hash = chain.sha(source)
    if source_hash != chain._digest(request['expected_source_sha256']): raise ValueError('Source document changed since review')
    review = request['reviewed_context']
    if type(review) is not dict or set(review) != {'acknowledged', 'source_sha256', 'formset_id', 'filing_status', 'prepared_absent_forms', 'fields'}:
        raise ValueError('Explicit limited-context review required')
    if review['acknowledged'] is not True or review['source_sha256'] != source_hash: raise ValueError('Review must bind this exact source document')
    if type(review['formset_id']) is not str or type(review['filing_status']) is not int or not 1 <= review['filing_status'] <= 5:
        raise ValueError('One reviewed source FormSet and filing status required')
    fsid = review['formset_id']
    formsets = [(index, fs) for index, fs in enumerate(document.formsets) if _text(fs.header.identifier) == fsid.upper()]
    if len(formsets) != 1: raise ValueError('One exact caller-profile-bound source FormSet required')
    fsindex, formset = formsets[0]
    owner = source_hash + ':' + str(fsindex)
    by_form, raw_forms = {}, []
    def nested_calculation_form(form):
        return any(_text(child.header.identifier) in (*profile.chain_profile.forms, 'FW2') or nested_calculation_form(child) for child in form.children)
    for index, form in enumerate(formset.forms):
        fid = _text(form.header.identifier)
        if fid == 'FW2': raw_forms.append((index, form))
        if fid in profile.chain_profile.forms:
            if fid in by_form: raise ValueError('Multiple current calculation copies require a new reviewed selector')
            by_form[fid] = index, form
        if nested_calculation_form(form):
            raise ValueError('Nested raw wage copy outside single-level source profile')
    if not raw_forms: raise ValueError('This source calculation requires at least one existing raw FW2 copy')
    prepared = review['prepared_absent_forms']
    if type(prepared) is not list or len(prepared) != len(set(prepared)) or set(prepared) != set(profile.chain_profile.forms) - set(by_form):
        raise ValueError('Review every missing calculation form as prepared absent; no implicit native creation')
    origins, source_trace, current_identities = {}, [], {}

    def node_record(fid, form, field, spec, path):
        # Follow the real hash bucket/next chain. A physically retained orphan
        # is not a current field value merely because its ordinal matches.
        node, binding_audit = source_node(form, spec, path, profile_format=source_format, bound=template_context)
        source_ordinal = binding_audit['source_ordinal']
        retained_matches = [item for buffer in form.hash_state.buffers for item in buffer.nodes
            if source_ordinal is not None and item.field_index == source_ordinal and item.element_index == 0]
        if len(retained_matches) > 1 or node is None and retained_matches:
            raise ValueError('Unreachable or repeated selected source node requires structural review')
        if node is None:
            source_trace.append({'form': fid, 'field': field, 'path': path, 'ordinal': spec.ordinal, 'node': 'absent', **binding_audit})
            return None
        audit = {'form': fid, 'field': field, 'path': path, 'ordinal': spec.ordinal, **binding_audit,
            'kind': node.kind_byte, 'raw64': str(node.raw), 'exponent_byte_retained': node.exponent_byte,
            'value_header': node.header, 'FV_attributes': node.specific_attributes,
            'format_flag10': node.flag10, 'uninterpreted_flag11': node.flag11,
            'document_file_copy_U32': form.header.file_copy, 'runtime_copy_number_U16': form.header.word7c}
        source_trace.append(audit)
        if (node.kind_byte != spec.kind or spec.format != 0 or spec.attributes & 64 or node.header != 0
                or node.flag10 != 0 or node.flag11 != 0 or node.specific_attributes not in chain.ATTRS):
            raise ValueError('Unsupported actual source kind/header/format/flags/attributes; review raw fact')
        if node.kind_byte in (11, 12):
            decoded = amount_decoder(kind_byte=node.kind_byte, raw64=node.raw, exponent_byte=node.exponent_byte,
                fv_attributes=node.specific_attributes, value_header=node.header)
            audit['amount_decode_status'] = decoded.status
            if decoded.status not in ('value', 'unused'): raise ValueError('Source numeric diagnostic/overflow is not a normal amount')
            # Retained storage remains separate from Used. It is bounded by the
            # finite runner even if the general amount adapter can inspect more.
            amount = D(decoded.signed_raw).scaleb(-decoded.scale)
        elif node.kind_byte in (3, 10):
            if node.exponent_byte != 0: raise ValueError('Selected current checkbox/predicate scale required')
            signed = node.raw if node.raw < 1 << 63 else node.raw - (1 << 64)
            if signed not in (0, 1): raise ValueError('Canonical current checkbox/predicate required')
            amount = D(signed)
        elif node.kind_byte == 22 and not node.specific_attributes & 1:
            amount = D(0); audit['unused_opaque_payload_not_interpreted'] = True
        else: raise ValueError('Actual source type needs a separately reviewed converter')
        return chain.Record(node.kind_byte, amount, node.specific_attributes, node.header)

    def check_binary_binding(fid, form, fields):
        key = fsid, fid
        if key not in selected: raise ValueError('Source form lacks an acknowledged binary metadata binding')
        if fid == 'FW2':
            expected = authority['wage_claim']['raw_form']
            expected_identity = expected['carrier_sha256'], expected['resource_id']
        else:
            home = profile.chain_profile.forms[fid][0].primary.source
            expected_identity = home.carrier_key.decode(), home.resource_id
        if selected[key] != expected_identity:
            raise ValueError('Acknowledged source binary template differs from approved calculation primary')
        template = registry.resolve(*key, selected[key])
        binary_fields = {field.field_id: field for field in template.fields}
        for name, spec in fields.items():
            binary = binary_fields.get(name)
            if binary is None or (binary.ordinal, binary.kind, binary.format, binary.is_array) != (spec.ordinal, spec.kind, spec.format, bool(spec.attributes & 64)):
                raise ValueError('Source binary metadata differs from calculation metadata')

    current = []
    for fid, (_, fields) in profile.chain_profile.forms.items():
        records = {field: None for field in fields}
        if fid in by_form:
            index, form = by_form[fid]
            if form.header.parent is not None: raise ValueError('Parentless current calculation form required')
            check_binary_binding(fid, form, fields)
            for field, spec in fields.items():
                # Unsupported unrelated types are not decoded into fake scalar
                # values. Their actual presence blocks this initial adapter.
                records[field] = node_record(fid, form, field, spec, (fsindex, index))
                origins[fid, field] = 'loaded_current_node_or_actual_absence'
            locator = form.header.file_copy
            current_identities[fid] = {'source_present': True, 'document_path': [fsindex, index],
                'document_file_copy_U32': form.header.file_copy, 'runtime_copy_number_U16': form.header.word7c,
                'prepared_absent': False}
        else:
            locator = 0
            for field in fields: origins[fid, field] = 'explicit_reviewed_prepared_absence'
            current_identities[fid] = {'source_present': False, 'document_path': None,
                'document_file_copy_U32': None, 'runtime_copy_number_U16': None, 'prepared_absent': True}
        current.append(chain.CurrentCopy(owner, fid, locator, records))
    if type(review['fields']) is not list: raise ValueError('Explicit reviewed context field list required')
    by_current = {copy.form_id: copy for copy in current}; changed = set()
    for row in review['fields']:
        if type(row) is not dict or set(row) != {'form_id', 'field_id', 'amount', 'reason'} or type(row['reason']) is not str or not row['reason']:
            raise ValueError('Reviewed context field/value/reason required')
        fid, field = row['form_id'], row['field_id']; key = fid, field
        if fid not in by_current or field not in by_current[fid].records or key in changed or field in FORBIDDEN_REVIEW_TARGETS.get(fid, set()):
            raise ValueError('Calculated intermediates and duplicate/unknown reviews are refused')
        changed.add(key); spec = profile.chain_profile.forms[fid][1][field]
        if row['amount'] is None: value = None
        else:
            if type(row['amount']) is not str: raise ValueError('Reviewed amount uses an exact decimal string')
            try: value = chain.Record(spec.kind, D(row['amount']), 1)
            except Exception as error: raise ValueError('Invalid reviewed amount') from error
        chain._checked_record(value, spec)
        by_current[fid].records[field] = value; origins[key] = 'explicit_reviewed_context:' + row['reason']
    # This is a reviewed filing choice, not a claim that the real source FS
    # node has metadata kind1 or that household qualification was recomputed.
    status = review['filing_status']
    for fid, field, record in (('FINFOWKS', 'FS', chain.Record(1, D(status), 1)),
        ('FINFOWKS', 'FS2', chain.Record(3, D(1), 1) if status == 2 else None),
        ('F1040', 'FS2', chain.Record(3, D(1), 1) if status == 2 else None)):
        by_current[fid].records[field] = record; origins[fid, field] = 'explicit_reviewed_filing_status'
    # Payment confirmation concerns an actual input, not a generated total.
    # Even a legitimate source Add(blank, literal0) must not stand in for a
    # reviewed financial input. Enumerate the exact selected payment program's
    # field reads rather than hardcoding a guessed withholding field list.
    local_names = {spec.ordinal: name for name, spec in profile.chain_profile.forms['F1040'][1].items()}
    payment_fields = {local_names[struct.unpack_from('<H', row.payload)[0]]
        for row in profile.chain_profile.programs[13212].instructions if row.opcode == 0x83}
    payment_evidence = []
    for field in sorted(payment_fields):
        record = by_current['F1040'].records[field]
        origin = origins['F1040', field]
        if (record is not None and record.attributes & 1
                and (origin == 'loaded_current_node_or_actual_absence' or origin.startswith('explicit_reviewed_context:'))):
            payment_evidence.append({'form': 'F1040', 'field': field, 'origin': origin, 'amount': record.amount})
    if not payment_evidence:
        raise ValueError('Review a present source payment input, including explicit zero; a generated total cannot confirm blank inputs')
    raw = []
    raw_fields = {name: profile.raw_fields[name] for name in wages.SOURCE_FIELDS}
    for index, form in raw_forms:
        if form.header.parent is not None: raise ValueError('Parentless raw wage copy required')
        check_binary_binding('FW2', form, raw_fields)
        records = {field: node_record('FW2', form, field, spec, (fsindex, index)) for field, spec in raw_fields.items()}
        raw.append(wages.W2Copy(owner, form.header.word7c, records))
    result = wages.calculate(profile, tuple(current), tuple(raw))
    payment = result['current_fields']['F1040']['L65']
    if payment is None or not payment.attributes & 1:
        raise ValueError('Review a present payment/withholding amount, including explicit zero; blank is not zero')
    existing_fields = {(row['form'], row['field']) for row in source_trace if 'kind' in row}
    for row in result['proposed_writes']:
        identity = current_identities[row['form']]
        exists = identity['source_present'] and (row['form'], row['field']) in existing_fields
        row.update(target_origin='loaded_current_node' if exists else 'missing_field_in_loaded_form' if identity['source_present'] else 'explicit_reviewed_prepared_form',
            target_form_exists_in_source=identity['source_present'], target_exists_in_source=bool(exists),
            source_document_path=identity['document_path'], source_runtime_copy_number=identity['runtime_copy_number_U16'],
            can_commit_to_source=False)
    computed = {(row['form'], row['field']) for row in result['current_write_trace'] if row['action'] == 'computed_Used1_even_zero'}
    computed |= {('FW2SUM', row['field']) for row in result['raw_normal_W2_projection']['summary_write_trace'] if row['action'] == 'computed_Used1_even_zero'}
    unresolved = sorted({(row['form'], row['field'], origins.get((row['form'], row['field']), 'unknown'))
        for row in result['current_read_trace'] if (row['form'], row['field']) not in computed and origins.get((row['form'], row['field'])) != 'loaded_current_node_or_actual_absence'})
    return _json({'status': 'proposed_source_calculation', 'source_sha256': source_hash, 'approved_profile_id': profile_id,
        'calculation': result, 'source_field_trace': source_trace,
        'source_payment_input_evidence': payment_evidence,
        'hash_structure_validation': hash_validation,
        'comparison_only': True, 'writeback_allowed': False, 'current_form_identities': current_identities,
        'explicit_reviewed_context': review, 'unclosed_or_reviewed_current_supplies':
            [{'form': fid, 'field': field, 'origin': origin} for fid, field, origin in unresolved],
        'source_modified': False, 'proposed_writes_committed': False, 'IRS_engine_called_or_replaced': False,
        'entire_original_recalculation': False, 'original_runtime': 0, 'original_saved_return_fixture': 0,
        'limitations': ['Normal-wage source dependency projection plus manually scheduled R2 programs; not fullFW2SUM/native queue.',
            'Derivedv4 reads complete saved field IDs through a static binding view; native FixupFields/conversion and current cache construction are not executed.',
            'Missing current forms are explicitly reviewed prepared absences, not proven native factory objects.',
            'Raw INT/DIV aggregation, deductions/eligibility/other input producers and native global recalculation remain unclosed.',
            'Filing review creates owned parameter facts; actual source FS enum node conversion remains outside this adapter.',
            'This finite adapter refuses unsupported actual node/header/format/flags/types; it does not reinterpret them.']})
