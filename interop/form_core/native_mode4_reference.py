"""Independent selected native fast0/0 mode4 match policy and finite composition.

Only method4, initialized65300/36864 successful buffers, input<=8192 and
prepared binaryBE/swapfalse ordinaryStringTable. Exact native compressor bytes
are proven only for one private originalresource3161B->403B. Other input tests
prove independent grammar/readback, not native runtime or universal exactness.
Original source/bytes stay private. CRC and old decoder are independently reused.
"""
from dataclasses import dataclass,replace
import struct
from .cx_string_wire_reference import (Writer,decode_mode4,decode_block,Buffers,
 initialized,cx_crc,UnsupportedProfile,NativeError,DEFAULTS,Table,LoadOutcome,
 raw_block,load,clear)
from .form_string_wire_reference import store_section as raw_store_section
from .form_string_wire_reference import load_section as raw_load_section,LoadSection

@dataclass(frozen=True)
class Candidate:
 native_return:int
 candidate:bytes
 tokens:tuple
 selected_compressed:bool
 profile:str='method4-fast0/0-scratch36864'
 native_execution_count:int=0


def encode_selected(data):
 if type(data) is not bytes or len(data)>8192:
  raise UnsupportedProfile('Independent finite input<=8192; native dispatcher65000 separate')
 if len(data)<2:return Candidate(len(data),b'',(),False)
 # Native fast0 selector uses4013 hash buckets. Scratch36864 minus2048pair
 # bytes gives34816; floor(34816/(4013*2))=4, minusone yieldsringdepth3.
 buckets=4013;heads=[0]*buckets;ring=[[65535]*3 for _ in range(buckets)];pairs=[0]*1024
 w=Writer();p=0;limit=len(data)-2;tokens=[]
 while p<limit:
  a,b,c=data[p:p+3];h=((a|(b<<8))^(c<<4))%buckets
  best=where=0;at=heads[h]
  for _ in range(3):
   at=at-1 if at else 2;q=ring[h][at]
   if q==65535:break
   if q>=p or data[q]!=a or data[q+best]!=data[p+best]:continue
   extra=0
   while extra<256 and p+extra<limit:
    nxt=extra+1
    if data[q+nxt]!=data[p+nxt] or q+nxt>=p:
     length=nxt;break
    extra=nxt
   else:length=extra
   if length>best:
    best=length;where=q
    if length==256:break
  if best<3:
   q=pairs[(a<<2)^b]
   if data[q]==a and data[q+1]==b and p+1<limit and 2<=p-q<=255:best=2;where=q
   else:best=0
  if not best:
   w.put(0,1);w.put(a,8);step=1;tokens.append(('literal',p,a))
  else:
   distance=p-where;w.put(1,1)
   if best==2:w.put(1,1)
   else:
    w.put(0,1);w.variable(best-1)
    high=distance>>8
    if not high:w.put(1,1)
    else:w.put(0,1);w.variable(high+1)
   w.put(distance&255,8);step=best;tokens.append(('match',p,best,distance))
  # Only token starts are inserted; skipped match interior is not indexed.
  ring[h][heads[h]]=p;heads[h]=(heads[h]+1)%3;pairs[(a<<2)^b]=p;p+=step
 for index in range(len(data)-2,len(data)):
  a=data[index];w.put(0,1);w.put(a,8);tokens.append(('literal-tail',index,a))
 w.put(1,1);w.put(0,1);w.variable(257)
 encoded=w.result()
 compressed=len(encoded)<len(data)
 return Candidate(len(encoded) if compressed else len(data),encoded,tuple(tokens),compressed)


def dispatch_profile(method,*,input_length,output_capacity,scratch_size):
 """Source dispatcher statuses/selectors. Does not execute any native mode."""
 if any(type(v) is not int or not 0<=v<=65535 for v in (method,input_length,output_capacity,scratch_size)):
  raise UnsupportedProfile('Actual ushort arguments supplied explicitly')
 if ((scratch_size+35)&65535)<18467:return 65532,None
 if input_length>65000 or output_capacity>65000:return 65533,None
 profiles={1:(1,1),2:(2,2),3:(3,3),4:(0,0),5:(3,0)}
 return (0,profiles[method]) if method in profiles else (65534,None)


def emit_selected_block(data,buffers,*,byte_order='>'):
 if type(data) is not bytes or len(data)>8192 or byte_order not in ('<','>'):
  raise UnsupportedProfile('Finite block and explicit scalar endian')
 if not initialized(buffers) or buffers.method==0:return raw_block(data) if byte_order=='>' else b'\x0f'+struct.pack('<I',len(data))+data
 if buffers.method!=4:raise UnsupportedProfile('Selected method4 only')
 r=encode_selected(data)
 if not r.selected_compressed:return b'\x0f'+struct.pack(byte_order+'I',len(data))+data
 return b'\xf0'+struct.pack(byte_order+'IH',len(r.candidate),cx_crc(data))+r.candidate


def rewrite_selected_table(wire,buffers,*,encode):
 if len(wire)<24:raise UnsupportedProfile('Complete finite tableheader')
 version,*cfg,free,slots,chunks=struct.unpack_from('>H4I3H',wire)
 if version!=2 or tuple(cfg)!=DEFAULTS or slots not in (0,64) or chunks not in (0,1):
  raise UnsupportedProfile('Accepted60finite v2/default/onechunk64slots')
 p=24;out=bytearray(wire[:24]);blocks=[]
 for i in range(chunks+(1 if slots else 0)):
  if i<chunks:
   if p+12>len(wire):raise UnsupportedProfile('Complete chunkheader')
   header=wire[p:p+12];p+=12;used,cap,holes=struct.unpack('>3I',header)
   if cap<used or cap<holes:raise NativeError(0x78)
   if cap!=512:raise UnsupportedProfile('Selected capacity512')
   expected=used;out.extend(header)
  else:expected=slots*4
  d=decode_block(wire[p:],expected,buffers)
  if d.code is None:raise UnsupportedProfile(d.limitation)
  if d.code:raise NativeError(d.code)
  block=emit_selected_block(d.data,buffers) if encode else raw_block(d.data)
  blocks.append((wire[p],block[0],len(d.data)));out.extend(block);p+=d.consumed
 return bytes(out),p,tuple(blocks)


def store_selected_section(table,buffers,**context):
 r=raw_store_section(table,**context)
 if r.string_section is None:return r
 wire,_,_=rewrite_selected_table(r.string_section,buffers,encode=True)
 return replace(r,string_section=wire)


def load_selected_section(wire,old,buffers,**context):
 # Existing finite callerguards run before local codec, preventing invented
 # header/hash/child success. Only actualstringsection predecessors supplied.
 prior=context.get('before_string_section_error',0)
 skip=context.get('just_get_objects',False) or context.get('streamed_values',False)
 if prior or skip or context.get('modify_acquired',True) is not True:
  return raw_load_section(wire,old,**context)
 if len(wire)>=2 and struct.unpack('>H',wire[:2])[0]!=2:
  return raw_load_section(wire,old,**context)
 try:
  normalized,_,_=rewrite_selected_table(wire,buffers,encode=False)
 except NativeError as e:
  phases=('BeginModify1','guard modify byte1','Clear keeps modify1','StringTable.Load','EndModify0')
  return LoadSection(replace(clear(old),config=DEFAULTS),context['cells'],context['current_handle'],phases,e.code)
 return raw_load_section(normalized,old,**context)
