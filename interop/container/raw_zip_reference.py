"""Finite ZIP32 read/rewrite preserving every unchanged member's local bytes.

Independent interoperability code. Native ZipFile/minizip execution and
deflater byte parity are not claimed. Unknown extras anchor geometry; they
never become permission to relocate opaque metadata.
"""
from dataclasses import dataclass
import struct,zlib

class UnsupportedProfile(ValueError):pass
MAX_SOURCE=32*1024*1024
MAX_MEMBER=16*1024*1024
MAX_TOTAL=64*1024*1024
MAX_MEMBERS=4096

@dataclass(frozen=True)
class Member:
 name:bytes
 payload:bytes
 flags:int
 method:int
 offset:int
 central:bytes
 local:bytes
 local_header:bytes
 compressed:bytes
 descriptor:bytes
 opaque_extra:bool

@dataclass(frozen=True)
class Archive:
 members:tuple
 source:bytes
 central_offset:int
 central_size:int
 eocd:bytes

def _need(condition,message):
 if not condition:raise UnsupportedProfile(message)

def _extra(raw):
 p=0;opaque=False
 while p<len(raw):
  _need(p+4<=len(raw),'Complete ZIP extra-field header')
  tag,size=struct.unpack_from('<HH',raw,p);p+=4
  _need(p+size<=len(raw),'Complete ZIP extra-field data');data=raw[p:p+size];p+=size
  _need(tag!=1,'ZIP64 extra fields are outside this finite ZIP32 profile')
  if tag==0x5455:
   # Standard UT timestamp bytes have no archive positions. Retain raw bytes.
   _need(bool(data)and not data[0]&~7 and len(data)==1+4*data[0].bit_count(),'Finite complete UT timestamp extra field')
  else:opaque=True
 return opaque

def _decode(data,method,size):
 if method==0:result=data
 else:
  try:
   d=zlib.decompressobj(-15);result=d.decompress(data,size+1)
   _need(d.eof and not d.unconsumed_tail and not d.unused_data,'Exact bounded raw-deflate member')
  except zlib.error as e:raise UnsupportedProfile('Valid raw-deflate ZIP member')from e
 _need(len(result)==size,'ZIP decoded member size matches directory')
 return result

def load_archive(wire):
 _need(type(wire)is bytes and 22<=len(wire)<=MAX_SOURCE,'Bounded complete ZIP byte buffer')
 candidates=[];p=len(wire)
 while True:
  p=wire.rfind(b'PK\x05\x06',max(0,len(wire)-65557),p)
  if p<0:break
  if p+22<=len(wire)and p+22+struct.unpack_from('<H',wire,p+20)[0]==len(wire):candidates.append(p)
 _need(len(candidates)==1,'One exact terminal ZIP end record, without trailing data');end=candidates[0]
 disk,cddisk,nlocal,count,cdsize,cdoff,comment=struct.unpack_from('<4H2IH',wire,end+4)
 _need(disk==cddisk==0 and nlocal==count and 0<count<=MAX_MEMBERS,'Finite single-disk nonempty ZIP directory')
 _need(count!=65535 and cdsize!=0xffffffff and cdoff!=0xffffffff,'ZIP32 directory bounds, without ZIP64 sentinel')
 _need(cdoff+cdsize==end,'Complete contiguous central directory before end record')
 central=[];p=cdoff;names=set();offsets=set();total=0
 for _ in range(count):
  _need(p+46<=end and wire[p:p+4]==b'PK\x01\x02','Complete ZIP central record')
  flags,method=struct.unpack_from('<HH',wire,p+8);crc,csize,size=struct.unpack_from('<3I',wire,p+16)
  ns,xs,cs,mdisk=struct.unpack_from('<4H',wire,p+28);offset=struct.unpack_from('<I',wire,p+42)[0];stop=p+46+ns+xs+cs
  _need(stop<=end and ns>0 and mdisk==0,'Complete ZIP names/extras/comments on same disk')
  _need(method in(0,8)and not flags&~0x080e,'Ordinary stored/deflated, unencrypted ZIP flags only')
  _need(size<=MAX_MEMBER and csize<=MAX_SOURCE and size!=0xffffffff and csize!=0xffffffff and offset!=0xffffffff,'Finite ZIP32 member bounds')
  name=wire[p+46:p+46+ns];_need(name not in names and b'\0'not in name,'Unique non-NUL raw ZIP member names')
  _need(offset not in offsets and offset<cdoff,'Unique local-header position before directory')
  names.add(name);offsets.add(offset);total+=size;_need(total<=MAX_TOTAL,'Independent total decoded ZIP size guard')
  opaque=_extra(wire[p+46+ns:p+46+ns+xs])
  central.append((name,flags,method,crc,csize,size,offset,wire[p:stop],opaque));p=stop
 _need(p==end,'Entire central directory consumed, no unmodeled records')
 ordered=sorted(offsets);_need(ordered[0]==0,'Selected modern ZIP begins at first local header; no self-extracting prefix')
 stops={a:b for a,b in zip(ordered,ordered[1:]+[cdoff])};members=[]
 for name,flags,method,crc,csize,size,off,raw,opaque in central:
  limit=stops[off];_need(off+30<=limit and wire[off:off+4]==b'PK\x03\x04','Complete local ZIP header')
  lf,lm=struct.unpack_from('<HH',wire,off+6);lc,ls,lu=struct.unpack_from('<3I',wire,off+14);ns,xs=struct.unpack_from('<HH',wire,off+26)
  begin=off+30+ns+xs;finish=begin+csize
  _need(lf==flags and lm==method and begin<=limit and finish<=limit,'Local and central ZIP method/flags/bounds agree')
  _need(wire[off+30:off+30+ns]==name,'Exact local/central ZIP raw name')
  local_opaque=_extra(wire[off+30+ns:begin])
  opaque=opaque or local_opaque
  descriptor=wire[finish:limit]
  if flags&8:
   _need(lc in(0,crc)and ls in(0,csize)and lu in(0,size),'Descriptor-mode local sizes/CRC are zero or exact facts')
   d=descriptor[4:]if descriptor[:4]==b'PK\x07\x08'else descriptor
   _need(len(d)==12 and struct.unpack('<3I',d)==(crc,csize,size),'Complete exact ZIP32 data descriptor')
  else:_need((lc,ls,lu)==(crc,csize,size)and not descriptor,'Exact local ZIP sizes/CRC without inter-record padding')
  compressed=wire[begin:finish];payload=_decode(compressed,method,size)
  _need(zlib.crc32(payload)&0xffffffff==crc,'CRC of every ZIP member, including unreferenced entries')
  members.append(Member(name,payload,flags,method,off,raw,wire[off:limit],wire[off:begin],compressed,descriptor,opaque))
 return Archive(tuple(members),wire,cdoff,cdsize,wire[end:])

def replace_payloads(archive,replacements):
 _need(isinstance(archive,Archive)and load_archive(archive.source)==archive,'Unmodified validated ZIP source state')
 _need(type(replacements)is dict and all(type(k)is bytes and type(v)is bytes for k,v in replacements.items()),'Exact existing raw-name to payload map')
 byname={m.name:m for m in archive.members};_need(set(replacements)<=set(byname),'No implicit new ZIP members')
 changed={k:v for k,v in replacements.items()if v!=byname[k].payload}
 if not changed:return archive.source
 _need(all(len(v)<=MAX_MEMBER for v in changed.values()),'Bounded replacement member bytes')
 local=[];central={};position=0
 for m in sorted(archive.members,key=lambda x:x.offset):
  header=bytearray(m.local_header);cr=bytearray(m.central)
  if m.name in changed:
   _need(not m.opaque_extra,'Selected member has unmodeled extra metadata; source edit refused')
   data=changed[m.name]
   if m.method==0:packed=data
   else:
    d=zlib.compressobj(9,zlib.DEFLATED,-15);packed=d.compress(data)+d.flush()
   crc=zlib.crc32(data)&0xffffffff;facts=(crc,len(packed),len(data))
   struct.pack_into('<3I',cr,16,*facts)
   if m.flags&8:
    old=struct.unpack_from('<3I',header,14);struct.pack_into('<3I',header,14,*tuple(new if prior else 0 for prior,new in zip(old,facts)))
    descriptor=(b'PK\x07\x08'if len(m.descriptor)==16 else b'')+struct.pack('<3I',*facts)
   else:struct.pack_into('<3I',header,14,*facts);descriptor=b''
   record=bytes(header)+packed+descriptor
  else:record=m.local
  struct.pack_into('<I',cr,42,position);central[m.name]=bytes(cr);local.append(record);position+=len(record)
 _need(position<=MAX_SOURCE,'Bounded rewritten ZIP local data')
 geometry_changed=position!=archive.central_offset or any(struct.unpack_from('<I',central[m.name],42)[0]!=m.offset for m in archive.members)
 _need(not geometry_changed or not any(m.opaque_extra for m in archive.members),'Unknown ZIP extra metadata cannot be relocated')
 directory=b''.join(central[m.name]for m in archive.members);_need(len(directory)==archive.central_size,'Preserve complete directory inventory/name/extra/comment sizes')
 end=bytearray(archive.eocd);struct.pack_into('<I',end,16,position)
 output=b''.join(local)+directory+bytes(end);loaded=load_archive(output)
 _need(tuple((m.name,m.payload)for m in loaded.members)==tuple((m.name,changed.get(m.name,m.payload))for m in archive.members),'Complete replacement ZIP readback')
 return output

def read_zip32(wire):
 return load_archive(wire)

def patch_single_payload(archive,member,payload):
 return replace_payloads(archive,{member:payload})
