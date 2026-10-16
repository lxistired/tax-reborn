"""Actual CF paired map / CE FormSet persistent-object envelope, raw body I/O.

Only source-bound148 UUID,151 metadata and finite nonempty version1 type14F
stored instance-map bodies can move, retaining the same parsed source owner.
All other body classes remain opaque and require unchanged stream positions.
No native factory, event, UUID refresh or metadata set_value/fixup is executed.
"""
from dataclasses import dataclass
import struct,re
from ..form_core.metadata_formset_body_reference import NAME as METADATA_NAME,load_named_metadata_body,preserve_metadata_body
from ..form_core.instance_map_formset_body_reference import NAME as INSTANCE_MAP_NAME,typed_raw_body_or_none
from ..form_core.field_template_reference import UnsupportedProfile

UUID_NAME=b'zccPersistentFormSetUUID'
UUID_PATTERN=re.compile(rb'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z')

@dataclass(frozen=True)
class Attribute:
 class_name:bytes
 body:bytes
 source_wire:bytes
 source_record_position:int

@dataclass(frozen=True)
class AttributeList:
 objects:tuple
 capacity:int
 used:int
 offsets:tuple
 source_base_position:int
 source_wire:bytes

@dataclass(frozen=True)
class LoadedAttributes:
 attributes:AttributeList
 consumed:int

def _u32(value):
 if type(value)is not int or not 0<=value<=0xffffffff:raise UnsupportedProfile('Actual unsigned32 persistent-list position')
 return value

def typed_body(class_name,body):
 if class_name==INSTANCE_MAP_NAME:return typed_raw_body_or_none(body)
 if class_name==METADATA_NAME:return load_named_metadata_body(class_name,body)
 if class_name==UUID_NAME:
  if type(body)is not bytes or len(body)!=37 or body[0]!=36 or not UUID_PATTERN.fullmatch(body[1:]):raise UnsupportedProfile('Canonical complete FormSet148 UUID body; native normalization/generation not supplied')
  return body[1:]
 return None

def load_attributes_bytes(wire,position=0,*,base_position=None):
 if type(wire)is not bytes or type(position)is not int or not 0<=position<=len(wire):raise UnsupportedProfile('Exact single buffer and CF position')
 base=position if base_position is None else _u32(base_position);_u32(base)
 start=position
 if position+5>len(wire)or wire[position]!=0xcf:raise UnsupportedProfile('Declared derived FormSet requires actual CF paired map')
 capacity,used=struct.unpack_from('>HH',wire,position+1);position+=5
 if not 1<=capacity<=65535 or used>capacity or used%2:raise UnsupportedProfile('Finite valid CF capacity/even used (native oddused1FB)')
 if position+capacity*4>len(wire):raise UnsupportedProfile('Complete CF little-endian offsets')
 offsets=struct.unpack_from('<'+'I'*capacity,wire,position);position+=capacity*4;expected=position;objects=[]
 for i in range(0,used,2):
  a,b=start+offsets[i],start+offsets[i+1]
  if a!=expected or b<a+2 or b>len(wire):raise UnsupportedProfile('Finite contiguous CE record pairs; no gaps/overlap/wrap guessed')
  record=wire[a:b];size=record[1]
  if record[0]!=0xce or not 1<=size<=100 or size+2>len(record):raise UnsupportedProfile('Actual CE andcomplete<=100-byte class name (native23F)')
  name=record[2:2+size]
  if b'\0'in name:raise UnsupportedProfile('Finite nonempty C class name; embeddedNUL not normalized')
  body=record[2+size:];typed_body(name,body)
  objects.append(Attribute(name,body,record,base+a-start));expected=b
 end=expected
 attributes=AttributeList(tuple(objects),capacity,used,offsets,base,wire[start:end])
 return LoadedAttributes(attributes,end-start)

def load_attributes(wire,*,base_position=0):
 loaded=load_attributes_bytes(wire,base_position=base_position)
 if loaded.consumed!=len(wire):raise UnsupportedProfile('Entire selected CF attributes must be consumed')
 return loaded.attributes

def preserve_attributes(attributes,*,base_position=None):
 if not isinstance(attributes,AttributeList):raise UnsupportedProfile('Explicit loaded FormSet AttributeList')
 original=load_attributes(attributes.source_wire,base_position=attributes.source_base_position)
 if original!=attributes:raise UnsupportedProfile('Source FormSet persistent-object inventory/body may not silently change')
 target=attributes.source_base_position if base_position is None else _u32(base_position)
 if target!=attributes.source_base_position:
  for obj in attributes.objects:
   if typed_body(obj.class_name,obj.body)is None:raise UnsupportedProfile('Unknown FormSet persistent-object relocation is not authorized')
 return attributes.source_wire

def build_owned_attributes(records,*,base_position=0,capacity=None,unused_offsets=None):
 """Owned fixture construction; not native object allocation or list creation."""
 _u32(base_position)
 if type(records)is not tuple or len(records)>32767:raise UnsupportedProfile('Explicit own paired-map inventory')
 used=len(records)*2;cap=max(1,used)if capacity is None else capacity
 if type(cap)is not int or not max(1,used)<=cap<=65535:raise UnsupportedProfile('Finite own CF capacity')
 cursor=5+cap*4;offsets=[];parts=[]
 for name,body in records:
  if type(name)is not bytes or not 1<=len(name)<=100 or b'\0'in name or type(body)is not bytes:raise UnsupportedProfile('Exact own CE name/body')
  typed_body(name,body);record=b'\xce'+bytes([len(name)])+name+body
  offsets.extend((cursor,cursor+len(record)));parts.append(record);cursor+=len(record)
  if base_position+cursor>0xffffffff:raise UnsupportedProfile('Finite CF own absolute-position overflow')
 unused=(0xffffffff,)*(cap-used)if unused_offsets is None else unused_offsets
 if type(unused)is not tuple or len(unused)!=cap-used:raise UnsupportedProfile('Explicit own unused offsets')
 for v in unused:_u32(v)
 wire=b'\xcf'+struct.pack('>HH',cap,used)+struct.pack('<'+'I'*cap,*(tuple(offsets)+unused))+b''.join(parts)
 return load_attributes(wire,base_position=base_position)
