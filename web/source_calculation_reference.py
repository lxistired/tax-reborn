"""Caller-owned XPRF -> finite ordinary current-state proposed calculation.

No filesystem/network/vendor executable, bundled original bytecode/table,
native state, App import, implicit absent field, or automatic scheduler.
The caller's profile claims must already have an independently reviewed
provenance; matching a caller-provided hash does not authenticate that claim.
"""
from dataclasses import dataclass, asdict
from decimal import Decimal as D
from types import MappingProxyType
import hashlib
import re
import struct

import effective_registry_fields_reference as registry_reader
from field_template_reference import read_id
import finite_function_reference as function
import call_protocol_reference as call
import table_reference as tables_reader

INCOME_PREFIX = (13101, 13100, 13102, 13103, 13205, 13195, 13189, 13029)
SEQUENCE = INCOME_PREFIX + (13044, 13219, 13047, 13039, 13006, 13012, 13183, 13092, 13212, 13054)
ATTRS = (0, 1, 2, 3, 8, 9, 10, 11)
FIELD_OPS = {1, 3, 4, 5, 9, 10, 0xe, 0xf, 0x10, 0x12, 0x14, 0x1c, 0x1f,
             0x51, 0x52, 0x54, 0x65, 0x72, 0x76, 0x83, 0x85, 0x86, 0x88, 0x89}
FUNCTION_OPS = {1, 3, 5, 6, 7, 9, 10, 11, 12, 0xe, 0xf, 0x10, 0x11, 0x12, 0x13,
                0x1f, 0x20, 0x21, 0x26, 0x46, 0x52, 0x56, 0x57, 0x58, 0x59,
                0x5d, 0x5e, 0x5f, 0x67, 0x76}
sha = lambda data: hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class CarrierBytes:
    name: str
    wire: bytes
    expected_sha256: str


@dataclass(frozen=True)
class Record:
    kind: int
    amount: D
    attributes: int
    header: int = 0


@dataclass(frozen=True)
class CurrentCopy:
    # file_copy is an owned document/proposed-write locator. It is NOT the
    # unexecuted runtime zccFormBase+0x7C copy number or a verified native map.
    owner: str
    form_id: str
    file_copy: int
    records: dict


@dataclass(frozen=True)
class VerifiedProfile:
    profile_id: str
    provenance_scope: str
    registry_order: tuple
    forms: object
    dependencies: tuple
    programs: object
    functions: object
    tables: object
    bindings: tuple


def _digest(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Explicit lowercase SHA256 required')
    return value


def index_carrier(carrier):
    if (not isinstance(carrier, CarrierBytes) or type(carrier.name) is not str or not carrier.name
            or type(carrier.wire) is not bytes or sha(carrier.wire) != _digest(carrier.expected_sha256)):
        raise ValueError('Complete caller-owned carrier bytes and matching expected SHA required')
    wire = carrier.wire
    if len(wire) < 16 or wire[:10] != b'XPRF\0\1\x10\x0c\x0a\0':
        raise ValueError('Selected modern little-endian XPRF header required')
    count = struct.unpack_from('<I', wire, 12)[0]; directory_end = 16 + 12 * count
    if not 1 <= count <= 100000 or directory_end > len(wire): raise ValueError('Complete bounded directory required')
    directory, resources, frames = [], {}, {}
    for index in range(count):
        typ, rid, offset, size = struct.unpack_from('<HHII', wire, 16 + index * 12)
        if offset < directory_end or size < 10 or offset + size > len(wire) or (typ, rid) in resources:
            raise ValueError('Unique complete directory keys and bounded frames required')
        frame = wire[offset:offset + size]
        if struct.unpack_from('<IIH', frame) != (size, size - 10, 0):
            raise ValueError('Only complete uncompressed modern frames supported')
        directory.append((offset, size)); resources[typ, rid] = frame[10:]; frames[typ, rid] = frame
    spans = sorted(directory)
    if any(left[0] + left[1] > right[0] for left, right in zip(spans, spans[1:])):
        raise ValueError('Overlapping resource frames refused')
    return MappingProxyType(resources), MappingProxyType(frames)


def _token(value):
    value = value.rstrip(b' ')
    if not value or any(c < 33 or c > 126 for c in value): raise ValueError('Printable fixed-ID token required')
    return value.decode('ascii')


def _decode_program(body, function_id=0):
    if type(body) is not bytes or len(body) < 11: raise ValueError('Complete program body required')
    header, length, variables, arrays, returned, params = struct.unpack_from('<HHHHBH', body)
    if (header != 11 + variables + 6 * arrays + params or header + length != len(body)
            or variables > 64 or arrays > 4 or params > 6): raise ValueError('Finite exact program header required')
    local_types = tuple(body[11:11 + variables]); start = 11 + variables
    array_meta = tuple(struct.unpack_from('<HHH', body, start + 6 * i) for i in range(arrays))
    parameter_types = tuple(body[start + 6 * arrays:header])
    allowed = FUNCTION_OPS if function_id else FIELD_OPS
    pc, rows = header, []
    while pc < len(body):
        at = pc; op = body[pc]; pc += 1
        if op not in allowed: raise ValueError('Unknown or unsupported source opcode refused')
        if op in (1, 3, 4, 5, 0x20, 0x21, 0x56, 0x57, 0x58, 0x59, 0x5e, 0x5f, 0x76, 0x88, 0x89): size = 2
        elif op in (0x83, 0x85): size = 3
        elif op == 0x52: size = 4
        elif op in (0x54, 0x67): size = 1
        elif op == 0x51:
            try: size = body.index(0, pc) + 1 - pc
            except ValueError: raise ValueError('Unterminated source string literal')
        elif op == 6:
            if pc + 2 > len(body): raise ValueError('Truncated membership header')
            size = 2 + struct.unpack_from('<H', body, pc)[0]
        elif op == 0x86:
            if pc >= len(body): raise ValueError('Truncated external ID')
            marker = body[pc]; size = 36 if marker == 255 else marker + 4 if marker < 9 else 11
        else: size = 0
        if pc + size > len(body): raise ValueError('Truncated source instruction')
        rows.append(function.Instruction(at, op, body[pc:pc + size], body[at:pc + size])); pc += size
    boundaries = {row.pc for row in rows} | {len(body)}
    if any(struct.unpack('<H', row.payload)[0] not in boundaries for row in rows if row.opcode in (1, 3, 4, 5)):
        raise ValueError('Unaligned source jump target refused')
    return function.Program(function_id, header, len(body), local_types, array_meta, parameter_types, returned, tuple(rows))


def prepare_profile(carriers, claim):
    """Validate byte identity/complete directories and compile caller resources.

    claim carries reviewed identities/hashes/schema expectations, not original
    bytes. Its provenance remains explicit; synthetic claims are test-only.
    """
    if type(carriers) is not tuple or type(claim) is not dict or not claim.get('profile_id'):
        raise ValueError('Explicit ordered carriers and reviewed profile claim required')
    if claim.get('provenance_scope') not in ('reviewed-original-resource-profile', 'caller-owned-synthetic-test'):
        raise ValueError('Explicit profile provenance boundary required')
    order = tuple(carrier.expected_sha256 for carrier in carriers)
    if order != tuple(claim['registry_order']) or len(set(order)) != len(order): raise ValueError('Exact unique registry carrier order required')
    indexed = {carrier.expected_sha256: index_carrier(carrier) for carrier in carriers}
    registry = registry_reader.register_records(tuple(registry_reader.Carrier(key.encode('ascii'), indexed[key][0]) for key in order))
    compiled = {(_token(fs.identifier), _token(form.identifier)): form for fs in registry.formsets for form in fs.forms}
    forms = {}
    for selected in claim['selected_forms']:
        fsid, fid = selected['formset_id'], selected['form_id']; form = compiled.get((fsid, fid))
        if form is None or form.primary is None: raise ValueError('Selected effective full form primary required')
        home = form.primary.source
        if (home.carrier_key.decode('ascii'), home.resource_id) != (selected['carrier_sha256'], selected['resource_id']):
            raise ValueError('Selected SHA/RID differs from effective primary')
        template, _ = registry_reader.field_template(registry, form, template_swap=False)
        fields = {_token(field.identifier): field for field in template.fields}
        if len(fields) != len(template.fields) or fid in forms: raise ValueError('Unique selected form/field IDs required')
        forms[fid] = (form, MappingProxyType(fields))
    if 'F1040' not in forms or tuple(claim['sequence']) != SEQUENCE: raise ValueError('Exact ordinary manual source sequence required')
    bindings = []
    def resource(typ):
        expected = claim['resources'][str(typ)]
        selected = None
        for home in forms['F1040'][0].homes:
            digest = home.source.carrier_key.decode('ascii'); key = typ, home.source.resource_id
            if key in indexed[digest][0]: selected = digest, key; break
        if selected is None: raise ValueError('Missing effective current form resource')
        digest, key = selected; frame = indexed[digest][1][key]
        if (digest, key[1], sha(frame)) != (expected['carrier_sha256'], expected['resource_id'], expected['record_sha256']):
            raise ValueError('Effective source resource differs from reviewed identity/hash')
        bindings.append({'type': typ, 'carrier_sha256': digest, 'resource_id': key[1], 'record_sha256': sha(frame), 'body_sha256': sha(frame[10:])})
        return frame
    deps = resource(3100)[10:]; count = struct.unpack_from('<H', deps)[0]; at = 2; dependencies = []
    for _ in range(count):
        identifier, at = read_id(deps, at); dependencies.append(_token(identifier))
    if at != len(deps): raise ValueError('Complete dependency-ID payload required')
    programs = {typ: _decode_program(resource(typ)[10:]) for typ in SEQUENCE}
    functions = {index: _decode_program(resource(13299 + index)[10:], index) for index in (1, 2, 3)}
    for index, parameter_types in ((1, (10,)), (2, (12,)), (3, (12, 12, 10, 10, 10, 10))):
        if functions[index].parameter_types != parameter_types or functions[index].return_type != (10 if index == 1 else 12):
            raise ValueError('Exact selected function scalar signature required')
    if functions[3].arrays != ((17, 7, 0), (18, 7, 0), (19, 7, 0), (20, 7, 0)):
        raise ValueError('Exact selected fixed Function3 arrays required')
    version = tables_reader.parse_version(resource(2401))
    tables = {number: tables_reader.parse_table(number, resource(14000 + number), version=version) for number in (16, 17, 19)}
    return VerifiedProfile(claim['profile_id'], claim['provenance_scope'], order, MappingProxyType(forms), tuple(dependencies),
        MappingProxyType(programs), MappingProxyType(functions), MappingProxyType(tables), tuple(bindings))


def _checked_record(record, field):
    if field.kind not in (1, 3, 10, 11, 12) or field.format != 0 or field.attributes & 64:
        raise ValueError('Selected scalar metadata required even for explicit absence')
    if record is None: return
    if (not isinstance(record, Record) or record.kind != field.kind or type(record.kind) is not int
            or record.kind not in (1, 3, 10, 11, 12) or type(record.amount) is not D or not record.amount.is_finite()
            or record.amount * (100 if record.kind == 11 else 1) != (record.amount * (100 if record.kind == 11 else 1)).to_integral_value()
            or abs(record.amount) > 10**9
            or record.attributes not in ATTRS or type(record.attributes) is not int or record.header != 0
            or field.format != 0 or field.attributes & 64):
        raise ValueError('Consistent selected scalar current storage/type/format/attrs required')
    if record.kind in (3, 10) and record.amount not in (D(0), D(1)):
        raise ValueError('Canonical current checkbox/hidden predicate required')


def calculate(profile, copies):
    if not isinstance(profile, VerifiedProfile) or type(copies) is not tuple or not copies:
        raise ValueError('Prepared verified resources and explicit current-copy snapshot required')
    selected, owner = {}, copies[0].owner
    if type(owner) is not str or not owner: raise ValueError('Explicit current owner required')
    for copy in copies:
        if (not isinstance(copy, CurrentCopy) or copy.owner != owner or copy.form_id in selected or copy.form_id not in profile.forms
                or type(copy.file_copy) is not int or not 0 <= copy.file_copy <= 65535 or type(copy.records) is not dict):
            raise ValueError('Unique explicit same-owner existing current copies required')
        if not set(copy.records) <= set(profile.forms[copy.form_id][1]):
            raise ValueError('Current snapshot contains an undeclared field')
        selected[copy.form_id] = copy
    state = {fid: dict(copy.records) for fid, copy in selected.items()}
    reads, writes, trace, calls, opens = [], [], [], [], []
    def metadata(fid, field):
        if fid not in selected or field not in profile.forms[fid][1] or field not in state[fid]:
            raise ValueError('Missing current copy/field/explicit absence refused')
        declared = profile.forms[fid][1][field]; _checked_record(state[fid][field], declared)
        return declared
    def read(fid, field):
        declared = metadata(fid, field); node = state[fid][field]
        value = None if node is None or not node.attributes & 1 else node.amount
        reads.append({'form': fid, 'field': field, 'ordinal': declared.ordinal, 'kind': declared.kind,
            'owner': owner, 'document_file_copy_locator': selected[fid].file_copy, 'present': value is not None,
            'retained_storage': None if node is None else str(node.amount), 'attributes': None if node is None else node.attributes})
        return value
    if read('F1040', 'L36') is None or read('F1040', 'HAS2555') not in (None, D(0)):
        raise ValueError('Ordinary profile requires presentL36/noforeign selector')
    for fid, field in (('F8615', 'L18'), ('FWSCHD40', 'L37'), ('FWCGTAX', 'L27'), ('FSCHJ', 'L22')):
        if read(fid, field) is not None: raise ValueError('Special child/preferential present amount including0 refused')
    if read('FINFOWKS', 'FS') not in map(D, range(1, 6)):
        raise ValueError('Reviewed finite source filing code1..5 required')
    # L39 is now a proposed output of the source prefix, not a supplied scalar.
    if read('FSCHE2', 'HL37C') is not None:
        raise ValueError('Alternate FSCHE2 current amount including present0 refused')
    def run_function(index, values):
        program = profile.functions[index]; prepared = []
        for kind, value in zip(program.parameter_types, values):
            prepared.append(None if value is None or type(value) is bool and not value else function.Number(kind, int(value), 0))
        if len(values) != len(program.parameter_types): raise ValueError('Actual parameter count required')
        def lookup(table, key):
            result = tables_reader.lookup_exact(dict(profile.tables), call.Value(table.kind, table.amount),
                None if key is None else call.Value(key.kind, key.amount), owner=owner)
            value = result['value']
            return None if value is None else function.Number(value.kind, int(value.amount), 0), result
        def midpoint(argument):
            child = run_function(2, (None if argument is None else argument.amount,))
            return child['result'], child
        return function.execute(dict(profile.functions), index, tuple(prepared), lookup=lookup, midpoint=midpoint)
    local_by_ordinal = {field.ordinal: name for name, field in profile.forms['F1040'][1].items()}
    for typ in SEQUENCE:
        if typ == 13044:
            taxable = read('F1040', 'L39')
            if taxable is not None and taxable < 0: raise ValueError('Nonnegative current taxable result required')
        program = profile.programs[typ]; rows = {row.pc: row for row in program.instructions}; stack = []; pc = program.start; steps = 0
        if program.local_types or program.arrays or program.parameter_types: raise ValueError('Selected scalar field sections only')
        while pc < program.end:
            if pc not in rows or steps > 1000: raise ValueError('Finite exact field-program flow required')
            steps += 1; row = rows[pc]; op, payload = row.opcode, row.payload; next_pc = pc + len(row.raw)
            if op in (0x83, 0x85):
                ordinal, flag = struct.unpack('<HB', payload)
                if flag or ordinal not in local_by_ordinal: raise ValueError('Exact scalar local ordinal required')
                field = local_by_ordinal[ordinal]
                if op == 0x83: stack.append(read('F1040', field))
                else: metadata('F1040', field); stack.append(('target', field))
            elif op == 0x88:
                index = struct.unpack('<H', payload)[0]
                if index >= len(profile.dependencies): raise ValueError('Exact dependency index required')
                stack.append(('formid', profile.dependencies[index]))
            elif op == 0x89:
                reference = stack.pop()
                if payload != b'\x01\x00' or reference[0] != 'formid': raise ValueError('Existing ordinary form-address reference required')
                stack.append(('address', reference[1]))
            elif op == 0x86:
                reference = stack.pop(); identifier, at = read_id(payload, 0)
                if reference[0] != 'address' or payload[at:] != bytes(3): raise ValueError('Scalar current external field required')
                stack.append(read(reference[1], _token(identifier)))
            elif op == 0x52: stack.append(D(struct.unpack('<i', payload)[0]))
            elif op == 0x54:
                if payload not in (b'0', b'1'): raise ValueError('Exact immediate Boolean required')
                stack.append(payload == b'1')
            elif op == 0x1f: stack.append(stack.pop() is not None)
            elif op == 0x14:
                value = stack.pop()
                if type(value) is not bool: raise ValueError('Immediate Boolean Not only')
                stack.append(not value)
            elif op in (9, 10, 0x1c, 0xe, 0xf, 0x10, 0x12):
                right, left = stack.pop(), stack.pop()
                a, b = (D(0) if value is None else D(int(value)) if type(value) is bool else value for value in (left, right))
                if type(a) is not D or type(b) is not D: raise ValueError('Selected whole numeric operands required')
                if op in (9, 10, 0x1c):
                    value = None if left is None and right is None else a + b if op == 9 else a - b if op == 10 else max(a, b)
                    if value is not None and abs(value) > 10**9: raise ValueError('Finite arithmetic limit')
                else: value = a < b if op == 0xe else a > b if op == 0xf else a == b if op == 0x10 else a >= b
                stack.append(value)
            elif op in (1, 3, 4, 5):
                if op == 1: taken = True
                else:
                    value = stack.pop()
                    if value is not None and type(value) not in (bool, D): raise ValueError('Selected scalar branch required')
                    if type(value) is D and value != value.to_integral_value(): raise ValueError('Whole source predicate required')
                    taken = bool(value) if op == 4 else not bool(value)
                    if op in (4, 5) and taken: stack.append(value)
                if taken: next_pc = struct.unpack('<H', payload)[0]
            elif op == 0x65:
                reference = stack.pop()
                if reference[0] != 'address' or reference[1] not in selected: raise ValueError('OpenForm requires explicit existing copy')
                opens.append({'resource_type': typ, 'pc': pc, 'form': reference[1], 'new_native_creation': False})
            elif op == 0x76:
                if payload != b'\x03\x00': raise ValueError('Only bound ordinary Function3 field call')
                values = tuple(reversed([stack.pop() for _ in range(6)])); execution = run_function(3, values)
                value = execution['result']; stack.append(None if value is None else value.amount)
                calls.append({'resource_type': typ, 'pc': pc, 'execution': execution})
            elif op == 0x72:
                value, target = stack.pop(), stack.pop()
                if target[0] != 'target': raise ValueError('Exact enterable field target')
                field = target[1]; declared = metadata('F1040', field); old = state['F1040'][field]
                if value is None: action = 'null_enterable_keeps_storage'
                elif old is not None and old.attributes & 8: action = 'override8_keeps_storage'
                else:
                    value = D(int(value)) if type(value) is bool else value
                    if type(value) is not D: raise ValueError('Exact decimal target value')
                    if declared.kind == 3 and value != 1: raise ValueError('Unclosed checkbox zero/group assignment refused')
                    if declared.kind == 12:
                        parts = value.as_tuple(); exponent = max(0, -parts.exponent)
                        coefficient = int(value.scaleb(exponent))
                        # Same audited AssignValue/ConvertFromFixPoint path:
                        # actual sourcekind11 cents may round into kind12.
                        value = function.typed(12, function.Number(25, coefficient, exponent)).amount
                    elif value != value.to_integral_value(): raise ValueError('Whole current target required')
                    state['F1040'][field] = Record(declared.kind, value, 3); action = 'computed_Used1_even_zero'
                writes.append({'resource_type': typ, 'pc': pc, 'form': 'F1040', 'field': field,
                    'ordinal': declared.ordinal, 'kind': declared.kind, 'action': action,
                    'before': old, 'after': state['F1040'][field], 'physical_write': False})
            else: raise ValueError('Unsupported finite field execution opcode')
            trace.append({'resource_type': typ, 'pc': pc, 'opcode': op, 'next_pc': next_pc, 'raw_sha256': sha(row.raw)})
            pc = next_pc
        if pc != program.end or stack: raise ValueError('Normal program end/empty stack required')
    changes = [{'form': fid, 'file_copy': selected[fid].file_copy, 'field': field, 'before': selected[fid].records[field], 'after': node}
               for fid, records in state.items() for field, node in records.items() if node != selected[fid].records[field]]
    return {'profile_id': profile.profile_id, 'profile_provenance_scope': profile.provenance_scope,
        'owner': owner, 'source_bindings': profile.bindings, 'current_fields': state, 'proposed_writes': changes,
        'current_read_trace': reads, 'current_write_trace': writes, 'source_instruction_trace': trace,
        'function_calls': calls, 'existing_form_requests': opens, 'manual_source_sequence': SEQUENCE,
        'current_income_summaries_to_L22_L32_L33_L39_computed': True,
        'raw_W2_1099_aggregation_and_summary_freshness_not_executed': True,
        'final_tax_L57': read('F1040', 'L57'), 'final_owed_L69': read('F1040', 'L69'),
        'native_automatic_dependency_or_global_recalculation': False, 'physical_writes': 0,
        'document_file_copy_not_native_copy_number': True, 'runtime_copy_identity_verified': False,
        'original_native_runtime_executions': 0, 'original_saved_return_acceptance': 0,
        'voucher_TPS30723_not_executed_by_this_XPRF_only_runner': True}
