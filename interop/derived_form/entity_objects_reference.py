"""Actual CD paired map / CC Entity persistent-object envelope, raw body I/O.

Only source-bound147 canonical UUID and146 exact U8-length raw bodies and14B version3/4 framed metadata can move.
All other Entity body classes remain opaque and require unchanged stream positions.
No native factory, event, UUID refresh or metadata set_value/fixup is executed.
"""
from dataclasses import dataclass
import struct,re
from ..form_core.field_template_reference import UnsupportedProfile
from .legacy_entity_uuid_body_reference import NAME as LEGACY_UUID_NAME,load_legacy_uuid_body
from .metadata_entity_body_reference import NAME as ENTITY_METADATA_NAME,load_metadata_entity_body

UUID_NAME=b'zccPersistentEntityUUID'
UUID_PATTERN=re.compile(rb'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z')

@dataclass(frozen=True)
class EntityObject:
 class_name:bytes
 body:bytes
 source_wire:bytes
 source_record_position:int

@dataclass(frozen=True)
class PersistentObjects:
 objects:tuple
 capacity:int
 used:int
 offsets:tuple
 source_base_position:int
 source_wire:bytes

@dataclass(frozen=True)
class LoadedObjects:
 objects_list:PersistentObjects
 consumed:int

def _u32(value):
 if type(value)is not int or not 0<=value<=0xffffffff:raise UnsupportedProfile('Actual unsigned32 persistent-list position')
 return value

def typed_body(class_name,body):
 if class_name==ENTITY_METADATA_NAME:
  # Unmodeled native original1/2 and unknown versions stay opaque, never movable.
  if len(body)>=2 and struct.unpack_from('>H',body)[0]not in(3,4):return None
  return load_metadata_entity_body(body)
 if class_name==LEGACY_UUID_NAME:return load_legacy_uuid_body(body)
 if class_name==UUID_NAME:
  if type(body)is not bytes or len(body)!=37 or body[0]!=36 or not UUID_PATTERN.fullmatch(body[1:]):raise UnsupportedProfile('Canonical complete Entity147 UUID body; native normalization/generation not supplied')
  return body[1:]
 return None

def load_objects_bytes(wire,position=0,*,base_position=None):
 if type(wire)is not bytes or type(position)is not int or not 0<=position<=len(wire):raise UnsupportedProfile('Exact single buffer and CD position')
 base=position if base_position is None else _u32(base_position);_u32(base)
 start=position
 if position+5>len(wire)or wire[position]!=0xcd:raise UnsupportedProfile('Declared derived Entity requires actual CD paired map')
 capacity,used=struct.unpack_from('>HH',wire,position+1);position+=5
 if not 1<=capacity<=65535 or used>capacity or used%2:raise UnsupportedProfile('Finite valid CD capacity/even used (native oddused1FB)')
 if position+capacity*4>len(wire):raise UnsupportedProfile('Complete CD little-endian offsets')
 offsets=struct.unpack_from('<'+'I'*capacity,wire,position);position+=capacity*4;expected=position;objects=[]
 for i in range(0,used,2):
  a,b=start+offsets[i],start+offsets[i+1]
  if a!=expected or b<a+2 or b>len(wire):raise UnsupportedProfile('Finite contiguous CC record pairs; no gaps/overlap/wrap guessed')
  record=wire[a:b];size=record[1]
  if record[0]!=0xcc or not 1<=size<=100 or size+2>len(record):raise UnsupportedProfile('Actual CC and complete<=100-byte class name (native1FE)')
  name=record[2:2+size]
  if b'\0'in name:raise UnsupportedProfile('Finite nonempty C class name; embeddedNUL not normalized')
  body=record[2+size:];typed_body(name,body)
  objects.append(EntityObject(name,body,record,base+a-start));expected=b
 end=expected
 objects_list=PersistentObjects(tuple(objects),capacity,used,offsets,base,wire[start:end])
 return LoadedObjects(objects_list,end-start)

def load_objects(wire,*,base_position=0):
 loaded=load_objects_bytes(wire,base_position=base_position)
 if loaded.consumed!=len(wire):raise UnsupportedProfile('Entire selected CD objects_list must be consumed')
 return loaded.objects_list

def preserve_objects(objects_list,*,base_position=None):
 if not isinstance(objects_list,PersistentObjects):raise UnsupportedProfile('Explicit loaded Entity PersistentObjects')
 original=load_objects(objects_list.source_wire,base_position=objects_list.source_base_position)
 if original!=objects_list:raise UnsupportedProfile('Source Entity persistent-object inventory/body may not silently change')
 target=objects_list.source_base_position if base_position is None else _u32(base_position)
 if target!=objects_list.source_base_position:
  for obj in objects_list.objects:
   if typed_body(obj.class_name,obj.body)is None:raise UnsupportedProfile('Unknown Entity persistent-object relocation is not authorized')
 return objects_list.source_wire

def build_owned_objects(records,*,base_position=0,capacity=None,unused_offsets=None):
 """Owned fixture construction; not native object allocation or list creation."""
 _u32(base_position)
 if type(records)is not tuple or len(records)>32767:raise UnsupportedProfile('Explicit own paired-map inventory')
 used=len(records)*2;cap=max(1,used)if capacity is None else capacity
 if type(cap)is not int or not max(1,used)<=cap<=65535:raise UnsupportedProfile('Finite own CD capacity')
 cursor=5+cap*4;offsets=[];parts=[]
 for name,body in records:
  if type(name)is not bytes or not 1<=len(name)<=100 or b'\0'in name or type(body)is not bytes:raise UnsupportedProfile('Exact own CC name/body')
  typed_body(name,body);record=b'\xcc'+bytes([len(name)])+name+body
  offsets.extend((cursor,cursor+len(record)));parts.append(record);cursor+=len(record)
  if base_position+cursor>0xffffffff:raise UnsupportedProfile('Finite CD own absolute-position overflow')
 unused=(0xffffffff,)*(cap-used)if unused_offsets is None else unused_offsets
 if type(unused)is not tuple or len(unused)!=cap-used:raise UnsupportedProfile('Explicit own unused offsets')
 for v in unused:_u32(v)
 wire=b'\xcd'+struct.pack('>HH',cap,used)+struct.pack('<'+'I'*cap,*(tuple(offsets)+unused))+b''.join(parts)
 return load_objects(wire,base_position=base_position)

def persistent_objects_snapshot(objects_list):
 """JSON facts; omit only absolute runtime positions, retain every wire byte."""
 if objects_list is None:return None
 preserve_objects(objects_list)
 return {'capacity':objects_list.capacity,'used':objects_list.used,'relative_offsets':list(objects_list.offsets),
         'wire_hex':objects_list.source_wire.hex(),
         'objects':[{'class_name_hex':obj.class_name.hex(),'body_hex':obj.body.hex(),'record_wire_hex':obj.source_wire.hex()}for obj in objects_list.objects]}
