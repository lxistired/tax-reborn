"""Independent mode4+CRC format with finite StringTable F0 composition.

Mode4 output writer uses an independently chosen repeated-byte LZ strategy.
It is a valid bounded format writer from decoded native grammar, not recovered
native match-finder/byte-for-byte compressor parity. CRC polynomial table is
mathematically generated, never copied from vendor bytes. Resource LE frames
and selected StringTable BE frames are separate. Native runtime/fixture0.
"""
from dataclasses import dataclass,replace
import struct
from .string_wire_reference import (Table,LoadOutcome,UnsupportedProfile,NativeError,
                                  DEFAULTS,store,load,clear,raw_block,read)

def polynomial_table():
 out=[]
 for i in range(256):
  v=i<<8
  for j in range(8):v=((v<<1)^0x1021 if v&0x8000 else v<<1)&65535
  out.append(v)
 return tuple(out)
CRC_TABLE=polynomial_table()
def cx_crc(data):
 if type(data) is not bytes or len(data)>65000:raise UnsupportedProfile('Bounded CX data')
 v=0
 for b in data:v=((v<<8)^CRC_TABLE[v>>8]^b)&65535
 return v

class Bits:
 def __init__(self,data):
  if not data or data[0]&7!=4:raise UnsupportedProfile('Only actual mode4 grammar')
  self.data=data;self.p=3
 def read(self,n):
  if self.p+n>len(self.data)*8:raise UnsupportedProfile('Independent strict input-bit bound; native uses65000-byte scratch')
  v=0
  for i in range(n):
   v|=((self.data[self.p//8]>>(self.p%8))&1)<<i;self.p+=1
  return v
 def variable(self):
  w=1
  while not self.read(1):
   w+=1
   if w>8:raise UnsupportedProfile('Bounded mode4 variable width')
  return (1<<w)+self.read(w)

def decode_mode4(data,capacity=65000):
 if type(data) is not bytes or not 0<=capacity<=65000:raise UnsupportedProfile('Explicit bounded destination capacity')
 bits=Bits(data);out=bytearray()
 while True:
  if not bits.read(1):
   if len(out)>=capacity:raise UnsupportedProfile('Decoded data exceeds destination bound')
   out.append(bits.read(8))
  else:
   length=2 if bits.read(1) else bits.variable()+1
   if length==258:return bytes(out)
   if not 2<=length<=257:raise UnsupportedProfile('Unknown match length')
   hi=0
   if length>2 and not bits.read(1):hi=(bits.variable()-1)*256
   distance=hi|bits.read(8)
   if not 0<distance<=len(out) or len(out)+length>capacity:raise UnsupportedProfile('Bounded sequential LZ source/destination')
   for _ in range(length):out.append(out[-distance])

class Writer:
 def __init__(self):self.bits=[0,0,1] # low3 actual mode4
 def put(self,v,n):
  if not 0<=v<1<<n:raise UnsupportedProfile('LSB bit payload')
  self.bits.extend((v>>i)&1 for i in range(n))
 def variable(self,v):
  if not 2<=v<=257:raise UnsupportedProfile('Mode4 finite variable value')
  w=v.bit_length()-1
  for _ in range(w-1):self.put(0,1)
  self.put(1,1);self.put(v-(1<<w),w)
 def result(self):
  out=bytearray((len(self.bits)+7)//8)
  for i,b in enumerate(self.bits):out[i//8]|=b<<(i%8)
  return bytes(out)

def encode_mode4_runs(data):
 if type(data) is not bytes or len(data)>512:raise UnsupportedProfile('Independent one-chunk512-byte writer strategy')
 w=Writer();p=0
 while p<len(data):
  run=0
  if p and data[p]==data[p-1]:
   while p+run<len(data) and data[p+run]==data[p-1] and run<257:run+=1
  if run>=2:
   w.put(1,1)
   if run==2:w.put(1,1)
   else:
    w.put(0,1);w.variable(run-1);w.put(1,1) # high-distance=0
   w.put(1,8);p+=run
  else:w.put(0,1);w.put(data[p],8);p+=1
 # Actual terminal is match length258: variable257 +1.
 w.put(1,1);w.put(0,1);w.variable(257)
 return w.result()

@dataclass(frozen=True)
class Buffers:
 compressed_pointer:object=None
 scratch_pointer:object=None
 current_size:int=0
 method:int=4
@dataclass(frozen=True)
class Initialization:
 buffers:Buffers
 code:int
 requested_allocations:tuple=()
 overwritten_nonnull_pointers:tuple=()
def initialized(b):return bool(b.compressed_pointer and b.scratch_pointer)
def initialize(b,*,prepared_compressed_pointer,prepared_scratch_pointer):
 if initialized(b):return Initialization(b,0x99)
 if not prepared_compressed_pointer or not prepared_scratch_pointer:raise UnsupportedProfile('Prepared successful new[] pointers; allocation throws excluded')
 # If onlyone existingpointer, native allocates BOTH without freeingoldfirst.
 lost=tuple(x for x in (b.compressed_pointer,b.scratch_pointer) if x)
 return Initialization(Buffers(prepared_compressed_pointer,prepared_scratch_pointer,0,b.method),0,(65300,36864),lost)
def uninitialize(b):return Buffers(None,None,0,b.method)
@dataclass(frozen=True)
class InitializationFailure:
 buffers:Buffers
 rethrows:bool
 freed_pointer:object=None
 overwritten_old_pointer:object=None
 returned_error:object=None

def allocation_failure(old,*,which,prepared_compressed_pointer=None):
 if initialized(old):raise UnsupportedProfile('Already initialized returns99, no new[] path')
 if which=='first':
  # LSDA first allocation has no local landingpad; current_size waszeroed,
  # but pointer assignments occur onlyafter each successfully returnednew[].
  return InitializationFailure(replace(old,current_size=0),True)
 if which=='scratch':
  if not prepared_compressed_pointer:raise UnsupportedProfile('Successful first new[] pointer before second failure')
  # Exact original catchall view frees currentcompressed, writesNULL and
  # __cxa_rethrow. Previous scratchvalue is unmodified, not bothcleared.
  return InitializationFailure(Buffers(None,old.scratch_pointer,0,old.method),True,
                               prepared_compressed_pointer,old.compressed_pointer)
 raise UnsupportedProfile('Only actual two allocation sites')
def compress_return(ret):
 if type(ret) is not int or not 0<=ret<=65535:raise UnsupportedProfile('Native unsigned16 callback return')
 return 0x9a if ret in (65532,65533,65534) else 0
def decompress_return(ret):
 if type(ret) is not int or not 0<=ret<=65535:raise UnsupportedProfile('Native unsigned16 callback return')
 return 0x9b if ret>=65532 else 0

def emit_block(data,buffers,*,byte_order='>'):
 if type(data) is not bytes or len(data)>512 or byte_order not in ('<','>'):raise UnsupportedProfile('Finite writer512/block endian profile')
 if not initialized(buffers) or buffers.method==0:return b'\x0f'+struct.pack(byte_order+'I',len(data))+data
 if buffers.method!=4:raise UnsupportedProfile('Only nativefile method4 selected')
 encoded=encode_mode4_runs(data)
 if len(encoded)>=len(data):return b'\x0f'+struct.pack(byte_order+'I',len(data))+data
 return b'\xf0'+struct.pack(byte_order+'IH',len(encoded),cx_crc(data))+encoded

@dataclass(frozen=True)
class DecodedBlock:
 data:object
 code:object
 consumed:int
 limitation:object=None
 native_block_size_after_decompress:object=None

def decode_block(wire,expected,buffers,*,byte_order='>'):
 if type(wire) is not bytes or not 0<=expected<=65000 or byte_order not in ('<','>'):raise UnsupportedProfile('Explicit binary block profile')
 p=0
 def take(n):
  nonlocal p
  if p+n>len(wire):raise UnsupportedProfile('Finite truncated frame; native EOF/scratch stale bytes refused')
  q=wire[p:p+n];p+=n;return q
 try:
  marker=take(1)[0]
  if marker==0xf0 and not initialized(buffers):return DecodedBlock(None,0x98,p)
  if marker not in (0x0f,0xf0):return DecodedBlock(None,0x9c,p)
  size=struct.unpack(byte_order+'I',take(4))[0]
  if marker==0x0f:
   if size!=expected:return DecodedBlock(None,0x78,p)
   data=take(size);return DecodedBlock(data,0,p)
  if size>65000:return DecodedBlock(None,0x78,p)
  crc=struct.unpack(byte_order+'H',take(2))[0]
  data=decode_mode4(take(size),capacity=expected)
  if cx_crc(data)!=crc:return DecodedBlock(data,0x9d,p,native_block_size_after_decompress=len(data))
  if len(data)!=expected:
   # Native Decompress sets blocksize=actual returnedlen andLoadDataCRC checks
   # that actual len; native doesNOT compare to initial expected afterward.
   return DecodedBlock(None,None,p,'Independent exact-length eligibility guard, not native78',len(data))
  return DecodedBlock(data,0,p,native_block_size_after_decompress=len(data))
 except UnsupportedProfile as e:return DecodedBlock(None,None,p,str(e))

def transform_table_blocks(wire,buffers,*,encode):
 """Finite v2 framing only; rewriteblock codecs, preserve exactmetadataBE."""
 if len(wire)<24:raise UnsupportedProfile('Complete finite table header')
 version,*cfg,free,slots,chunks=struct.unpack_from('>H4I3H',wire)
 if version!=2 or tuple(cfg)!=DEFAULTS or slots not in (0,64) or chunks not in (0,1):
  raise UnsupportedProfile('Accepted60finite table framing')
 p=24;out=bytearray(wire[:24]);blocks=[]
 for i in range(chunks+(1 if slots else 0)):
  if i<chunks:
   if p+12>len(wire):raise UnsupportedProfile('Complete chunkheader')
   header=wire[p:p+12];p+=12;used,cap,holes=struct.unpack('>3I',header)
   if cap<used or cap<holes:raise NativeError(0x78)
   if cap!=512:raise UnsupportedProfile('Selected preparedcapacity512')
   expected=used;out.extend(header)
  else:expected=slots*4
  d=decode_block(wire[p:],expected,buffers)
  if d.code is None:raise UnsupportedProfile(d.limitation)
  if d.code:raise NativeError(d.code)
  block=emit_block(d.data,buffers) if encode else raw_block(d.data)
  blocks.append(dict(original_marker=wire[p],emitted_marker=block[0],decoded_bytes=len(d.data)))
  out.extend(block);p+=d.consumed
 return bytes(out),p,tuple(blocks)

def store_compressed_table(table,buffers,*,successful_begin_access=True):
 raw=store(table,successful_begin_access=successful_begin_access)
 return transform_table_blocks(raw,buffers,encode=True)[0]

def load_compressed_table(wire,old,buffers,*,allocation_image=b'.'*512):
 if len(wire)>=2 and struct.unpack('>H',wire[:2])[0]!=2:
  return load(wire,old,allocation_image=allocation_image)
 # Raw stream has same decoder whetherglobalsavailable ornot. Actualerror
 # cleared storage/config route is selected onlyaftercompleteheader known.
 try:
  normalized,p,blocks=transform_table_blocks(wire,buffers,encode=False)
  r=load(normalized,old,allocation_image=allocation_image)
  return replace(r,consumed=p)
 except NativeError as e:
  return LoadOutcome(replace(clear(old),config=DEFAULTS),e.code,0,(),limitation='OrdinaryF0/nativeblockerror; finite complete defaultheader context')
 except UnsupportedProfile as e:
  return LoadOutcome(clear(old),None,0,(),limitation=str(e))
