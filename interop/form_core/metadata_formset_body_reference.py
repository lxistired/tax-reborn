"""Typed raw body view for MetaDataKeyValueFormSetPO (IsA151).

No native TreeNode/set_value/current IDataModel/fixup is executed. Ordered raw
rows and every source framing byte remain distinct from native runtime values.
This subset parses the actual framed0F/mode4 format and preserves the complete
body unchanged. It does not grant an unknown object class relocation permission.
"""
from dataclasses import dataclass
import struct
from .cx_string_wire_reference import decode_mode4,cx_crc,UnsupportedProfile
from .native_mode4_reference import emit_selected_block,Buffers

NAME=b'MetaDataKeyValueFormSetPO'
CLASS_ID=0x151
MAX_BYTES=4*1024*1024
MAX_ROWS=65535 # independent finite limit; native count is U32

@dataclass(frozen=True)
class Row:
 path:bytes
 text:bytes

@dataclass(frozen=True)
class Chunk:
 marker:int
 encoded_bytes:int
 decoded_bytes:int
 source_frame:bytes

@dataclass(frozen=True)
class Body:
 version:int
 rows:tuple
 skipped_lines:tuple
 payload:bytes
 chunks:tuple
 stream_endian:object
 source_body:bytes
 native_set_value_executed:bool=False
 native_current_model_verified:bool=False
 native_nonNULL_FormSet_fixup_executed:bool=False

@dataclass(frozen=True)
class LoadedBody:
 body:Body
 consumed:int

def _bytes(data,label):
 if type(data)is not bytes or len(data)>MAX_BYTES:raise UnsupportedProfile('Finite exact '+label+' bytes')
 return data

def _row(row):
 if not isinstance(row,Row):raise UnsupportedProfile('Explicit own byte row')
 _bytes(row.path,'path');_bytes(row.text,'text')
 if not row.path or any(v in row.path for v in (b'\0',b'\t',b'\n'))or b'\0'in row.text or b'\n'in row.text:
  raise UnsupportedProfile('Finite complete C-string row grammar; no NUL/LF or path TAB')
 return row

def decode_framed_stream(blob):
 if type(blob)is not bytes or not 1<=len(blob)<=MAX_BYTES+8192:raise UnsupportedProfile('Complete bounded compression stream')
 if blob[0]not in(0,1):raise UnsupportedProfile('Finite actual framed stream; native78 raw fallback is separate')
 order='<'if blob[0]==0 else'>';p=1;out=bytearray();chunks=[]
 while p<len(blob):
  start=p
  if p+5>len(blob):raise UnsupportedProfile('Complete compression block header')
  marker=blob[p];size=struct.unpack_from(order+'I',blob,p+1)[0];p+=5
  if not 0<size<=65000:raise UnsupportedProfile('Finite positive native65000 compression block bound')
  if marker==0x0f:
   if p+size>len(blob):raise UnsupportedProfile('Complete stored compression block')
   data=blob[p:p+size];p+=size
  elif marker==0xf0:
   if p+2+size>len(blob):raise UnsupportedProfile('Complete mode4 block and CRC')
   crc=struct.unpack_from(order+'H',blob,p)[0];p+=2
   data=decode_mode4(blob[p:p+size],capacity=65000);p+=size
   if cx_crc(data)!=crc:raise UnsupportedProfile('Mode4 source CRC mismatch (native9D)')
   if not data:raise UnsupportedProfile('Finite nonempty decoded compression block')
  else:raise UnsupportedProfile('Only actual0F andF0 compression block markers')
  out.extend(data)
  if len(out)>MAX_BYTES:raise UnsupportedProfile('Independent decoded metadata size bound')
  chunks.append(Chunk(marker,size,len(data),blob[start:p]))
 if not chunks:raise UnsupportedProfile('Nonempty rowcount requires actual framed data')
 return bytes(out),tuple(chunks),blob[0]

def parse_row_payload(payload,expected_count):
 _bytes(payload,'decoded metadata')
 if type(expected_count)is not int or not 0<=expected_count<=MAX_ROWS:raise UnsupportedProfile('Finite declared metadata row count; nativeU32 separate')
 if not payload or payload[-1:]!=b'\n':raise UnsupportedProfile('Complete LF-terminated native row input; no unbounded strchr fallback')
 if b'\0'in payload:raise UnsupportedProfile('Embedded NUL lies outside bounded native C-string row profile')
 rows=[];skipped=[];position=0
 for line in payload[:-1].split(b'\n'):
  tab=line.find(b'\t')
  if tab<0:skipped.append((position,line))
  else:rows.append(_row(Row(line[:tab],line[tab+1:])))
  position+=len(line)+1
 if len(rows)!=expected_count:raise UnsupportedProfile('Native buffer parser rowcount mismatch after prior set_value side effects; no rollback asserted')
 return tuple(rows),tuple(skipped)

def load_metadata_body_bytes(wire,position=0):
 if type(wire)is not bytes or type(position)is not int or not 0<=position<=len(wire):raise UnsupportedProfile('Exact single buffer and body start')
 start=position
 if position+6>len(wire):raise UnsupportedProfile('Complete version/count metadata body')
 version,count=struct.unpack_from('>HI',wire,position);position+=6
 if version not in(1,2):raise UnsupportedProfile('Native Load accepts versions1/2; other version clears loaded flag, not a native call error')
 if count>MAX_ROWS:raise UnsupportedProfile('Independent rowcount bound; nativeU32 count not truncated')
 if not count:
  return LoadedBody(Body(version,(),(),b'',(),None,wire[start:position]),position-start)
 if position+4>len(wire):raise UnsupportedProfile('Complete nonempty metadata blob length')
 size=struct.unpack_from('>I',wire,position)[0];position+=4
 if not 0<size<=MAX_BYTES+8192 or position+size>len(wire):raise UnsupportedProfile('Complete bounded metadata blob')
 payload,chunks,endian=decode_framed_stream(wire[position:position+size]);position+=size
 rows,skipped=parse_row_payload(payload,count)
 return LoadedBody(Body(version,rows,skipped,payload,chunks,endian,wire[start:position]),position-start)

def load_metadata_body(wire):
 loaded=load_metadata_body_bytes(wire)
 if loaded.consumed!=len(wire):raise UnsupportedProfile('Exact metadata object body; trailing bytes not discarded')
 return loaded.body

def load_named_metadata_body(class_name,wire):
 if class_name!=NAME or type(class_name)is not bytes:raise UnsupportedProfile('Only source-bound MetaDataKeyValueFormSetPO class body')
 return load_metadata_body(wire)

def preserve_metadata_body(body):
 if not isinstance(body,Body)or load_metadata_body(body.source_body)!=body:raise UnsupportedProfile('Unmodified complete typed raw metadata body required')
 return body.source_body

def exact_path_rows(body,path):
 if not isinstance(body,Body):raise UnsupportedProfile('Explicit typed raw body view')
 _bytes(path,'exact query path')
 # This is a raw stored-row lookup, not native GetValues/array matching.
 return tuple(row for row in body.rows if row.path==path)

def encode_owned_metadata_body(rows,*,compress=True):
 """Independently chosen valid framing, not universal native byte parity.

 Native Store writes2 and a flattened GetAllMetaData tree inventory. This own
 fixture constructor takes explicit ordered rows; it does not invent that tree
 or reproduce GetAllMetaData's traversal order.
 """
 if type(rows)is not tuple or len(rows)>MAX_ROWS or type(compress)is not bool:raise UnsupportedProfile('Explicit finite own immutable row inventory')
 for row in rows:_row(row)
 head=struct.pack('>HI',2,len(rows))
 if not rows:return head
 payload=b''.join(row.path+b'\t'+row.text+b'\n'for row in rows);_bytes(payload,'complete own metadata')
 buffer=Buffers(1000,2000,0,4 if compress else 0)
 stream=b'\0'+b''.join(emit_selected_block(payload[p:p+65000],buffer,byte_order='<')for p in range(0,len(payload),65000))
 wire=head+struct.pack('>I',len(stream))+stream
 loaded=load_metadata_body(wire)
 if loaded.rows!=rows:raise AssertionError('Own metadata row roundtrip')
 return wire
