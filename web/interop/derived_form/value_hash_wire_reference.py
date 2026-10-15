"""Independent modern>=18 wide/noncompact ValueHash/BufferMap bytes.

BEscalar/nativeLE/swapfalse. Actual1..16000 buckets, <=255 runtimebuffers
with<=2700 nodes. Loader redistributes wire blocks into runtime buffers;
source allocator success remains prepared. Legacy/swaptrue are refused.
"""
from dataclasses import dataclass,replace
import struct
from .native_mode4_reference import emit_selected_block,decode_block,UnsupportedProfile,Table,load_selected_section,rewrite_selected_table,NativeError
from .form_header_map_reference import store_core_sections,load_map,get_position,load_header,Header
NULL=0xffffffff
@dataclass(frozen=True)
class Node:
 next_index:int=NULL
 header:int=0
 kind_byte:int=7
 raw:int=0
 exponent_byte:int=0
 element_index:int=0
 field_index:int=0
 flag10:int=0
 flag11:int=0
 specific_attributes:int=0
 transient_bytes:bytes=b'\0'*8
@dataclass(frozen=True)
class Buffer:
 nodes:tuple=()
 capacity:int=0
@dataclass(frozen=True)
class Hash:
 heads:tuple=()
 buffers:tuple=()
 wide:bool=True
@dataclass(frozen=True)
class HashResult:
 state:Hash
 code:object
 wire:bytes=b''
 consumed:int=0
 phases:tuple=()
 limitation:object=None
 native_execution_count:int=0

def validate_size(size):
 if type(size) is not int or not 0<=size<=65535:raise UnsupportedProfile('Native u16bucketcount')
 return 0 if 1<=size<=16000 else 6

def validate(h):
 if not isinstance(h,Hash) or type(h.heads) is not tuple or not 0<=len(h.heads)<=16000 or type(h.buffers) is not tuple or len(h.buffers)>255 or h.wide is not True:
  raise UnsupportedProfile('Modernwide Hash:<=16000 buckets/255 buffers')
 if any(type(v) is not int or not 0<=v<=NULL for v in h.heads):raise UnsupportedProfile('Nativeu32indices supplied')
 for b in h.buffers:
  if not isinstance(b,Buffer) or type(b.nodes) is not tuple or not 0<=len(b.nodes)<=b.capacity<=2700:raise UnsupportedProfile('Native2700-node runtime buffer / explicit used/capacity')

def trim(h,*,successful_resize=True):
 validate(h);out=[]
 for b in h.buffers:
  if b.nodes and len(b.nodes)<b.capacity:
   if successful_resize is not True:raise UnsupportedProfile('PreparedsuccessfulSetDataSize; allocator/runtimefailure outsideprofile')
   b=replace(b,capacity=len(b.nodes))
  out.append(b)
 return replace(h,buffers=tuple(out))

def pack_node(n):
 if not isinstance(n,Node):raise UnsupportedProfile('Preparedtypednode')
 for value,maxi in ((n.next_index,NULL),(n.header,255),(n.kind_byte,255),(n.raw,(1<<64)-1),(n.exponent_byte,255),(n.element_index,65535),(n.field_index,65535),(n.flag10,255),(n.flag11,255),(n.specific_attributes,65535)):
  if type(value) is not int or not 0<=value<=maxi:raise UnsupportedProfile('Explicit boundednative field')
 # Full commonvalue=2byteheader+8raw+1exponent+8metadata; nodenextu32.
 return struct.pack('<IBBQBHHBBH',n.next_index,n.header,n.kind_byte,n.raw,n.exponent_byte,n.element_index,n.field_index,n.flag10,n.flag11,n.specific_attributes)

def unpack_node(data):
 if len(data)!=23:raise UnsupportedProfile('Exactwide/noncompactnode23B')
 return Node(*struct.unpack('<IBBQBHHBBH',data),transient_bytes=b'\0'*8)

def store_hash(h,buffers,*,version=18,stream_mode=10,trim_before=True,successful_resize=True):
 if type(stream_mode) is not int or type(version) is not int or not 0<=version<=255:raise UnsupportedProfile('Explicitmode/version')
 if stream_mode&10!=10:return HashResult(h,6)
 if version<18:raise UnsupportedProfile('Actualmodern18+wide/noncompact selected; legacywidth/compact separate')
 validate(h)
 state=trim(h,successful_resize=successful_resize) if trim_before else h
 if validate_size(len(state.heads)):return HashResult(state,6,phases=('Trim successful' if trim_before else 'NoTrim','ValidateHashSize failure'))
 # Trim doesnotdrop emptyallocatedbuffers. Their unknownunusedmemory is not
 # manufactured into node records by this finiteprofile.
 if any(b.capacity!=len(b.nodes) for b in state.buffers):raise UnsupportedProfile('Fullallocatednodeimage unknown; nativewritescapacity notused')
 out=bytearray(struct.pack('>H',len(state.heads)))
 out.extend(emit_selected_block(struct.pack('<'+'I'*len(state.heads),*state.heads),buffers))
 out.extend(bytes([0xd8,len(state.buffers)]))
 for b in state.buffers:
  out.extend(struct.pack('>H',b.capacity));out.extend(emit_selected_block(b''.join(pack_node(n) for n in b.nodes),buffers))
 out.append(0x5e)
 return HashResult(state,0,wire=bytes(out),phases=('Trim successful' if trim_before else 'NoTrim','ValidateHashSize','u16bucketcount','headblock.Store','D8/BufferMap.Store','caret5E'))

def load_hash(wire,old,buffers,*,version=18,stream_mode=6,swap=False):
 if type(wire) is not bytes or type(swap) is not bool:raise UnsupportedProfile('Explicitbinarybytes/Swapflag')
 if stream_mode&6!=6:return HashResult(old,6)
 if version<18 or swap:raise UnsupportedProfile('Actualmodernwide/noncompact/swapfalse only; SwapBytes caller exists but not implemented here')
 if len(wire)<2:raise UnsupportedProfile('Complete modernhash size')
 count=struct.unpack_from('>H',wire)[0];p=2
 updated=replace(old,wide=True)
 if validate_size(count):return HashResult(updated,6,consumed=p,phases=('wideflag1','ValidateHashSize failure'))

 updated=replace(updated,heads=(NULL,)*count)
 def fail(code,*,clear_buffers=False,limitation=None):
  state=replace(updated,heads=(NULL,)*count,buffers=() if clear_buffers else updated.buffers)
  return HashResult(state,code,consumed=p,phases=('size/heads assigned','headvector resetNULL'),limitation=limitation)
 def block(expected):
  nonlocal p
  r=decode_block(wire[p:],expected,buffers);p+=r.consumed
  return r
 d=block(count*4)
 if d.code!=0:return fail(d.code,limitation=d.limitation)
 updated=replace(updated,heads=struct.unpack('<'+'I'*count,d.data))
 if p>=len(wire):raise UnsupportedProfile('CompleteBufferMap tag')
 mark=wire[p];p+=1
 if mark!=0xd8:return fail(0x1fb,clear_buffers=True)
 if p>=len(wire):raise UnsupportedProfile('CompleteBufferMap count')
 chunks=wire[p];p+=1
 nodes=[];newbufs=[];current=[];remaining_capacity=0
 for block_index in range(chunks):
  if p+2>len(wire):raise UnsupportedProfile('CompleteBufferMap nodecount')
  nodecount=struct.unpack_from('>H',wire,p)[0];p+=2
  d=block(nodecount*23)
  if d.code!=0:return fail(d.code,clear_buffers=True,limitation=d.limitation)
  decoded=[unpack_node(d.data[j:j+23]) for j in range(0,len(d.data),23)]
  offset=0
  while offset<len(decoded):
   if not remaining_capacity:
    remaining_capacity=2700
    if block_index==chunks-1:remaining_capacity=min(2700,len(decoded)-offset)
    current=[];newbufs.append([current,remaining_capacity])
    if len(newbufs)>255:raise UnsupportedProfile('Native255 runtime-buffer slots; overflow refused')
   take=min(remaining_capacity,len(decoded)-offset);current.extend(decoded[offset:offset+take]);offset+=take;remaining_capacity-=take
 newbufs=[Buffer(tuple(nodes),capacity) for nodes,capacity in newbufs]

 updated=replace(updated,buffers=tuple(newbufs))
 if p>=len(wire):raise UnsupportedProfile('Completecaret5E')
 terminal=wire[p];p+=1
 if terminal!=0x5e:return fail(0x1fb)
 return HashResult(updated,0,consumed=p,phases=('wideflag1','ValidateHashSize','u16bucketcount','headblock.Load','D8/BufferMap.Load','caret5E','Swapflagfalse'))

def find_value(h,field,element):
 validate(h)
 if any(type(v) is not int or not 0<=v<=65535 for v in (field,element)):raise UnsupportedProfile('Preparedu16field/element')
 if not h.heads:raise UnsupportedProfile('Nativezero-bucketlookup dividesbyzero; finiteguard')
 bucket=(field*3+element*5)%len(h.heads);index=h.heads[bucket];seen=set()
 while index!=NULL:
  if index in seen:raise UnsupportedProfile('Independent cycle guard; native unbounded chain refused')
  seen.add(index);base=0;n=None
  for b in h.buffers:
   if base<=index<base+b.capacity:
    local=index-base
    if local<len(b.nodes):n=b.nodes[local]
    break
   base+=b.capacity
  if n is None:return None
  if n.field_index==field and n.element_index==element:return n
  index=n.next_index
 return None

def hash_for_nodes(nodes,*,bucket_count=127,capacity=None):
 if type(nodes) is not tuple or not 1<=bucket_count<=16000 or len(nodes)>255*2700:raise UnsupportedProfile('Modern prepared node construction bounds')
 heads=[NULL]*bucket_count;out=list(nodes);tails={}
 for index,n in enumerate(nodes):
  if n.next_index!=NULL:raise UnsupportedProfile('Preparedunlinkednodeinput')
  bucket=(n.field_index*3+n.element_index*5)%bucket_count
  if bucket in tails:out[tails[bucket]]=replace(out[tails[bucket]],next_index=index)
  else:heads[bucket]=index
  tails[bucket]=index
 if capacity is not None and len(nodes)>2700:raise UnsupportedProfile('Explicit spare capacity only for one buffer')
 chunks=tuple(Buffer(tuple(out[p:p+2700]),min(2700,len(out)-p)) for p in range(0,len(out),2700))
 if capacity is not None and chunks:chunks=(replace(chunks[0],capacity=capacity),)
 return Hash(tuple(heads),chunks)

@dataclass(frozen=True)
class FormCore:
 prefix:object
 hash_result:HashResult
 value_hash_bytes_prepared:bool=False
 whole_form_proven:bool=False
 native_execution_count:int=0

def store_form_core(header,hash_state,string_table,buffers,*,table_id=2,base_position=0,version=18):
 h=store_hash(hash_state,buffers,version=version)
 if h.code:raise UnsupportedProfile('Preparedsuccessfulhashstore')
 p=store_core_sections(header,string_table,buffers,table_id=table_id,prepared_value_hash_bytes=h.wire,base_position=base_position)
 return FormCore(p,h)

@dataclass(frozen=True)
class CoreLoad:
 header:object
 hash_state:Hash
 string_table:Table
 name:object
 code:object
 string_handles_changed_flag:bool=False
 consumed:int=0
 saved_table_id:object=None
 single_buffer_reader:bool=False
 whole_form_proven:bool=False
 native_execution_count:int=0

def _load_mapped_sections(wire,header,m,buffers,*,current_table_id,saved_table_id,field_index,base_position,single_buffer):
 positions=[get_position(m,i)-base_position for i in range(4)]
 if not (0<=positions[0]<=positions[1]==positions[2]<=positions[3]<=len(wire)):
  raise UnsupportedProfile('Independent finiteorderedsectionbounds; nativeMapLoad doesnotvalidate this')
 start,end=positions[:2];h=load_hash(wire[start:end],Hash(),buffers)
 if h.code:return CoreLoad(header,h.state,Table(),None,h.code,consumed=start+h.consumed,saved_table_id=saved_table_id,single_buffer_reader=single_buffer)
 if h.consumed!=end-start:raise UnsupportedProfile('Independent exactValueHashsectionbound')
 start,end=positions[2:];stringwire=wire[start:end]
 try:
  _,string_consumed,_=rewrite_selected_table(stringwire,buffers,encode=False)
 except NativeError as e:
  return CoreLoad(header,h.state,Table(),None,e.code,consumed=start,saved_table_id=saved_table_id,single_buffer_reader=single_buffer)
 if string_consumed!=len(stringwire):raise UnsupportedProfile('Independent exactStringTablesectionbound')
 strings=load_selected_section(stringwire,Table(),buffers,cells=(),current_handle=current_table_id,saved_handle=saved_table_id)
 if strings.code:return CoreLoad(header,h.state,strings.table,None,strings.code,consumed=start,saved_table_id=saved_table_id,single_buffer_reader=single_buffer)
 # Actualaccepted61 ResetStringTableHandles appliesonlywhenIDs differ.
 # Only kind7StringTypes profile is interpreted, no mask-derivedpromotion.
 out=[];changed=False
 for b in h.state.buffers:
  nodes=[]
  for n in b.nodes:
   if saved_table_id!=current_table_id and n.kind_byte==7:
    if n.raw&65535:n=replace(n,raw=(n.raw&~65535)|current_table_id)
    else:changed=True
   nodes.append(n)
  out.append(replace(b,nodes=tuple(nodes)))
 state=replace(h.state,buffers=tuple(out));node=find_value(state,field_index,0)
 from .string_wire_reference import read
 name=read(strings.table,(node.raw>>16)&65535) if node and node.kind_byte==7 and node.raw&65535==current_table_id else None
 return CoreLoad(header,state,strings.table,name,0,changed,positions[3],saved_table_id,single_buffer)


def load_form_core(core,buffers,*,current_table_id=3,saved_table_id=2,field_index=23,base_position=0):
 """Finite model+sidecar convenience; not a rawformbyte reader."""
 p=core.prefix;header=load_header(p.header)
 if header.code:return CoreLoad(header.header,Hash(),Table(),None,header.code)
 m=load_map(p.map_wire,0xc9,p.mapping.base).mapping
 return _load_mapped_sections(p.wire_prefix,header.header,m,buffers,current_table_id=current_table_id,saved_table_id=saved_table_id,field_index=field_index,base_position=base_position,single_buffer=False)


def load_form_core_bytes(wire,buffers,*,base_position=0,current_table_id=3,prepared_parents=(),old_header=Header(),field_index=23):
 """Parse one bytebuffer: C4/CB consumedlength -> tableID -> C9 -> sections.

 A finite ordinarymoderncore prefix withfourC9offsets andemptysection1 is
 accepted. Tailtables/children/links mayfollowbutarenotparsed. Externalruntime
 tableID/parents/buffers remainprepared. This isnot arbitrary.taxfile parsing.
 """
 if type(wire) is not bytes or type(base_position) is not int or not 0<=base_position<=0xffffffff or base_position+len(wire)>0xffffffff:
  raise UnsupportedProfile('Finitebytebuffer/nonwrappingstreambase')
 if type(current_table_id) is not int or not 0<=current_table_id<65535:
  raise UnsupportedProfile('PreparedsuccessfulcurrenttableID; nativeinvalidcurrenthandle guard67 is earlier')
 header=load_header(wire,old_header,parents=prepared_parents)
 if header.code:return CoreLoad(header.header,Hash(),Table(),None,header.code,consumed=header.consumed,single_buffer_reader=True)
 pos=header.consumed
 if pos+2>len(wire):raise UnsupportedProfile('CompletewiretableIDu16')
 saved=struct.unpack_from('>H',wire,pos)[0];pos+=2
 mapped=load_map(wire[pos:],0xc9,base_position+pos)
 if mapped.code:return CoreLoad(header.header,Hash(),Table(),None,mapped.code,consumed=pos+mapped.consumed,saved_table_id=saved,single_buffer_reader=True)
 m=mapped.mapping
 if m.capacity!=4 or m.used!=4:raise UnsupportedProfile('IndependentordinarymodernC9foursectionprofile')
 first=get_position(m,0)-base_position
 if first!=pos+mapped.consumed:raise UnsupportedProfile('IndependentC9section0immediatelyaftermapheader')
 return _load_mapped_sections(wire,header.header,m,buffers,current_table_id=current_table_id,saved_table_id=saved,field_index=field_index,base_position=base_position,single_buffer=True)
