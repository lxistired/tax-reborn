"""Independently authored bounded StringTable version2/raw-block codec.

It writes real bytes, not prepared compressed-frame placeholders. Selected
concrete zccProcessStream has explicit enabled=False; underlying stream is
binary with big-endian scalar primitives and little-endian native payload.
Only zero or one512-byte chunk,0 or64 slots, defaults512/512/64/64, balanced
unlocked state, successful prepared allocations and unavailable compression
buffers. No heap, v1 conversion, compressedF0, general.tax or native execution.
Store is a selected synthetic wrapper with explicit successful BeginAccess\ncontext and balanced EndAccess; higher native serializer caller unbound.\nAdditional consistency refusals below are independent-model eligibility
guards, not assertions that native Load checks them.
"""
from dataclasses import dataclass,replace
import struct

DEFAULTS=(512,512,64,64)
FFFF=65535
class UnsupportedProfile(ValueError):pass
class NativeError(Exception):
 def __init__(self,code):self.code=code
@dataclass(frozen=True)
class Chunk:
 data:bytes
 used:int
 holes:int=0
@dataclass(frozen=True)
class Table:
 config:tuple=DEFAULTS
 free_head:int=FFFF
 slots:bytes=b''
 chunks:tuple=()
 counter:int=0
 access_count:int=0
 modifying:bool=False
 locked:bool=False
@dataclass(frozen=True)
class LoadOutcome:
 table:Table
 code:object
 consumed:int
 trace:tuple
 limitation:object=None
 native_execution_count:int=0
 original_fixture_count:int=0

def idle(table):
 if table.access_count or table.modifying or table.locked:
  raise UnsupportedProfile('Balanced idle/unlocked profile only; Clear does not reset access/modifying')
def clear(table):
 idle(table)
 # Existing native Clear resets storage/head/slotcount/livecounter, not config.
 return replace(table,free_head=FFFF,slots=b'',chunks=(),counter=0)

def records(chunk):
 if type(chunk.data) is not bytes or len(chunk.data)!=512 or not 0<=chunk.used<=512:
  raise UnsupportedProfile('Explicit successful512-byte storage')
 p=0;out={}
 while p<chunk.used:
  if p+2>=chunk.used:raise UnsupportedProfile('Incomplete physical CString record')
  h=struct.unpack_from('<H',chunk.data,p)[0]
  q=chunk.data.find(b'\0',p+2,chunk.used)
  if q<0:raise UnsupportedProfile('Missing CString NUL')
  text=chunk.data[p+2:q]
  if any(c>127 for c in text):raise UnsupportedProfile('ASCII finite payload')
  out[p+2]=(h,text,q+1-p);p=q+1
 return out

def validate(table):
 idle(table)
 if table.config!=DEFAULTS:raise UnsupportedProfile('Actual fresh selected ctor defaults only')
 if not table.chunks:
  if table.slots or table.free_head!=FFFF:raise UnsupportedProfile('Zero-chunk/zero-slot profile')
  return
 if len(table.chunks)!=1 or len(table.slots)!=256:
  raise UnsupportedProfile('One chunk and64 physical4-byte slots only')
 c=table.chunks[0];rs=records(c)
 if not 0<=c.holes<=512:raise UnsupportedProfile('Bounded holes')
 seen=set();free=table.free_head
 while free!=FFFF:
  if not 0<=free<64 or free in seen:raise UnsupportedProfile('Acyclic bounded free chain')
  seen.add(free);block,nxt=struct.unpack_from('<HH',table.slots,free*4)
  if block!=0:raise UnsupportedProfile('Free-chain entry must be unused')
  free=nxt
 allocated=set()
 for h in range(64):
  block,off=struct.unpack_from('<HH',table.slots,h*4)
  if block==0:
   if h not in seen:raise UnsupportedProfile('All unused entries accounted by free chain')
  elif block==1:
   if off not in rs or rs[off][0]!=h:raise UnsupportedProfile('Selected handle-to-record bijection')
   allocated.add(h)
  else:raise UnsupportedProfile('Only chunk1 finite profile')
 if {h for h,_,_ in rs.values() if h!=FFFF}!=allocated:
  raise UnsupportedProfile('No unresolved live/duplicate physical record')
 if sum(size for h,_,size in rs.values() if h==FFFF)!=c.holes:
  raise UnsupportedProfile('Finite deleted-record holes profile')
 # counter is intentionally not matched to slot population: Load leaves it0.

def read(table,handle):
 validate(table)
 if type(handle) is not int or not 0<=handle<64:raise UnsupportedProfile('Finite existing handle')
 block,off=struct.unpack_from('<HH',table.slots,handle*4)
 if block!=1:raise UnsupportedProfile('Removed/unallocated handle')
 return records(table.chunks[0])[off][1]

def raw_block(data):
 if type(data) is not bytes:raise UnsupportedProfile('Bytes required')
 if len(data)>65000:raise NativeError(0x78)
 return b'\x0f'+struct.pack('>I',len(data))+data

def store(table,*,compression_buffers_unavailable=True,successful_begin_access=True):
 if successful_begin_access is not True:
  raise UnsupportedProfile('Native Store dereferences cached pointers; explicit successful BeginAccess wrapper context')
 if compression_buffers_unavailable is not True:raise UnsupportedProfile('Actual raw fallback with explicit buffers-unavailable condition')
 validate(table)
 out=bytearray(struct.pack('>H4I3H',2,*table.config,table.free_head,len(table.slots)//4,len(table.chunks)))
 for c in table.chunks:
  out.extend(struct.pack('>3I',c.used,len(c.data),c.holes))
  out.extend(raw_block(c.data[:c.used]))
 if table.slots:out.extend(raw_block(table.slots))
 return bytes(out)

class Reader:
 def __init__(self,data,errors):
  self.data=data;self.p=0;self.trace=[];self.errors=dict(errors or {})
 def take(self,n):
  if self.p+n>len(self.data):
   raise UnsupportedProfile('Truncated stream: actual v58 EOF return bytes/error destination mutation unbound')
  p=self.p;self.p+=n;return self.data[p:self.p]
 def scalar(self,fmt,name,commit=None):
  value=struct.unpack('>'+fmt,self.take(struct.calcsize(fmt)))[0]
  if commit:commit(value)
  self.trace.append((name,value))
  # Explicit synthetic callback profile: complete destination primitive then
  # nonzero stream error. This is not a general EOF/error implementation.
  code=self.errors.get(name,0)
  if code:
   if type(code) is not int or not 0<code<=65535:raise UnsupportedProfile('Explicit nonzero synthetic stream error')
   raise NativeError(code)
  return value
 def block(self,expected,name):
  marker=self.scalar('B',name+'.marker')
  if marker==0xf0:raise NativeError(0x98) # selected buffers unavailable
  if marker!=0x0f:raise NativeError(0x9c)
  size=self.scalar('I',name+'.size')
  if size!=expected:raise NativeError(0x78)
  data=self.take(size);self.trace.append((name+'.payload',size))
  code=self.errors.get(name+'.payload',0)
  if code:raise NativeError(code)
  return data

def load(data,old,*,allocation_image=b'.'*512,compression_buffers_unavailable=True,
         byte_swap_enabled=False,completed_read_errors=None):
 idle(old)
 if type(data) is not bytes:raise UnsupportedProfile('Bytes required')
 if compression_buffers_unavailable is not True or byte_swap_enabled is not False:
  raise UnsupportedProfile('Explicit concrete stream disabled and unavailable compression buffers')
 if type(allocation_image) is not bytes or len(allocation_image)!=512:
  raise UnsupportedProfile('Prepared successful512-byte allocation image')
 allowed={'version','config0','config1','config2','config3','free_head','slots','chunks',
          'chunk0.used','chunk0.capacity','chunk0.holes','chunk0.payload','slots.payload'}
 if completed_read_errors and not set(completed_read_errors)<=allowed:
  raise UnsupportedProfile('Only actual post-read checked metadata/payload error positions')
 state=clear(old);r=Reader(data,completed_read_errors);cfg=list(state.config)
 try:
  version=r.scalar('H','version')
  if version not in (1,2):raise NativeError(0x1ff)
  if version==1:raise UnsupportedProfile('Native accepts v1; its8-byte slot conversion not in this codec')
  for i in range(4):
   def commit(v,i=i):
    nonlocal state
    cfg[i]=v;state=replace(state,config=tuple(cfg))
   r.scalar('I','config'+str(i),commit)
  free=r.scalar('H','free_head');count=r.scalar('H','slots');chunks=r.scalar('H','chunks')
  if tuple(cfg)!=DEFAULTS or count not in (0,64) or chunks not in (0,1):
   raise UnsupportedProfile('Bounded defaults/one-chunk/64slots scope')
  result=[]
  for i in range(chunks):
   used=r.scalar('I','chunk'+str(i)+'.used')
   cap=r.scalar('I','chunk'+str(i)+'.capacity')
   holes=r.scalar('I','chunk'+str(i)+'.holes')
   if cap<used or cap<holes:raise NativeError(0x78)
   if cap!=512:raise UnsupportedProfile('Successful selected capacity512 only')
   payload=r.block(used,'chunk'+str(i))
   result.append(Chunk(payload+allocation_image[len(payload):],used,holes))
  slots=r.block(count*4,'slots') if count else b''
  state=replace(state,free_head=free,slots=slots,chunks=tuple(result))
  validate(state)
  return LoadOutcome(state,0,r.p,tuple(r.trace))
 except NativeError as e:return LoadOutcome(clear(state),e.code,r.p,tuple(r.trace))
 except UnsupportedProfile as e:
  # Finite refusal; no fabricated native error code/EOF destination bytes.
  return LoadOutcome(clear(state),None,r.p,tuple(r.trace),str(e))

def swap_record_handles(payload):
 if type(payload) is not bytes:raise UnsupportedProfile('Exact used prefix')
 p=0;out=bytearray(payload)
 while p<len(out):
  if p+2>=len(out):raise UnsupportedProfile('Incomplete record')
  q=out.find(0,p+2)
  if q<0:raise UnsupportedProfile('Unterminated record')
  out[p],out[p+1]=out[p+1],out[p];p=q+1
 return bytes(out)

def swap_slot_pairs(payload):
 if type(payload) is not bytes or len(payload)%4:raise UnsupportedProfile('Whole4-byte slot records')
 out=bytearray(payload)
 for p in range(0,len(out),2):out[p],out[p+1]=out[p+1],out[p]
 return bytes(out)
