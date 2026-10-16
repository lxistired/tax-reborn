"""Independent E1 base/value-table headers; factory choice is caller supplied.

The selected scalar order is big endian. E1 has no class discriminator.
ValueTable.Load reads the final U16 only for EntityHeader.schema >= 13.
The observed ValueTable.Store always writes it; this preserving helper refuses
legacy value-table stores rather than claiming a schema<13 round trip.
Rows remain in the containing form's value hash. No row allocation is implied.
"""
from dataclasses import dataclass, field
import struct

class UnsupportedTableProfile(ValueError):
    pass

@dataclass(frozen=True)
class TableHeader:
    identifier: bytes
    word28: int = 0
    word2a: int = 0
    last_used_record_index: object = None
    metadata: dict = field(default_factory=dict, compare=False, repr=False)


def _u16(value):
    if type(value) is not int or not 0 <= value <= 65535:
        raise UnsupportedTableProfile('Explicit unsigned 16-bit metadata required')
    return value


def _schema(value):
    if type(value) is not int or not 0 <= value <= 255:
        raise UnsupportedTableProfile('EntityHeader schema byte required')
    return value


def _kind(value):
    if value not in ('base_e1', 'value_table'):
        raise UnsupportedTableProfile('Caller must declare base_e1 or value_table factory')
    return value


def _identifier(value):
    if type(value) is not bytes or len(value) > 32 or b'\0' in value:
        raise UnsupportedTableProfile('Selected table ID: 0..32 non-NUL bytes')
    return value


def load_table_header(wire, *, entity_schema, table_kind):
    """Consume exactly one indexed E1 record using a declared form factory.

    entity_schema is the already-loaded C0 EntityHeader.schema, not a tax year
    or a FormSet checksum. A legacy value-table load returns index zero as the
    native branch does, but cannot be re-stored by this preserving helper.
    """
    schema = _schema(entity_schema)
    kind = _kind(table_kind)
    if type(wire) is not bytes or len(wire) < 3 or wire[0] != 0xe1:
        raise UnsupportedTableProfile('Complete E1 header required')
    length = struct.unpack_from('>H', wire, 1)[0]
    if length > 32 or 3 + length > len(wire):
        raise UnsupportedTableProfile('Complete table ID in selected 0..32 range')
    identifier = _identifier(wire[3:3 + length])
    cursor = 3 + length
    extension = 2 if kind == 'value_table' and schema >= 13 else 0
    if len(wire) != cursor + 4 + extension:
        raise UnsupportedTableProfile('Exact declared table header boundary required')
    first, last = struct.unpack_from('>HH', wire, cursor)
    saved = None
    if kind == 'value_table':
        saved = struct.unpack_from('>H', wire, cursor + 4)[0] if extension else 0
    return TableHeader(identifier, first, last, saved, {
        'source_wire': wire, 'source_entity_schema': schema,
        'declared_table_kind': kind, 'value_table_extension_consumed': bool(extension),
    })


def store_table_header(table, *, entity_schema, table_kind):
    """Preserve supplied metadata; no native Build/row-used scan is simulated.

    The saved index is preserved verbatim. Native Store recomputes the index
    from prepared runtime records; callers that create/delete records need
    that separate context before changing the saved index.
    """
    schema = _schema(entity_schema)
    kind = _kind(table_kind)
    if not isinstance(table, TableHeader):
        raise UnsupportedTableProfile('Explicit TableHeader required')
    identifier = _identifier(table.identifier)
    result = b'\xe1' + struct.pack('>H', len(identifier)) + identifier
    result += struct.pack('>HH', _u16(table.word28), _u16(table.word2a))
    if kind == 'base_e1':
        if table.last_used_record_index is not None:
            raise UnsupportedTableProfile('base_e1 cannot silently discard a value-table index')
        return result
    if schema < 13:
        raise UnsupportedTableProfile('Native Store always adds U16; legacy preserving store unsupported')
    return result + struct.pack('>H', _u16(table.last_used_record_index))


def load_value_table_header(wire, *, entity_schema):
    return load_table_header(wire, entity_schema=entity_schema, table_kind='value_table')


def store_preserved_value_table_header(table, *, entity_schema):
    return store_table_header(table, entity_schema=entity_schema, table_kind='value_table')
