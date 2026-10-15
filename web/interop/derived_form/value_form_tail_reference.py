"""Independent modern ValueForm derived tail with opaque payload preservation.

Selected schema18/release100/share0/swapfalse: D2 field map, D1/DE/DF paired
StreamMaps for form/record/value objects. No native factories or object bodies
are executed. Exact raw blocks decode locally; compressed blocks require the
already-source-checked method4/CRC decoder callback. Original wire is retained.
"""
from dataclasses import dataclass, field
import struct

class UnsupportedTailProfile(ValueError): pass

@dataclass(frozen=True)
class FieldEntry:
    identifier: bytes                 # full32-byte native ID, including padding
    source_field_index: int

@dataclass(frozen=True)
class FieldMap:
    entries: tuple
    decoded_payload: bytes
    padding: bytes
    source_wire: bytes = field(compare=False, repr=False)

@dataclass(frozen=True)
class PersistentObject:
    group: int                        # 0=form,1=record,2=value
    class_name: bytes
    first_index: object = None         # record:table; value:field
    second_index: object = None        # record:record; value:element
    attachment_id: object = None
    opaque_payload: bytes = b''
    source_wire: bytes = field(default=b'', compare=False, repr=False)

@dataclass(frozen=True)
class ValueFormTail:
    field_map: FieldMap
    groups: tuple
    source_base_position: int
    source_wire: bytes = field(compare=False, repr=False)
    metadata: dict = field(default_factory=dict, compare=False, repr=False)

MAP_MARKERS = (0xd1, 0xde, 0xdf)
OBJECT_MARKERS = (0xd0, 0xdd, 0xdb)


def _integer(value, maximum, label):
    if type(value) is not int or not 0 <= value <= maximum:
        raise UnsupportedTailProfile(label)
    return value


def _profile(entity_schema, entity_release, share_status):
    if (entity_schema, entity_release, share_status) != (18, 100, 0) or any(
        type(value) is not int for value in (entity_schema, entity_release, share_status)):
        raise UnsupportedTailProfile('Selected Entity schema18/release100/share0 required')


def _memory_id(payload, cursor):
    if cursor >= len(payload): raise UnsupportedTailProfile('Complete field memory-ID')
    first = payload[cursor]
    if first == 255:
        end = cursor + 33
        if end > len(payload): raise UnsupportedTailProfile('Complete FF/32-byte field ID')
        return payload[cursor + 1:end], end
    if first < 9:
        end = cursor + 1 + first
        if end > len(payload): raise UnsupportedTailProfile('Complete short field ID')
        return payload[cursor + 1:end].ljust(32, b' '), end
    end = cursor + 8
    if end > len(payload): raise UnsupportedTailProfile('Complete legacy8-byte field ID')
    return payload[cursor:end].ljust(32, b' '), end


def raw_frame_decoder(wire, expected):
    """Only uncompressed0F; F0 requires the existing method4/CRC implementation."""
    if type(wire) is not bytes or len(wire) < 5 or wire[0] != 0x0f:
        raise UnsupportedTailProfile('F0 requires explicit source-checked frame decoder')
    size = struct.unpack_from('>I', wire, 1)[0]
    if size != expected or len(wire) < 5 + size:
        raise UnsupportedTailProfile('Complete raw frame with exact decoded length')
    return wire[5:5 + size], 5 + size


def _load_field_map(wire, decoder):
    if len(wire) < 3 or wire[0] != 0xd2:
        raise UnsupportedTailProfile('D2 field-map header required')
    count = struct.unpack_from('>H', wire, 1)[0]
    cursor = 3
    if count == 0: return FieldMap((), b'', b'', wire[:cursor]), cursor
    if len(wire) < 7: raise UnsupportedTailProfile('Modern field-map decoded length')
    total = struct.unpack_from('>I', wire, 3)[0]
    if not count * 3 <= total <= count * 35:
        raise UnsupportedTailProfile('Selected bounded field-map decoded bytes3..35 per entry')
    cursor = 7
    remaining = total
    chunks = []
    while remaining:
        expected = min(remaining, 65000)
        if cursor + 5 > len(wire) or wire[cursor] not in (0x0f, 0xf0):
            raise UnsupportedTailProfile('Complete selected0F/F0 field-map frame')
        encoded = struct.unpack_from('>I', wire, cursor + 1)[0]
        header = 5 if wire[cursor] == 0x0f else 7
        if encoded > 65000 or cursor + header + encoded > len(wire):
            raise UnsupportedTailProfile('Field-map frame exceeds complete native65000 bound')
        frame = wire[cursor:cursor + header + encoded]
        data, consumed = decoder(frame, expected)
        if type(data) is not bytes or len(data) != expected or consumed != len(frame):
            raise UnsupportedTailProfile('Decoder must verify frame/CRC and exact decoded size')
        chunks.append(data); cursor += consumed; remaining -= expected
    payload = b''.join(chunks)
    at = 0; entries = []
    for _ in range(count):
        identifier, at = _memory_id(payload, at)
        if at + 2 > len(payload): raise UnsupportedTailProfile('Complete rawLE field ordinal')
        ordinal = struct.unpack_from('<H', payload, at)[0]; at += 2
        entries.append(FieldEntry(identifier, ordinal))
    return FieldMap(tuple(entries), payload, payload[at:], wire[:cursor]), cursor


def _stream_id(wire, cursor):
    # Stream ReadID and memory ReadID share FF/full32, short0..8 and legacy8
    # wire branches. This is not E1's separately written U16-length ID.
    return _memory_id(wire, cursor)


def _object(wire, group):
    if len(wire) < 2 or wire[0] != OBJECT_MARKERS[group]:
        raise UnsupportedTailProfile('Object tag must match its declared paired-map group')
    size = wire[1]
    if size > 100 or 2 + size > len(wire):
        raise UnsupportedTailProfile('Complete class name of at most100 bytes')
    name = wire[2:2 + size]
    if not name or b'\0' in name:
        raise UnsupportedTailProfile('Explicit nonempty non-NUL class name')
    cursor = 2 + size
    a = b = attachment = None
    if group:
        if cursor + 4 > len(wire): raise UnsupportedTailProfile('Complete object attachment indices')
        a, b = struct.unpack_from('>HH', wire, cursor); cursor += 4
        attachment, cursor = _stream_id(wire, cursor)
    return PersistentObject(group, name, a, b, attachment, wire[cursor:], wire)


def _load_group(wire, cursor, group, maximum):
    start = cursor
    if cursor + 5 > len(wire) or wire[cursor] != MAP_MARKERS[group]:
        raise UnsupportedTailProfile('Modern D1/DE/DF maps in form/record/value order')
    capacity, used = struct.unpack_from('>HH', wire, cursor + 1)
    if capacity < 1 or used > capacity or used % 2 or used // 2 > maximum:
        raise UnsupportedTailProfile('Bounded paired StreamMap capacity/used count')
    cursor += 5
    if cursor + capacity * 4 > len(wire): raise UnsupportedTailProfile('Complete LE map-offset array')
    offsets = struct.unpack_from('<' + 'I' * capacity, wire, cursor)
    cursor += capacity * 4
    header_end = cursor
    objects = []; expected_start = cursor
    for index in range(0, used, 2):
        a, b = start + offsets[index], start + offsets[index + 1]
        if a != expected_start or b < a or b > len(wire):
            raise UnsupportedTailProfile('Contiguous complete object pairs; no gaps/overlap/wrapping')
        objects.append(_object(wire[a:b], group)); expected_start = b
    end = expected_start if used else header_end
    return tuple(objects), end, dict(capacity=capacity, used=used,
        unused_raw_offsets=tuple(offsets[used:]), source_relative_span=(start, end))


def load_value_form_tail(wire, *, entity_schema=18, entity_release=100,
                         share_status=0, base_position=0,
                         decode_frame=raw_frame_decoder, max_objects=32767):
    """Consume one entire derived tail after BaseForm, from a single byte buffer.

    Object class factories/semantic loaders are deliberately not invoked. The
    source attachment IDs/indices and every opaque body byte remain retained.
    """
    _profile(entity_schema, entity_release, share_status)
    _integer(base_position, 0xffffffff, 'Unsigned32 tail base position')
    _integer(max_objects, 32767, 'Paired-U16 map object bound')
    if type(wire) is not bytes or not callable(decode_frame):
        raise UnsupportedTailProfile('Explicit byte buffer and frame decoder')
    field_map, cursor = _load_field_map(wire, decode_frame)
    groups = []; reports = []
    for group in range(3):
        objects, cursor, report = _load_group(wire, cursor, group, max_objects)
        groups.append(objects); reports.append(report)
    if cursor != len(wire): raise UnsupportedTailProfile('Entire selected derived tail must be consumed')
    return ValueFormTail(field_map, tuple(groups), base_position, wire,
        dict(entity_schema=entity_schema, entity_release=entity_release,
             share_status=share_status, map_reports=tuple(reports),
             opaque_object_payloads=True, native_execution_count=0))


def store_preserved_value_form_tail(tail, *, base_position=None,
                                   decode_frame=raw_frame_decoder,
                                   relocatable_classes=frozenset()):
    """Emit retained source bytes only after structural equality readback.

    Unknown object bodies may carry position-sensitive state. Moving a nonempty
    tail therefore requires explicit caller knowledge of every class being moved.
    This allowlist is caller-owned knowledge, not a native registry inference.
    Field/object mutations are refused; object creation is a separate contract.
    """
    if not isinstance(tail, ValueFormTail): raise UnsupportedTailProfile('Explicit loaded ValueFormTail')
    target = tail.source_base_position if base_position is None else base_position
    _integer(target, 0xffffffff, 'Unsigned32 tail base position')
    original = load_value_form_tail(tail.source_wire, base_position=tail.source_base_position,
                                   decode_frame=decode_frame)
    if original != tail: raise UnsupportedTailProfile('Mutated field-map/object metadata or body cannot be silently ignored')
    if target != tail.source_base_position:
        if not isinstance(relocatable_classes, (set, frozenset)):
            raise UnsupportedTailProfile('Explicit caller-owned relocatable-class set')
        if any(obj.class_name not in relocatable_classes for group in tail.groups for obj in group):
            raise UnsupportedTailProfile('Opaque object relocation requires class-specific source evidence or same base')
    return tail.source_wire


def load_value_form_tail_bytes(wire, *, tail_position, record_limit=None,
                               entity_schema=18, entity_release=100, share_status=0,
                               decode_frame=raw_frame_decoder, max_objects=32767):
    """Read the tail directly from one complete document/form byte buffer.

    tail_position is the consumed end returned by the source-bound BaseForm
    parser; record_limit is the selected form's StreamMap limit. No section
    sidecar or inferred form class is accepted.
    """
    if type(wire) is not bytes: raise UnsupportedTailProfile('One complete byte buffer required')
    end = len(wire) if record_limit is None else record_limit
    _integer(tail_position, len(wire), 'Existing tail byte position')
    _integer(end, len(wire), 'Existing form record limit')
    if end < tail_position: raise UnsupportedTailProfile('Ordered selected form tail bounds')
    return load_value_form_tail(wire[tail_position:end], entity_schema=entity_schema,
        entity_release=entity_release, share_status=share_status, base_position=tail_position,
        decode_frame=decode_frame, max_objects=max_objects)
