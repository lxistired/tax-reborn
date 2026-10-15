"""Actual14B Entity metadata raw body: version3 framed rows / version4 marker.

This is a separate class from FormSet151. Shared compression and line grammar
are source-bound to their actual common utility calls. Native tree set_value,
model cleanup and migration into FormSets are never executed. Raw ordered rows
and all framing bytes remain distinct from active metadata values.
"""
from dataclasses import dataclass
import struct
from ..form_core.metadata_formset_body_reference import (Row,Chunk,MAX_BYTES,MAX_ROWS,
 decode_framed_stream,parse_row_payload,encode_owned_metadata_body)
from ..form_core.cx_string_wire_reference import UnsupportedProfile
NAME=b'MetaDataKeyValuePersistentObject'
CLASS_ID=0x14b

@dataclass(frozen=True)
class EntityMetadataBody:
 version:int
 rows:tuple
 skipped_lines:tuple
 payload:bytes
 chunks:tuple
 stream_endian:object
 source_body:bytes
 native_set_value_executed:bool=False
 native_cleanup_or_migration_executed:bool=False
 native_current_model_verified:bool=False

@dataclass(frozen=True)
class LoadedEntityMetadata:
 body:EntityMetadataBody
 consumed:int

def load_metadata_entity_body_bytes(wire,position=0):
 if type(wire)is not bytes or type(position)is not int or not 0<=position<=len(wire):raise UnsupportedProfile('Exact single buffer and Entity14B body position')
 start=position
 if position+2>len(wire):raise UnsupportedProfile('Complete Entity14B version')
 version=struct.unpack_from('>H',wire,position)[0];position+=2
 if version==4:return LoadedEntityMetadata(EntityMetadataBody(4,(),(),b'',(),None,wire[start:position]),position-start)
 if version!=3:raise UnsupportedProfile('Entity14B versions1/2 original grammar and other loadedflag branches remain unmodeled')
 if position+4>len(wire):raise UnsupportedProfile('Complete Entity14B version3 rowcount')
 count=struct.unpack_from('>I',wire,position)[0];position+=4
 if count>MAX_ROWS:raise UnsupportedProfile('Independent Entity metadata row limit; actual countU32')
 if not count:return LoadedEntityMetadata(EntityMetadataBody(3,(),(),b'',(),None,wire[start:position]),position-start)
 if position+4>len(wire):raise UnsupportedProfile('Complete Entity14B compressed blob size')
 size=struct.unpack_from('>I',wire,position)[0];position+=4
 if not 0<size<=MAX_BYTES+8192 or position+size>len(wire):raise UnsupportedProfile('Complete bounded Entity14B blob')
 payload,chunks,endian=decode_framed_stream(wire[position:position+size]);position+=size
 rows,skipped=parse_row_payload(payload,count)
 return LoadedEntityMetadata(EntityMetadataBody(3,rows,skipped,payload,chunks,endian,wire[start:position]),position-start)

def load_metadata_entity_body(wire):
 loaded=load_metadata_entity_body_bytes(wire)
 if loaded.consumed!=len(wire):raise UnsupportedProfile('Exact entire Entity14B body; no ignored trailing bytes')
 return loaded.body

def preserve_metadata_entity_body(body):
 if not isinstance(body,EntityMetadataBody)or load_metadata_entity_body(body.source_body)!=body:raise UnsupportedProfile('Unmodified complete Entity14B raw body')
 return body.source_body

def exact_path_rows(body,path):
 if not isinstance(body,EntityMetadataBody)or type(path)is not bytes:raise UnsupportedProfile('Exact Entity14B stored-row query')
 return tuple(row for row in body.rows if row.path==path)

def encode_owned_metadata_entity_body(rows,*,empty_main_tree=False,compress=True):
 """Own caller inventory only; native tree count and rowcount are separate.

 Native Store writes4 if its main tree is empty. With a nonempty main tree it
 writes3 even if flattened rows are empty. This explicit own flag supplies that
 construction choice; no raw row inventory is treated as a runtime tree.
 """
 if type(rows)is not tuple or type(empty_main_tree)is not bool or type(compress)is not bool:raise UnsupportedProfile('Explicit own Entity14B inventory and tree occupancy')
 if empty_main_tree:
  if rows:raise UnsupportedProfile('Own empty main tree cannot declare stored rows')
  return b'\0\x04'
 # Shared independent encoder builds the actual common count/blob grammar.
 own=encode_owned_metadata_body(rows,compress=compress)
 wire=b'\0\x03'+own[2:]
 if load_metadata_entity_body(wire).rows!=rows:raise AssertionError('Own Entity14B body roundtrip')
 return wire
