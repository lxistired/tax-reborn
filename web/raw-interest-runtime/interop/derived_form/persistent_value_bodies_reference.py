"""Independent finite body readers for two source-bound native value classes.

Only selected big-endian stream scalars are supported. These bodies contain
raw string/ID/index data, without file positions or StringTable handles. They
may be copied to a new byte offset unchanged after complete validation. Native
class allocation, attachment, field creation and destination resolution are
outside this byte-preservation contract.
"""
from dataclasses import dataclass,field
import struct
from .value_form_tail_reference import PersistentObject,ValueFormTail

VALUE_TAG=b'ztbPersistentValueTag'
RECORD_ORDER=b'zcvPersistentRecordOrder'
NAMES=frozenset((VALUE_TAG,RECORD_ORDER))

class UnsupportedBodyProfile(ValueError):pass

@dataclass(frozen=True)
class ValueTagBody:
    text_bytes:bytes
    source_wire:bytes=field(compare=False,repr=False)

    @property
    def native_store_length_written(self):
        # Native Store emits only version1 when the low16 string length is0;
        # Load(version1) unconditionally expects another U16 length.
        return bool(self.text_bytes)

@dataclass(frozen=True)
class RecordOrderBody:
    destination_formset_raw15:bytes
    destination_id:bytes
    destination_index:int
    destination_element:int
    source_wire:bytes=field(compare=False,repr=False)

    @property
    def destination_formset_text(self):
        return self.destination_formset_raw15.split(b'\0',1)[0]

def _bytes(value,label):
    if type(value) is not bytes:raise UnsupportedBodyProfile(label)
    return value

def _uint16(value,label):
    if type(value) is not int or not 0<=value<=65535:raise UnsupportedBodyProfile(label)
    return value

def _object(obj,name):
    if not isinstance(obj,PersistentObject) or obj.group!=2 or obj.class_name!=name:
        raise UnsupportedBodyProfile('Exact native value-object class in group2 required')
    if not 1<=_uint16(obj.first_index,'U16 attachment field')<=65535:
        raise UnsupportedBodyProfile('Native field attachment requires a nonzero field index')
    _uint16(obj.second_index,'U16 attachment element')
    if type(obj.attachment_id) is not bytes or len(obj.attachment_id)!=32:
        raise UnsupportedBodyProfile('Complete32-byte attachment ID required')
    return _bytes(obj.opaque_payload,'Complete object body bytes required')

def parse_value_tag_body(wire):
    """Version1+U16 length+exact bytes; retain an explicit zero-length read.

    A short2-byte native empty Store is refused because the matching Load would
    consume beyond this object. An explicit4-byte version1/length0 can be read
    and preserved, but is not called native writer parity. NUL text is refused
    because native Assign(char*) would discard its suffix.
    """
    _bytes(wire,'Complete value-tag body bytes required')
    if len(wire)<4:raise UnsupportedBodyProfile('Version1 requires its complete U16 length')
    version,size=struct.unpack_from('>HH',wire)
    if version!=1:raise UnsupportedBodyProfile('Only source-proven value-tag version1 supported')
    if len(wire)!=4+size:raise UnsupportedBodyProfile('Value-tag length must consume the exact body')
    text=wire[4:]
    if b'\0' in text:raise UnsupportedBodyProfile('Value-tag embedded NUL needs separate native normalization handling')
    return ValueTagBody(text,wire)

def load_value_tag_body(obj):return parse_value_tag_body(_object(obj,VALUE_TAG))

def encode_nonempty_value_tag_body(text):
    _bytes(text,'Explicit raw text bytes required')
    if not 1<=len(text)<=65535 or b'\0' in text:
        raise UnsupportedBodyProfile('Nonempty NUL-free text within native U16 length required')
    return struct.pack('>HH',1,len(text))+text

def _stream_id(wire,cursor):
    if cursor>=len(wire):raise UnsupportedBodyProfile('Complete destination stream ID required')
    first=wire[cursor]
    if first==255:
        end=cursor+33
        if end>len(wire):raise UnsupportedBodyProfile('Complete FF/full32 destination ID required')
        return wire[cursor+1:end],end
    if first<9:
        end=cursor+1+first
        if end>len(wire):raise UnsupportedBodyProfile('Complete short destination ID required')
        return wire[cursor+1:end].ljust(32,b' '),end
    end=cursor+8
    if end>len(wire):raise UnsupportedBodyProfile('Complete legacy8 destination ID required')
    return wire[cursor:end].ljust(32,b' '),end

def parse_record_order_body(wire):
    """Marker16+15 raw FormSetID bytes+ReadID+two U16 indices.

    Native Store uses strcpy into a16-byte local then writes15 bytes. Bytes
    after the first NUL therefore remain raw source data, never zero-normalized.
    Destination ID/category resolution and row creation are not implemented.
    """
    _bytes(wire,'Complete record-order body bytes required')
    if len(wire)<21 or wire[0]!=16:
        raise UnsupportedBodyProfile('Record-order marker16 and complete fixed15-byte FormSetID required')
    destination,cursor=_stream_id(wire,16)
    if cursor+4!=len(wire):raise UnsupportedBodyProfile('Destination ID and two U16 indices must consume the exact body')
    index,element=struct.unpack_from('>HH',wire,cursor)
    return RecordOrderBody(wire[1:16],destination,index,element,wire)

def load_record_order_body(obj):return parse_record_order_body(_object(obj,RECORD_ORDER))

def encode_canonical_record_order_body(formset_text,destination_id,index,element):
    _bytes(formset_text,'Explicit FormSetID bytes required')
    _bytes(destination_id,'Explicit complete32-byte destination ID required')
    if len(formset_text)>15 or b'\0' in formset_text or len(destination_id)!=32:
        raise UnsupportedBodyProfile('FormSetID at most15 non-NUL bytes and exact32-byte destination ID required')
    _uint16(index,'U16 destination index');_uint16(element,'U16 destination element')
    # Padding here belongs to this independent caller-owned encoder. Native
    # stack padding is not claimed deterministic or reproduced by this choice.
    return b'\x10'+formset_text.ljust(15,b'\0')+b'\xff'+destination_id+struct.pack('>HH',index,element)

def store_preserved_body(body):
    if isinstance(body,ValueTagBody):original=parse_value_tag_body(body.source_wire)
    elif isinstance(body,RecordOrderBody):original=parse_record_order_body(body.source_wire)
    else:raise UnsupportedBodyProfile('Explicit complete parsed typed body required')
    if original!=body:raise UnsupportedBodyProfile('Typed body mutation cannot be silently discarded')
    return body.source_wire

def proven_value_relocation_classes(tail):
    """Validate every instance before granting a class-wide raw-copy permission.

    Unknown classes are not granted permission. A known class in the wrong
    attachment group, or with malformed body, is refused even when another
    instance with the same name was valid. No caller class-name assertion is
    accepted as evidence.
    """
    if not isinstance(tail,ValueFormTail):raise UnsupportedBodyProfile('Explicit loaded derived tail required')
    found=set()
    for group in tail.groups:
        for obj in group:
            if obj.class_name==VALUE_TAG:load_value_tag_body(obj);found.add(VALUE_TAG)
            elif obj.class_name==RECORD_ORDER:load_record_order_body(obj);found.add(RECORD_ORDER)
    return frozenset(found)
