"""Independent caller-local original TKE XML resource framing and CRC decode.

Only reviewed resources5014/5015/5017/5021 are supported. 5014 is ElementTypes;
5021 is derived-gist definitions. No interpretation is assigned to5016 here.
Compression uses the existing independently authored codec, never native code.
"""
from dataclasses import dataclass
import struct,xml.etree.ElementTree as ET
from raw_tke_nodes_reference import read_xprf_directory,identity,sha
from interop.form_core.cx_string_wire_reference import decode_mode4,cx_crc
MAX_XML_BYTES=32*1024*1024
MAX_XML_ELEMENTS=250000

@dataclass(frozen=True)
class XMLDefinition:
 index:int
 source_start:int
 source_end:int
 source_sha256:str
 decoded:bytes
 decoded_sha256:str
 blocks:tuple
 def parse(self):return parse_xml(self.decoded)

def parse_xml(data):
 if type(data)is not bytes or not 0<len(data)<=MAX_XML_BYTES:raise ValueError('Bounded complete source XML bytes required')
 try:text=data.decode('utf-8')
 except UnicodeError as error:raise ValueError('Original source XML UTF8 required')from error
 if '\0'in text or '<!DOCTYPE'in text.upper()or '<!ENTITY'in text.upper():raise ValueError('XML DTD/entity/NUL outside finite source profile')
 try:root=ET.fromstring(text)
 except ET.ParseError as error:raise ValueError('Invalid original XML')from error
 stack=[(root,0)];count=0
 while stack:
  e,d=stack.pop();count+=1
  if d>256 or count>MAX_XML_ELEMENTS:raise ValueError('Bounded XML source structure required')
  stack.extend((c,d+1)for c in e)
 return root

def decode_stream(stream,*,source_start=0):
 if type(stream)is not bytes or not 1<len(stream)<=MAX_XML_BYTES or stream[0]!=0:raise ValueError('Complete little-endian source compression stream required')
 p=1;output=bytearray();blocks=[]
 while p<len(stream):
  start=p
  if p+5>len(stream):raise ValueError('Truncated source compression block header')
  tag=stream[p];size=struct.unpack_from('<I',stream,p+1)[0];p+=5
  if not 1<=size<=65000:raise ValueError('Original bounded compression block required')
  crc=None
  if tag==0xf0:
   if p+2>len(stream):raise ValueError('Truncated source compression CRC')
   crc=struct.unpack_from('<H',stream,p)[0];p+=2
  elif tag!=0x0f:raise ValueError('Unsupported source compression block kind')
  if p+size>len(stream):raise ValueError('Truncated source block payload')
  blob=stream[p:p+size];p+=size
  try:data=decode_mode4(blob,capacity=65000)if tag==0xf0 else blob
  except ValueError as error:raise ValueError('Invalid source mode4 block')from error
  if not data or len(data)>65000 or crc is not None and cx_crc(data)!=crc:raise ValueError('Source decoded block size/CRC mismatch')
  if len(output)+len(data)>MAX_XML_BYTES:raise ValueError('Decoded source XML size budget exceeded')
  blocks.append(dict(source_start=source_start+start,source_end=source_start+p,marker=tag,encoded_bytes=size,decoded_bytes=len(data),decoded_start=len(output),decoded_sha256=sha(data),source_crc=crc));output.extend(data)
 return bytes(output),tuple(blocks)

def read_xml_resource(carrier,*,approved_carrier_sha256,approved_payload_sha256,resource_type,resource_id=1,selected_indices=None):
 if type(resource_type)is not int or resource_type not in(5014,5015,5017,5021)or type(resource_id)is not int or resource_id!=1:raise ValueError('Exact reviewed XML resource profile required')
 directory=read_xprf_directory(carrier,expected_sha256=approved_carrier_sha256)
 if(resource_type,resource_id)not in directory:raise ValueError('Required original XML resource absent')
 offset,size=directory[resource_type,resource_id];start=offset+10;end=offset+size;identity(memoryview(carrier)[start:end],approved_payload_sha256)
 if resource_type in(5015,5021):
  if start+2>end:raise ValueError('Missing compressed string-list count')
  count=struct.unpack_from('<H',carrier,start)[0];p=start+2
  if not 1<=count<=10000:raise ValueError('Bounded explicit original definition count required')
 else:count=1;p=start
 frames=[]
 for i in range(count):
  at=p
  if p+4>end:raise ValueError('Truncated original compressed string length')
  length=struct.unpack_from('<I',carrier,p)[0];p+=4;z=p+length
  if not 1<length<=MAX_XML_BYTES or z>end:raise ValueError('Complete bounded source compressed string required')
  frames.append((at,p,z));p=z
 if p!=end:raise ValueError('Unconsumed source XML definition bytes')
 if selected_indices is None:selected=set(range(count))
 elif type(selected_indices)not in(list,tuple)or len(selected_indices)!=len(set(selected_indices))or any(type(i)is not int or not 0<=i<count for i in selected_indices):raise ValueError('Explicit unique existing XML definition indices required')
 else:selected=set(selected_indices)
 result=[]
 for i,(at,p,z)in enumerate(frames):
  if i not in selected:continue
  decoded,blocks=decode_stream(carrier[p:z],source_start=p);result.append(XMLDefinition(i,at,z,sha(memoryview(carrier)[at:z]),decoded,sha(decoded),blocks))
 return tuple(result)
