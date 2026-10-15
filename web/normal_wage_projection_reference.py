"""Independent finite normal-W2 wage dependency projection and source join.

This is an algorithm projection of the reviewed TP1A/SP1A dependency cone,
not an interpreter for the entire wage-summary section. Complete local
resource bytes/hashes/metadata are checked before the selected algorithm is
enabled. Trust in the reviewed algorithm/profile remains external authority.
No vendor bytes, filesystem/network I/O, native copy inventory or scheduler.
"""
from dataclasses import dataclass, replace
from decimal import Decimal as D
from types import MappingProxyType
import struct
import source_calculation_reference as chain

SOURCE_FIELDS = {'SPBX': 3, 'WAGES': 11, '__POR__': 10, 'STATX': 3,
    'NOTSTEMP': 3, 'STATLC': 22, 'INMATEX': 3, 'NQPLANS': 11}
SPECIAL_PRESENCE = ('STATX', 'NOTSTEMP', 'STATLC', 'INMATEX')


@dataclass(frozen=True)
class W2Copy:
    owner: str
    runtime_copy_number: int
    records: dict


@dataclass(frozen=True)
class WageProfile:
    chain_profile: object
    raw_fields: object
    program_binding: object


def prepare_profile(carriers, chain_claim, wage_claim):
    prepared = chain.prepare_profile(carriers, chain_claim)
    indexed = {carrier.expected_sha256: chain.index_carrier(carrier) for carrier in carriers}
    registry = chain.registry_reader.register_records(tuple(chain.registry_reader.Carrier(carrier.expected_sha256.encode(), indexed[carrier.expected_sha256][0]) for carrier in carriers))
    fid = wage_claim['raw_form']; candidates = [(fs, form) for fs in registry.formsets for form in fs.forms
        if chain._token(form.identifier) == 'FW2' and chain._token(fs.identifier) == fid['formset_id']]
    if len(candidates) != 1: raise ValueError('Unique effective selected raw wage form required')
    _, form = candidates[0]; home = form.primary.source
    if (home.carrier_key.decode(), home.resource_id) != (fid['carrier_sha256'], fid['resource_id']):
        raise ValueError('Raw wage effective primary differs from reviewed identity')
    template, _ = chain.registry_reader.field_template(registry, form)
    fields = {chain._token(field.identifier): field for field in template.fields}
    for field, kind in SOURCE_FIELDS.items():
        declared = fields.get(field)
        if declared is None or (declared.kind, declared.format) != (kind, 0) or declared.attributes & 64:
            raise ValueError('Reviewed exact raw wage scalar/presence metadata required')
    for field in ('TP1A', 'SP1A'):
        declared = prepared.forms['FW2SUM'][1][field]
        if (declared.kind, declared.format) != (12, 0) or declared.attributes & 64:
            raise ValueError('Reviewed whole wage summary targets required')
    for fid in ('F1040', 'FINFOWKS'):
        declared = prepared.forms[fid][1]['FS2']
        if (declared.kind, declared.format) != (3, 0): raise ValueError('Current filing checkbox presence metadata required')
    expected = wage_claim['summary_program']; selected = None
    for home in prepared.forms['FW2SUM'][0].homes:
        digest = home.source.carrier_key.decode(); key = (13000, home.source.resource_id)
        if key in indexed[digest][1]: selected = digest, key; break
    if selected is None: raise ValueError('Complete effective wage summary program required')
    digest, key = selected; frame = indexed[digest][1][key]; body = frame[10:]
    if (digest, key[1], chain.sha(frame)) != (expected['carrier_sha256'], expected['resource_id'], expected['record_sha256']):
        raise ValueError('Wage algorithm source differs from trusted reviewed full-frame SHA')
    if len(body) < 11: raise ValueError('Complete wage program header required')
    header, length, variables, arrays, returned, params = struct.unpack_from('<HHHHBH', body)
    if header != 11 + variables + 6 * arrays + params or header + length != len(body): raise ValueError('Complete wage header/body required')
    local_types = body[11:11 + variables]
    array_data = tuple(struct.unpack_from('<HHH', body, 11 + variables + 6 * index) for index in range(arrays))
    if variables <= 135 or any(local_types[index] != kind for index, kind in ((12, 10), (17, 10), (19, 10), (123, 12), (135, 10), (105, 12))) or (105, 2, 0) not in array_data:
        raise ValueError('Selected typed wage locals/fixed array105 capacity2 required')
    binding = {'carrier_sha256': digest, 'resource_id': key[1], 'type': 13000, 'record_sha256': chain.sha(frame),
        'body_sha256': chain.sha(body), 'header': header, 'locals': variables, 'arrays': arrays,
        'execution_scope': 'reviewed normal wage dependency algorithm; entire source section not executed'}
    return WageProfile(prepared, MappingProxyType(fields), MappingProxyType(binding))


def _present(record, kind):
    if record is None: return None
    if (not isinstance(record, chain.Record) or type(record.kind) is not int or record.kind != kind
            or type(record.attributes) is not int or record.attributes not in chain.ATTRS or record.header != 0):
        raise ValueError('Explicit matching current native storage and finite attrs required')
    # Unused payload, including an opaque link, is not interpreted as a value.
    if not record.attributes & 1: return None
    if kind == 22: raise ValueError('Present raw link/classifier branch is outside normal wage projection')
    value = record.amount
    if type(value) is not D or not value.is_finite() or abs(value) > 10**9: raise ValueError('Finite selected raw wage scalar required')
    if kind in (3, 10) and value not in (D(0), D(1)): raise ValueError('Canonical current checkbox/predicate required')
    if kind == 11 and value * 100 != (value * 100).to_integral_value(): raise ValueError('Native cents precision required')
    if kind == 12 and value != value.to_integral_value(): raise ValueError('Native whole target precision required')
    return value


def project_normal_wages(profile, owner, copies, fin_fs2, prior_summary):
    if not isinstance(profile, WageProfile) or type(owner) is not str or not owner or type(copies) is not tuple or len(copies) > 64:
        raise ValueError('Prepared resource profile and bounded explicit current inventory required')
    if set(prior_summary) != {'TP1A', 'SP1A'}: raise ValueError('Both explicit prior summary targets required')
    joint_presence = _present(fin_fs2, 3) is not None
    by_copy = {}
    for copy in copies:
        if (not isinstance(copy, W2Copy) or copy.owner != owner or type(copy.runtime_copy_number) is not int
                or copy.runtime_copy_number in by_copy or type(copy.records) is not dict or not set(SOURCE_FIELDS) <= set(copy.records)):
            raise ValueError('Explicit same-owner raw copies and complete selected fields required')
        by_copy[copy.runtime_copy_number] = copy
    if set(by_copy) != set(range(1, len(copies) + 1)):
        raise ValueError('Only explicit dense runtime copy numbers1..CountCopies supported; document locator is not substituted')
    totals, trace = {1: None, 2: None}, []
    for index in range(1, len(copies) + 1):
        raw = by_copy[index].records
        spouse = _present(raw['SPBX'], 3) is not None
        owner_index = 2 if spouse and joint_presence else 0 if spouse else 1
        if owner_index == 0:
            trace.append({'runtime_copy_number': index, 'owner_index': 0, 'action': 'source_spouse_nonjoint_skipped'}); continue
        amount = _present(raw['WAGES'], 11)
        active = _present(raw['__POR__'], 10)
        if active != 1:
            trace.append({'runtime_copy_number': index, 'owner_index': owner_index, 'active': active, 'action': 'source_POR_not_equal_true_skipped'}); continue
        for field in SPECIAL_PRESENCE:
            if _present(raw[field], SOURCE_FIELDS[field]) is not None: raise ValueError('Unsupported normal wage classifier presence including0')
        nq = _present(raw['NQPLANS'], 11)
        if nq is not None and nq > 0: raise ValueError('Positive nonqualified-plan wage adjustment outside normal projection')
        if amount is not None and amount < 0: raise ValueError('Negative raw wages outside finite ordinary projection')
        # Source local123 type12 is assigned before localarray105 type12 adds.
        rounded = None if amount is None else chain.function.typed(12, chain.function.Number(11, int(amount * 100), 2)).amount
        previous = totals[owner_index]
        total = previous if rounded is None else rounded if previous is None else previous + rounded
        if total is not None and abs(total) > 10**9: raise ValueError('Finite selected aggregate limit')
        totals[owner_index] = total
        trace.append({'runtime_copy_number': index, 'owner_index': owner_index, 'source_wages': amount,
            'local123_kind12': rounded, 'array105_before': previous, 'array105_after': total})
    projected, actions = {}, []
    for index, field in ((1, 'TP1A'), (2, 'SP1A')):
        prior = prior_summary[field]; _present(prior, 12); amount = totals[index]
        if amount is None: after, action = prior, 'null_enterable_keeps_storage'
        elif prior is not None and prior.attributes & 8: after, action = prior, 'override8_keeps_storage'
        else: after, action = chain.Record(12, amount, 3), 'computed_Used1_even_zero'
        projected[field] = after; actions.append({'field': field, 'before': prior, 'after': after, 'action': action})
    return {'projected_summary': projected, 'raw_copy_trace': trace, 'summary_write_trace': actions,
        'program_binding': dict(profile.program_binding), 'entire_FW2SUM_section_executed': False,
        'native_copy_inventory_verified': False, 'physical_writes': 0}


def calculate(profile, current_copies, raw_w2_copies):
    if not isinstance(profile, WageProfile) or type(current_copies) is not tuple or not current_copies:
        raise ValueError('Prepared profile and explicit current snapshot required')
    selected = {copy.form_id: copy for copy in current_copies}; owner = current_copies[0].owner
    if len(selected) != len(current_copies) or any(copy.owner != owner for copy in current_copies): raise ValueError('Unique same-owner current copies required')
    def current(fid, field, kind):
        if fid not in selected or field not in selected[fid].records: raise ValueError('Explicit current copy and absence required')
        return _present(selected[fid].records[field], kind)
    status = current('FINFOWKS', 'FS', 1)
    if status not in map(D, range(1, 6)): raise ValueError('Selected source FS enum1..5 required')
    joint = status == 2
    if (current('FINFOWKS', 'FS2', 3) is not None) != joint or (current('F1040', 'FS2', 3) is not None) != joint:
        raise ValueError('Loaded FS enum and both FS2 presence facts must agree in this finite join')
    if current('FW7', 'L15', 12) is not None:
        raise ValueError('Higher-priority FW7.L15 current supplier requires its own raw producer; no stale bypass')
    summary = selected.get('FW2SUM')
    if summary is None or not {'TP1A', 'SP1A'} <= set(summary.records): raise ValueError('Explicit current wage summary targets required')
    projection = project_normal_wages(profile, owner, raw_w2_copies, selected['FINFOWKS'].records['FS2'],
        {field: summary.records[field] for field in ('TP1A', 'SP1A')})
    replacements = {**summary.records, **projection['projected_summary']}
    calculated = chain.calculate(profile.chain_profile, tuple(replace(copy, records=replacements) if copy is summary else copy for copy in current_copies))
    prefix_changes = [{'form': 'FW2SUM', 'file_copy': summary.file_copy, 'field': row['field'], 'before': row['before'], 'after': row['after']}
        for row in projection['summary_write_trace'] if row['before'] != row['after']]
    calculated['proposed_writes'] = prefix_changes + calculated['proposed_writes']
    calculated['raw_normal_W2_projection'] = projection
    calculated['raw_normal_W2_to_final_owed_computed'] = True
    calculated['raw_INT_DIV_producers_not_executed'] = True
    calculated['full_native_FW2SUM_recalculation'] = False
    return calculated
