"""Owned scalar call-frame contract, with no vendor I/O or function-body VM.

CreateParameters treats immediateFalse as absent, unlike a nonnull numeric0.
ReturnVal boxes immediateFalse as presentkind10zero; declared returntype gates
the caller push and does not cast the returned value. Normal noerror only.
"""
from dataclasses import dataclass
from decimal import Decimal as D
import hashlib
import struct

PROFILE = 'independent-local-scalar-function-call-v1'


@dataclass(frozen=True)
class Value:
    kind: int
    amount: D


@dataclass(frozen=True)
class Descriptor:
    function_id: int
    resource_type: int
    body_sha256: str
    header_size: int
    code_length: int
    declared_return_type: int
    parameter_types: tuple


@dataclass(frozen=True)
class Parameter:
    kind: int
    present: bool
    value: Value | None
    branch: str


def checked(value, *, input_value=False):
    if (not isinstance(value, Value) or type(value.kind) is not int
            or value.kind not in ((1, 10, 12) if input_value else (1, 10, 11, 12, 25))
            or type(value.amount) is not D or not value.amount.is_finite()
            or abs(value.amount) > D('1e9')):
        raise ValueError('Finite selected numeric pointer value required')
    if input_value and value.amount != value.amount.to_integral_value():
        raise ValueError('Call input conversion is limited to exact whole scalars')
    if value.kind in (1, 10, 12) and value.amount != value.amount.to_integral_value():
        raise ValueError('Selected integer kind requires exact whole payload')


def descriptor_from_body(function_id, body, *, profile=PROFILE):
    if profile != PROFILE or type(function_id) is not int or function_id not in (1, 2, 3) or type(body) is not bytes or len(body) < 11:
        raise ValueError('Selected local function1..3 and complete little-endian body required')
    header, length, variables, arrays, returned, count = struct.unpack_from('<HHHHBH', body)
    if header != 11 + variables + 6 * arrays + count or header + length != len(body) or count > 6:
        raise ValueError('Actual scalar function header/trailer framing required')
    kinds = tuple(body[11 + variables + 6 * arrays:header])
    expected = {1: (10,), 2: (12,), 3: (12, 12, 10, 10, 10, 10)}[function_id]
    if kinds != expected or returned != (10 if function_id == 1 else 12):
        raise ValueError('Selected exact scalar parameter and return metadata required')
    return Descriptor(function_id, 13300 + function_id - 1, hashlib.sha256(body).hexdigest(), header, length, returned, kinds)


def prepare(descriptor, arguments, *, profile=PROFILE):
    if (profile != PROFILE or not isinstance(descriptor, Descriptor) or type(arguments) is not tuple
            or len(arguments) != len(descriptor.parameter_types) or not 1 <= len(arguments) <= 6
            or descriptor.parameter_types != {1: (10,), 2: (12,), 3: (12, 12, 10, 10, 10, 10)}.get(descriptor.function_id)
            or descriptor.resource_type != 13300 + descriptor.function_id - 1
            or (descriptor.header_size, descriptor.code_length, descriptor.declared_return_type) !=
                {1: (21, 299, 10), 2: (13, 139, 12), 3: (62, 492, 12)}.get(descriptor.function_id)
            or type(descriptor.body_sha256) is not str or len(descriptor.body_sha256) != 64
            or any(char not in '0123456789abcdef' for char in descriptor.body_sha256)):
        raise ValueError('Exact selected descriptor and ordered scalar arguments required')
    records = [None] * len(arguments); trace = []
    for index in reversed(range(len(arguments))):
        operand = arguments[index]; kind = descriptor.parameter_types[index]
        if operand is None:
            record = Parameter(kind, False, None, 'null_pointer_sets_type_only')
        elif type(operand) is bool:
            record = Parameter(kind, operand, Value(kind, D(1)) if operand else None,
                'immediateTrue_Assign1_present1' if operand else 'immediateFalse_sets_type_only_present0')
        else:
            checked(operand, input_value=True)
            record = Parameter(kind, True, Value(kind, operand.amount), 'nonnull_numeric_AssignValue_present1_even_zero')
        records[index] = record
        trace.append({'popped_argument_index': index, 'declared_kind': kind, 'present': record.present, 'branch': record.branch,
            'native_record_stride': 32, 'native_present_byte_offset': 0, 'native_embedded_Value_offset': 2,
            'native_variant_kind_offset': 24, 'native_variant_scalar_tag': 1})
    return {'descriptor': descriptor, 'parameters': tuple(records), 'argument_pop_trace': tuple(trace),
        'actual_native_allocation_or_execution': 0, 'normal_noerror_success_supplied': True}


def read_parameter(frame, index):
    if type(frame) is not dict or type(frame.get('parameters')) is not tuple:
        raise ValueError('Owned scalar call frame required')
    if type(index) is not int or not 0 <= index < len(frame['parameters']):
        raise ValueError('In-range scalar parameter index required')
    record = frame['parameters'][index]
    if not isinstance(record, Parameter) or type(record.present) is not bool:
        raise ValueError('Owned scalar parameter block required')
    if record.kind not in (10, 12) or (record.present and (not isinstance(record.value, Value) or record.value.kind != record.kind)) or (not record.present and record.value is not None):
        raise ValueError('Consistent selected scalar parameter block required')
    if record.present: checked(record.value, input_value=True)
    return record.value if record.present else None


def box_return(operand):
    if operand is None: return None
    if type(operand) is bool: return Value(10, D(int(operand)))
    checked(operand)
    return Value(operand.kind, operand.amount)


def finish(declared_return_type, operand):
    if type(declared_return_type) is not int or not 0 <= declared_return_type <= 255:
        raise ValueError('Actual u8 declared return gate required')
    boxed = box_return(operand)
    return {'caller_push_occurs': declared_return_type != 0,
        'caller_pushed_value': boxed if declared_return_type else None,
        'callee_return_storage': boxed, 'returned_value_header_cast_to_declared_type': False,
        'normal_return_only': True, 'native_unwind_guarantee': False, 'actual_native_execution': 0}
