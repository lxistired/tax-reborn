"""Owned finite local tax-function interpreter; no vendor I/O.

Programs, sorted table records, and the exact midpoint executor are supplied
by the separately bound private wrapper. Program construction is not source
authentication. Native storage, allocation and normal execution remain models.
Only the ordinary, zero-adjustment, year25 Function3 path is admitted.
"""
from dataclasses import dataclass
from decimal import Decimal as D
from fractions import Fraction
import hashlib
import struct

import function3_fixed_bridge_reference_private as bridge

LIMIT = 10**9
GUARD = 0xccccccccccccccd
SCALE_GUARD = 0x147ae147ae147af
PRECISION = {10: 0, 11: 2, 12: 0, 13: 1, 14: 2, 15: 3,
             16: 4, 17: 5, 18: 6, 19: 7, 20: 8}
KIND_FOR_PRECISION = (10, 13, 14, 15, 16, 17, 18, 19, 20)


@dataclass(frozen=True)
class Number:
    kind: int
    coefficient: int
    exponent: int

    @property
    def fraction(self):
        return Fraction(self.coefficient, 10**self.exponent)

    @property
    def amount(self):
        return D(self.coefficient).scaleb(-self.exponent)


@dataclass(frozen=True)
class Instruction:
    pc: int
    opcode: int
    payload: bytes
    raw: bytes


@dataclass(frozen=True)
class Program:
    function_id: int
    start: int
    end: int
    local_types: tuple
    arrays: tuple
    parameter_types: tuple
    return_type: int
    instructions: tuple


def checked(value):
    if (not isinstance(value, Number) or type(value.kind) is not int
            or value.kind not in (*PRECISION, 25)
            or type(value.coefficient) is not int or abs(value.coefficient) >= 2**63 - 1
            or type(value.exponent) is not int or not 0 <= value.exponent <= 18
            or abs(value.fraction) > LIMIT
            or (value.kind != 25 and value.exponent != PRECISION[value.kind])):
        raise ValueError('Consistent finite selected numeric coefficient/exponent required')
    return value


def whole(value):
    checked(value)
    if value.fraction.denominator != 1:
        raise ValueError('Exact whole selected scalar required')
    return int(value.fraction)


def typed(kind, value):
    """Numeric AssignValue -> ConvertFromFixPoint -> GetMantissaAsIf.

    Mirrors signed quotient/remainder and half-away-from-zero. It never
    routes numeric zero through Boolean truth or makes blank present.
    """
    if type(kind) is not int or kind not in (10, 11, 12, 15):
        raise ValueError('Only actual selected local kinds10/11/12/15')
    if value is None: return None
    if type(value) is bool: value = Number(10, int(value), 0)
    checked(value); exponent = PRECISION[kind]
    if exponent >= value.exponent:
        coefficient = value.coefficient * 10**(exponent - value.exponent)
    else:
        divisor = 10**(value.exponent - exponent)
        quotient, remainder = divmod(abs(value.coefficient), divisor)
        coefficient = (quotient + int(remainder * 2 >= divisor)) * (-1 if value.coefficient < 0 else 1)
    return checked(Number(kind, coefficient, exponent))


def _result(coefficient, exponent, *, left=None, right=None, operation=None):
    if abs(coefficient) >= 2**63 - 1 or not 0 <= exponent <= 18:
        raise ValueError('Native sentinel/overflow/excess precision refused')
    kind = KIND_FOR_PRECISION[exponent] if exponent < 9 else 25
    # ConvertFromFixPoint(kind25) removes exact trailing zeroes. The chosen
    # kind remains25 even when the stored exponent becomes small.
    if kind == 25:
        while exponent and coefficient % 10 == 0:
            coefficient //= 10; exponent -= 1
    value = checked(Number(kind, coefficient, exponent))
    # OperatorMath's numeric Add/Sub post-processing changes an integer result
    # back to the eligible left kind. This selected profile only reaches12.
    if (operation in (9, 10) and left is not None and right is not None
            and left.kind in (1, 2, 12) and right.kind in (1, 2, 10, 12)
            and value.kind == 10):
        value = typed(left.kind, value)
    return value


def arithmetic(opcode, left, right):
    for value in (left, right):
        if value is not None: checked(value)
    if opcode not in (9, 10, 11, 12): raise ValueError('Selected Add/Sub/Mul/Div only')
    if left is None and right is None: return None, {'branch': 'both_blank_null'}
    if opcode == 9 and (left is None or right is None):
        return left if right is None else right, {'branch': 'Add_copy_nonnull'}
    if opcode == 10 and right is None: return left, {'branch': 'Subtract_copy_left'}
    if opcode in (11, 12) and (left is None or right is None):
        return None, {'branch': 'Multiply_Divide_requires_both_nonnull'}
    if left is None: left = Number(10, 0, 0)
    if opcode in (9, 10):
        exponent = max(left.exponent, right.exponent)
        lcoef = left.coefficient * 10**(exponent - left.exponent)
        rcoef = right.coefficient * 10**(exponent - right.exponent)
        coefficient = lcoef + (rcoef if opcode == 9 else -rcoef)
        # The actual Add digit loop consumes all exponent digits in this
        # range. No significant-digit drop or native rounding branch occurs.
        if max(abs(lcoef), abs(rcoef), abs(coefficient)) >= GUARD:
            raise ValueError('Unclosed significant-digit Add/negation range refused')
        trace = {'branch': 'exact_aligned_Add' if opcode == 9 else 'negate_right_then_exact_Add',
                 'aligned_exponent': exponent, 'unconsumed_remainder': 0}
    elif opcode == 11:
        coefficient = left.coefficient * right.coefficient
        exponent = left.exponent + right.exponent
        if abs(coefficient) >= GUARD or exponent > 18:
            raise ValueError('Unclosed large native Boost product/rounding refused')
        trace = {'branch': 'exact_small_signed64_product',
                 'native_Boost_product_format_allocator_normal_success_supplied': True}
    else:
        numerator, divisor = whole(left), whole(right)
        if numerator < 0 or divisor != 1000:
            raise ValueError('Selected nonnegative whole /1000 only')
        if numerator == 0:
            return Number(10, 0, 0), {'branch': 'native_Div_zero_early_return', 'remainder': 0}
        n, d, exponent, scaled = numerator, divisor, 0, 0
        while d % 10 == 0 and exponent < 18: d //= 10; exponent += 1
        if n < GUARD and exponent < 18:
            while True:
                previous, old_exponent = n, exponent
                n *= 10; exponent += 1; scaled += 1
                if old_exponent > 16 or previous >= SCALE_GUARD: break
        coefficient, remainder = divmod(n, d)
        if remainder or exponent > 18:
            raise ValueError('Unclosed long-division remainder extension refused')
        trace = {'branch': 'native_Div_normalize1000_scale_exact_remainder0',
                 'scaled_steps': scaled, 'normalized_divisor': d, 'remainder': remainder,
                 'raw_coefficient': coefficient, 'raw_exponent': exponent}
    return _result(coefficient, exponent, left=left, right=right, operation=opcode), trace


def truth(value):
    if type(value) is bool: return value
    if value is None: return False
    # Selected JumpIfFalse/GetValue sources are whole kind10 only.
    if value.kind != 10: raise ValueError('Selected branch needs whole kind10 pointer')
    return whole(value) != 0


def compare(opcode, left, right):
    for value in (left, right):
        if value is not None: checked(value)
    left = Fraction(0) if left is None else left.fraction
    right = Fraction(0) if right is None else right.fraction
    if opcode == 0xe: return left < right
    if opcode == 0xf: return left > right
    if opcode == 0x10: return left == right
    if opcode == 0x11: return left != right
    if opcode == 0x12: return left >= right
    if opcode == 0x13: return left <= right
    raise ValueError('Selected source comparison required')


def execute(programs, function_id, parameters, *, lookup, midpoint):
    """Execute prepared actual Programs1/3; nested2 uses bound49-row caller.

    lookup is the exact source-bound reader, not a supplied tax scalar.
    midpoint is the separately source-bound actual Function2 interpreter.
    Generic callbacks, malformed/native references and error unwinds are not
    accepted by the private current-tax wrapper that invokes this function.
    """
    if function_id not in (1, 3) or type(programs) is not dict:
        raise ValueError('Selected actual Function1/3 inventory required')
    program = programs.get(function_id)
    if (not isinstance(program, Program) or program.function_id != function_id
            or type(parameters) is not tuple or len(parameters) != len(program.parameter_types)):
        raise ValueError('Prepared typed program and exact scalar parameters required')
    parameters = list(parameters)
    for kind, value in zip(program.parameter_types, parameters):
        if value is not None and (checked(value).kind != kind or whole(value) != value.fraction):
            raise ValueError('Prepared exact whole scalar parameter kinds required')
    if function_id == 3 and (len(parameters) != 6 or parameters[1] != Number(12, 0, 0)
            or parameters[3] != Number(10, 25, 0) or parameters[4] != Number(10, 1, 0)):
        raise ValueError('Selected ordinary zero-adjustment current-year25 table-tax call only')
    if function_id == 1 and parameters != [Number(10, 25, 0)]:
        raise ValueError('Only selected actual Function1 normalization of25')
    rows = {row.pc: row for row in program.instructions}
    if (len(rows) != len(program.instructions) or program.start not in rows
            or any(type(row.raw) is not bytes or row.raw != bytes((row.opcode,)) + row.payload for row in rows.values())):
        raise ValueError('Consistent bytecode row framing required')
    locals_ = {index: None for index in range(len(program.local_types))}
    arrays = {ordinal: [None] * capacity for ordinal, capacity, flags in program.arrays if flags == 0}
    if len(arrays) != len(program.arrays): raise ValueError('Selected fixed arrays only')
    stack, trace, math, writes, table_reads, nested, index_reads = [], [], [], [], [], [], []
    pc, returned = program.start, None
    def scalar_assignment(kind, operand):
        converted = operand if operand is None or type(operand) is bool else bridge.Numeric(operand.kind, operand.amount)
        assigned = bridge.scalar_parameter_assign(kind, converted)
        return None if not assigned.present else Number(kind, int(assigned.amount), 0)
    while pc < program.end:
        if pc not in rows or len(trace) >= 2000: raise ValueError('Source control-flow/finite loop guard')
        row = rows[pc]; op, payload = row.opcode, row.payload
        next_pc = pc + len(row.raw); extra = {}
        if op == 0x52: stack.append(Number(10, struct.unpack('<i', payload)[0], 0))
        elif op in (0x56, 0x58, 0x5e, 0x5f):
            index = struct.unpack('<H', payload)[0]
            if op in (0x56, 0x58):
                if index not in locals_: raise ValueError('Exact local variable index')
                stack.append(('local', index) if op == 0x56 else locals_[index])
            else:
                if index >= len(parameters): raise ValueError('Exact scalar parameter index')
                stack.append(('parameter', index) if op == 0x5f else parameters[index])
        elif op in (0x57, 0x59):
            ordinal = struct.unpack('<H', payload)[0]; operand = stack.pop()
            if operand is None: raise ValueError('Selected nonnull existing array index')
            index = bridge.array_index(bridge.Numeric(operand.kind, operand.amount), ordinal, len(arrays.get(ordinal, ())))
            stack.append(('array', ordinal, index) if op == 0x57 else arrays[ordinal][index - 1])
            index_reads.append({'pc': pc, 'ordinal': ordinal, 'index': index, 'native_u16_narrowing_is_identity': True})
        elif op in (7, 0x46):
            operand, reference = stack.pop(), stack.pop()
            if not isinstance(reference, tuple): raise ValueError('Actual selected scalar/local/array reference')
            if op == 0x46:
                if reference[0] != 'parameter': raise ValueError('Parameter assign reference')
                index = reference[1]; kind = program.parameter_types[index]
                value = scalar_assignment(kind, operand); parameters[index] = value
            elif reference[0] == 'local':
                index = reference[1]; kind = program.local_types[index]
                value = typed(kind, operand); locals_[index] = value
            elif reference[0] == 'array':
                ordinal, index = reference[1:]; kind = program.local_types[ordinal]
                value = typed(kind, operand); arrays[ordinal][index - 1] = value
            else: raise ValueError('Selected local assignment reference')
            writes.append({'pc': pc, 'reference': reference, 'target_kind': kind, 'value': value,
                           'present': value is not None, 'native_record_stride': 32 if op == 0x46 else 14})
        elif op in (9, 10, 11, 12):
            right, left = stack.pop(), stack.pop(); value, witness = arithmetic(op, left, right)
            stack.append(value); math.append({'pc': pc, 'opcode': op, 'left': left, 'right': right, 'value': value, **witness})
        elif op in range(0xe, 0x14):
            right, left = stack.pop(), stack.pop(); stack.append(compare(op, left, right))
        elif op == 0x1f:
            value = stack.pop()
            if value is not None: checked(value)
            stack.append(value is not None)
        elif op in (1, 3, 5):
            target = struct.unpack('<H', payload)[0]
            if target not in rows and target != program.end: raise ValueError('Actual jump target row boundary')
            if op == 1: taken = True
            else:
                tested = stack.pop(); taken = not truth(tested)
                if op == 5 and taken: stack.append(tested)
            if taken: next_pc = target
            extra['jump_taken'] = taken
        elif op == 6:
            count = struct.unpack_from('<H', payload)[0]
            if count != 5 or payload[2:] != bytes(5): raise ValueError('Actual five scalar nonrange membership')
            tested = stack.pop(); candidates = [stack.pop() for _ in range(count)]
            if any(value != Number(10, index, 0) for index, value in zip(range(5, 0, -1), candidates)):
                raise ValueError('Actual ordered filing codes1..5 required')
            stack.append(tested is not None and whole(tested) in range(1, 6))
        elif op == 0x67:
            if payload != b'\x00': raise ValueError('Actual current-form table lookup with no form identifier')
            key, table = stack.pop(), stack.pop(); value, receipt = lookup(table, key)
            stack.append(value); table_reads.append({'pc': pc, **receipt})
        elif op in (0x20, 0x21):
            index = struct.unpack('<H', payload)[0]; old = locals_[index]
            if old is None: raise ValueError('Selected initialized loop counter')
            updated = bridge.index_step(bridge.Numeric(old.kind, old.amount), 1 if op == 0x20 else -1)
            locals_[index] = Number(updated.kind, int(updated.amount), 0)
            writes.append({'pc': pc, 'reference': ('local', index), 'value': locals_[index], 'present': True,
                           'native_record_stride': 14, 'actual_index_step': True})
        elif op == 0x76:
            target = struct.unpack('<H', payload)[0]
            if target not in (1, 2): raise ValueError('Actual nested Function1/2 only')
            argument = stack.pop()
            if target == 1:
                if argument is None or argument.kind != 10: raise ValueError('Actual annual call25')
                child = execute(programs, 1, (argument,), lookup=lookup, midpoint=midpoint)
                value = child['result']
            else:
                value, child = midpoint(argument)
            stack.append(value); nested.append({'pc': pc, 'function': target, 'argument': argument, 'result': value, 'execution': child})
        elif op == 0x5d:
            returned = stack.pop()
            if type(returned) is bool: returned = Number(10, int(returned), 0)
            elif returned is not None: checked(returned)
            extra['normal_ReturnVal_clones_actual_kind_without_declared_cast'] = True
        else: raise ValueError('Opcode outside actual selected Function1/3')
        if next_pc not in rows and next_pc != program.end: raise ValueError('Complete next opcode boundary')
        trace.append({'pc': pc, 'opcode': op, 'next_pc': next_pc, 'raw_sha256': hashlib.sha256(row.raw).hexdigest(),
                      'stack_size_after': len(stack), **extra})
        pc = next_pc
    if pc != program.end or stack: raise ValueError('Actual normal end with empty local stack required')
    return {'function': function_id, 'result': returned, 'parameters': tuple(parameters),
            'locals': locals_, 'arrays': {key: tuple(value) for key, value in arrays.items()},
            'source_instruction_trace': trace, 'native_finite_math_trace': math, 'typed_assignment_trace': writes,
            'table_reads': table_reads, 'nested_calls': nested, 'array_index_trace': index_reads,
            'source_rows': len(rows), 'normal_return_only': True,
            'native_Boost_allocation_global_fixed_temporaries_local_storage_success_supplied': True,
            'original_native_runtime_executions': 0, 'physical_TPS_writes': 0,
            'original_saved_return_acceptance': 0, 'native_global_queue_completed': False}
