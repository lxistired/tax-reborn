"""Owned selected modern tax-table reader and exact-key lookup, no vendor I/O.

Native queue current-form, resource/GetData/cache success are explicit caller
boundaries. A miss is refused because native interpolation/error side effects
are outside this finite exact-key profile. No general table compatibility.
"""
from dataclasses import dataclass
from decimal import Decimal as D
import hashlib
import struct

import call_protocol_reference as call

PROFILE = 'independent-current-F1040-modern-tax-table-exact-v1'


@dataclass(frozen=True)
class Table:
    table_id: int
    version: int
    key_kind: int
    value_kind: int
    rows: tuple
    record_sha256: str


def _body(record):
    if type(record) is not bytes or len(record) < 10:
        raise ValueError('Complete caller-supplied little-endian resource frame required')
    total, unpacked, flag = struct.unpack_from('<IIH', record)
    if total != len(record) or unpacked != len(record) - 10 or flag != 0:
        raise ValueError('Exact uncompressed resource framing required')
    return record[10:]


def parse_version(record):
    body = _body(record)
    if len(body) != 4 or struct.unpack('<I', body)[0] != 31:
        raise ValueError('Selected original current F1040 version31 profile required')
    return 31


def parse_table(table_id, record, *, version, profile=PROFILE):
    if profile != PROFILE or type(table_id) is not int or table_id not in (16, 17, 19) or type(version) is not int or version != 31:
        raise ValueError('Selected current F1040 table16/17/19 and version31 required')
    body = _body(record)
    if len(body) < 4: raise ValueError('Actual modern table header required')
    count, key_kind, value_kind = struct.unpack_from('<HBB', body)
    if not 1 <= count <= 2000 or len(body) != 4 + count * 32 or key_kind != 10 or value_kind != (12 if table_id == 19 else 10):
        raise ValueError('Exact selected modern32B whole-key/value table layout required')
    rows = []
    for index in range(count):
        at = 4 + index * 32; key, key_exp, value, value_exp = struct.unpack_from('<qH6xqH6x', body, at)
        if (key_exp != 0 or value_exp != 0 or body[at + 10:at + 16] != bytes(6)
                or body[at + 26:at + 32] != bytes(6) or abs(key) > 10**9 or abs(value) > 10**9):
            raise ValueError('Selected source exact whole rows and verified zero padding required')
        if rows and key <= rows[-1][0]: raise ValueError('Strictly increasing selected source table keys required')
        rows.append((key, value))
    return Table(table_id, 31, key_kind, value_kind, tuple(rows), hashlib.sha256(record).hexdigest())


def lookup_exact(tables, table_id, key, *, owner, current_form='F1040', profile=PROFILE):
    if profile != PROFILE or type(owner) is not str or not owner or current_form != 'F1040' or type(tables) is not dict:
        raise ValueError('Prepared same-owner current F1040 table inventory required')
    if not isinstance(table_id, call.Value) or table_id.kind != 10 or table_id.amount not in (D(16), D(17), D(19)):
        raise ValueError('Actual selected table-id pointer kind10 required')
    call.checked(table_id, input_value=True)
    if key is None:
        return {'value': None, 'native_branch': 'null_key_returns_null_before_FindForm',
            'current_owner': owner, 'physical_native_lookup_calls': 0}
    call.checked(key)
    if key.amount != key.amount.to_integral_value() or key.kind not in (1, 10, 12, 25):
        raise ValueError('Selected whole numeric key pointer required')
    number = int(table_id.amount); table = tables.get(number)
    if not isinstance(table, Table) or (table.table_id, table.version, table.key_kind, table.value_kind) != (number, 31, 10, 12 if number == 19 else 10):
        raise ValueError('Prepared exact current form table and metadata required')
    if (type(table.rows) is not tuple or not 1 <= len(table.rows) <= 2000
            or any(type(row) is not tuple or len(row) != 2 or any(type(value) is not int or abs(value) > 10**9 for value in row)
                   for row in table.rows)
            or any(left[0] >= right[0] for left, right in zip(table.rows, table.rows[1:]))):
        raise ValueError('Consistent finite owned sorted table rows required')
    # Mirrors the native linear upper-bound traversal; only the equality path
    # is eligible here. No native table row pointer or cache is created.
    for index, (row_key, row_value) in enumerate(table.rows):
        if row_key < key.amount: continue
        if row_key != key.amount: break
        result = call.Value(table.value_kind, D(row_value))
        return {'value': result, 'native_branch': 'modern31_exact_upper_key_copy_no_interpolation',
            'current_owner': owner, 'current_form': current_form, 'table_id': number, 'row_index': index,
            'native_attribute_type': 14000 + number, 'native_key_type': 10,
            'native_value_type': table.value_kind, 'actual_native_table_allocation_or_cache_lookup': 0,
            'native_GetData_resource_lock_success_supplied': True}
    raise ValueError('Unclosed interpolation, out-of-range, missing table/error side effects refused')
