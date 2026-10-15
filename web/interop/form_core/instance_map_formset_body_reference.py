"""Finite stored type14F body codec; byte view, not current native cache.

Only complete nonempty version1 bodies are accepted. Native Load may clean rows
or migrate14D data later; neither native operation is executed here. Compressed
body bytes are preserved exactly. Logical path strings are opaque bytes.
"""
from dataclasses import dataclass
import struct
from .metadata_formset_body_reference import decode_framed_stream
from .cx_string_wire_reference import UnsupportedProfile
from .native_mode4_reference import emit_selected_block, Buffers

NAME = b'TpsInstanceToMefInstanceMapFormSetPO'
CLASS_ID = 0x14F
MAX_BYTES = 4 * 1024 * 1024
MAX_ROWS = 65535


@dataclass(frozen=True)
class StoredPair:
    tps_address: bytes
    mef_xpath: bytes


@dataclass(frozen=True)
class StoredBody:
    rows: tuple
    decoded_payload: bytes
    source_body: bytes
    source_compression_chunks: tuple
    compression_endian: int
    native_cleanup_executed: bool = False
    native_14D_transfer_executed: bool = False
    native_current_cache_verified: bool = False


def _pair(pair):
    if type(pair) is not StoredPair:
        raise UnsupportedProfile('Explicit stored byte pair required')
    if any(type(x) is not bytes or len(x) > MAX_BYTES for x in (pair.tps_address, pair.mef_xpath)):
        raise UnsupportedProfile('Finite exact byte strings required')
    if not pair.tps_address or not pair.mef_xpath:
        raise UnsupportedProfile('Finite nonempty pair strings required')
    if any(x in pair.tps_address for x in (b'\0', b'\t', b'\n')) or any(x in pair.mef_xpath for x in (b'\0', b'\n')):
        raise UnsupportedProfile('Complete native C-string TAB/LF row grammar required')
    return pair


def _rows(payload, count):
    if not payload or len(payload) > MAX_BYTES or payload[-1:] != b'\n' or b'\0' in payload:
        raise UnsupportedProfile('Complete nonempty LF-terminated byte payload required')
    rows = []
    left = set()
    right = set()
    for line in payload[:-1].split(b'\n'):
        tab = line.find(b'\t')
        if tab < 0:
            raise UnsupportedProfile('Every finite stored row must contain the actual first TAB separator')
        pair = _pair(StoredPair(line[:tab], line[tab + 1:]))
        if pair.tps_address in left or pair.mef_xpath in right:
            # Native SetValue mutates a bidirectional map on repeated keys.
            # This reader refuses those cases instead of inventing that state.
            raise UnsupportedProfile('Duplicate left or right key lies outside immutable finite pair profile')
        left.add(pair.tps_address)
        right.add(pair.mef_xpath)
        rows.append(pair)
    if len(rows) != count:
        raise UnsupportedProfile('Declared row count must match all consumed rows')
    return tuple(rows)


def load_stored_body(wire):
    if type(wire) is not bytes or not 10 <= len(wire) <= MAX_BYTES + 8192:
        raise UnsupportedProfile('Complete bounded type14F body bytes required')
    version, count, size = struct.unpack_from('>HII', wire)
    if version != 1:
        raise UnsupportedProfile('Only actual type14F version1 profile is accepted')
    if not 1 <= count <= MAX_ROWS:
        raise UnsupportedProfile('Nonempty count required; empty Store/Load framing remains unproved')
    if not 1 <= size <= MAX_BYTES + 8192 or len(wire) != 10 + size:
        raise UnsupportedProfile('Exact declared compressed body; no unknown tail, gap or truncation')
    payload, chunks, endian = decode_framed_stream(wire[10:])
    rows = _rows(payload, count)
    return StoredBody(rows, payload, wire, chunks, endian)


def load_named_stored_body(class_name, wire, *, owner_level):
    if type(class_name) is not bytes or class_name != NAME or owner_level != 'formset':
        raise UnsupportedProfile('Exact source descriptor and FormSet object envelope required')
    return load_stored_body(wire)


def typed_raw_body_or_none(wire):
    """App raw-copy classification; None means opaque, never empty/success.

    The caller must first match the exact class name in the parsed FormSet CE
    envelope. Unknown versions and count0 retain the old opaque-object policy.
    Known nonempty version1 bodies must pass every complete body guard.
    """
    if type(wire) is not bytes or len(wire) < 2:
        raise UnsupportedProfile('Complete type14F version header required')
    version = struct.unpack_from('>H', wire)[0]
    if version != 1:
        return None
    if len(wire) < 6:
        raise UnsupportedProfile('Complete type14F version1 count required')
    if struct.unpack_from('>I', wire, 2)[0] == 0:
        return None
    return load_stored_body(wire)


def preserve_stored_body(body):
    if type(body) is not StoredBody or load_stored_body(body.source_body) != body:
        raise UnsupportedProfile('Untampered fully validated complete stored body required')
    return body.source_body


def clone_stored_body(body):
    """Independent byte clone, not native Clone/MoveTo/Load or cache creation."""
    return load_stored_body(bytes(bytearray(preserve_stored_body(body))))


def relocation_evidence(class_name, wire, *, owner_level, source_owner_key, target_owner_key):
    # These byte keys must come from the enclosing parsed source object, not a
    # request claiming a new native owner. Only its file position may change.
    if (type(source_owner_key) is not bytes or not source_owner_key or
            len(source_owner_key) > MAX_BYTES or type(target_owner_key) is not bytes or
            source_owner_key != target_owner_key):
        raise UnsupportedProfile('Retain the exact enclosing source owner; owner reassignment is unproved')
    body = load_named_stored_body(class_name, wire, owner_level=owner_level)
    return {'class_id': CLASS_ID, 'class_name': NAME.decode('ascii'),
            'owner_level': 'formset', 'complete_body_validated': True,
            'stored_rows': len(body.rows), 'all_body_bytes_classified': True,
            'source_body_contains_physical_file_offsets': False,
            'source_body_position_independent': True,
            'preserve_source_body_exact': True,
            'same_source_owner_required': True, 'owner_reassignment_allowed': False,
            'native_cleanup_executed': False, 'native_14D_transfer_executed': False,
            'native_current_cache_verified': False, 'native_clone_executed': False,
            'native_inventory_verified': False, 'native_execution_count': 0}


def encode_owned_body(rows, *, compressed=False):
    """Owned valid fixture framing, not universal native compressor byte parity."""
    if type(rows) is not tuple or not 1 <= len(rows) <= MAX_ROWS or type(compressed) is not bool:
        raise UnsupportedProfile('Finite explicit nonempty owned pairs required')
    for pair in rows:
        _pair(pair)
    # Native Store walks the address index. This independent finite constructor
    # chooses address order; it never reconstructs a live bimap or source owner.
    rows = tuple(sorted(rows, key=lambda row: row.tps_address))
    payload = b''.join(row.tps_address + b'\t' + row.mef_xpath + b'\n' for row in rows)
    _rows(payload, len(rows))
    buffers = Buffers(1000, 2000, 0, 4 if compressed else 0)
    blob = b'\0' + b''.join(emit_selected_block(payload[p:p + 65000], buffers, byte_order='<')
                           for p in range(0, len(payload), 65000))
    wire = struct.pack('>HII', 1, len(rows), len(blob)) + blob
    if load_stored_body(wire).rows != rows:
        raise AssertionError('Owned pair body roundtrip')
    return wire
