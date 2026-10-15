"""Independent bounded reader for already obtained template attributes1900/1901.

Resource/carrier selection, version matching, and native runtime registration
are external. The optional template byte swap is separate from .tax endian
state. Every source ID byte and its six metadata bytes are retained.
"""
from dataclasses import dataclass
import struct

class UnsupportedProfile(ValueError):
    pass

def read_id(wire,position):
    if position<0 or position>=len(wire):raise UnsupportedProfile('truncated ID')
    marker=wire[position]
    if marker==255:start,size,end=position+1,32,position+33
    elif marker<9:start,size,end=position+1,marker,position+1+marker
    else:start,size,end=position,8,position+8
    if end>len(wire):raise UnsupportedProfile('truncated ID')
    return wire[start:start+size].ljust(32,b' '),end

@dataclass(frozen=True)
class DeclaredField:
    ordinal: int
    identifier: bytes
    kind: int
    format: int
    attributes: int
    hidden: bool
    source_encoded_id: bytes
    source_metadata: bytes

@dataclass(frozen=True)
class FieldSegment:
    fields: tuple[DeclaredField,...]
    consumed: int
    source_payload: bytes

def parse_field_payload(wire,*,template_swap=False,hidden=False,start_ordinal=1,
                        require_all=True):
    if type(wire) is not bytes or len(wire)<2:raise UnsupportedProfile('complete field payload required')
    if type(template_swap) is not bool or type(hidden) is not bool:raise UnsupportedProfile('explicit template flags required')
    if type(start_ordinal) is not int or not 1<=start_ordinal<=65535:raise UnsupportedProfile('one-based U16 ordinal required')
    endian='>' if template_swap else '<';count=struct.unpack_from(endian+'H',wire)[0]
    if start_ordinal+count-1>65535:raise UnsupportedProfile('finite ordinal wrap refused')
    p=2;fields=[]
    for offset in range(count):
        begin=p;identifier,p=read_id(wire,p);encoded=wire[begin:p]
        if p+6>len(wire):raise UnsupportedProfile('truncated field metadata')
        raw=wire[p:p+6];kind,fmt,attributes=struct.unpack(endian+'BBI',raw);p+=6
        fields.append(DeclaredField(start_ordinal+offset,identifier,kind,fmt,attributes,hidden,encoded,raw))
    if require_all and p!=len(wire):raise UnsupportedProfile('unconsumed template payload')
    return FieldSegment(tuple(fields),p,wire)

@dataclass(frozen=True)
class FieldTemplate:
    visible: FieldSegment|None
    hidden: FieldSegment|None
    template_swap: bool
    @property
    def fields(self):
        return (self.visible.fields if self.visible else ())+(self.hidden.fields if self.hidden else ())
    def find_field(self,identifier):
        if type(identifier) is not bytes or len(identifier)!=32:raise UnsupportedProfile('fixed32 ID required')
        return next((x.ordinal for x in self.fields if x.identifier==identifier),0)
    def get_field(self,ordinal):
        if type(ordinal) is not int or not 0<=ordinal<=65535:raise UnsupportedProfile('U16 index required')
        return self.fields[ordinal-1] if 1<=ordinal<=len(self.fields) else None
    def context_field_ids(self):
        """App token mapping; native raw IDs remain available in .fields.

        Current document profile supports printable non-space ASCII tokens.
        Ambiguous or unrepresentable IDs block conversion instead of dropping.
        """
        result={};seen=set()
        for f in self.fields:
            token=f.identifier.rstrip(b' ')
            if not token or any(c<33 or c>126 for c in token) or token in seen:
                raise UnsupportedProfile('ambiguous or unsupported context ID')
            result[f.ordinal]=token;seen.add(token)
        return result

def load_field_template(visible_payload,hidden_payload,*,template_swap=False):
    if type(template_swap) is not bool:raise UnsupportedProfile('explicit template byte swap required')
    visible=parse_field_payload(visible_payload,template_swap=template_swap) if visible_payload is not None else None
    count=len(visible.fields) if visible else 0
    if count==65535 and hidden_payload is not None:
        # No subsequent index can be represented; an empty hidden block is valid.
        if hidden_payload!=(b'\0\0'):raise UnsupportedProfile('finite ordinal wrap refused')
        hidden=FieldSegment((),2,hidden_payload)
    else:
        hidden=parse_field_payload(hidden_payload,template_swap=template_swap,hidden=True,start_ordinal=count+1) if hidden_payload is not None else None
    return FieldTemplate(visible,hidden,template_swap)
