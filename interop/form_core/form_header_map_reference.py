"""Independent finite FormHeader and StreamMap, prepared binaryBE/swapfalse.

Native StreamMap rawoffsetarray is LE on selected x86; scalar headers are the
explicit olderBEstream profile. Swaptrue load is separately selectable, not
silently imposed. Does not implement valuehash/tables/child/link/.taxcontainer.
Header errors assume prepared CheckLoadError/FormLoadError preserve error.
No vendor source/bytes/nativeexecution. Bounds stronger than native recorded.
"""
from dataclasses import dataclass,replace
import struct
from .native_mode4_reference import UnsupportedProfile,store_selected_section
MAX=65535
@dataclass(frozen=True)
class Parent:
 identifier:bytes
 file_copy:int
 word7c:int=0
@dataclass(frozen=True)
class Header:
 identifier:bytes=b''
 file_copy:int=0
 word7c:int=0
 word7e:int=0
 word80:int=0
 word82:int=0
 parent:object=None
 parent_field_id:bytes=b''
 parent_field_index:int=0
 parent_element:int=0
@dataclass(frozen=True)
class HeaderLoad:
 header:Header
 code:int
 consumed:int
 encoded_parent_present:bool=False
 error_callback:object=None
 native_execution_count:int=0

def valid_id(v):
 if type(v) is not bytes or len(v)>32 or any(b>127 or b==0 for b in v):raise UnsupportedProfile('Independent ASCII32/NULfree ID profile; StoreHeader native has no32guard')
 return v

def u16(v):
 if type(v) is not int or not 0<=v<=MAX:raise UnsupportedProfile('Native unsigned16 scalar')
 return v

def u32(v):
 if type(v) is not int or not 0<=v<=0xffffffff:raise UnsupportedProfile('Native unsigned32 scalar')
 return v

def ident_bytes(v):valid_id(v);return struct.pack('>H',len(v))+v

def store_header(h,*,successful_parent_field_callback=True,initial_error=0):
 if not isinstance(h,Header):raise UnsupportedProfile('Explicit Header')
 if initial_error:return b'',initial_error
 out=bytearray(b'\xc4'+ident_bytes(h.identifier)+struct.pack('>I4H',u32(h.file_copy),u16(h.word7c),u16(h.word7e),u16(h.word80),u16(h.word82))+b'\xcb'+bytes([bool(h.parent)]))
 if h.parent is not None:
  if not isinstance(h.parent,Parent):raise UnsupportedProfile('Prepared concrete parent pointer')
  out.extend(ident_bytes(h.parent.identifier));out.extend(struct.pack('>IH',u32(h.parent.file_copy),u16(h.parent.word7c)))
  if h.parent_field_index:
   if successful_parent_field_callback is not True:raise UnsupportedProfile('Opaqueparent v58 error/success callback must be prepared; no inventedID lookup')
   if not h.parent_field_id:raise UnsupportedProfile('Prepared successful nonemptyparent fieldID')
   out.extend(ident_bytes(h.parent_field_id))
  else:out.extend(b'\0\0')
  out.extend(struct.pack('>2H',u16(h.parent_field_index),u16(h.parent_element)))
 return bytes(out),0

def load_header(wire,old=Header(),*,parents=(),initial_error=0):
 if type(wire) is not bytes or not isinstance(old,Header) or type(parents) is not tuple:raise UnsupportedProfile('Finite byteheader/preparedparentlookup')
 p=0;h=old;present=False;last_id_length=0
 def take(n):
  nonlocal p
  if p+n>len(wire):raise UnsupportedProfile('Independent completeheader bound; nativeEOF/errorcallback excluded')
  a=wire[p:p+n];p+=n;return a
 def get(fmt):return struct.unpack('>'+fmt,take(struct.calcsize('>'+fmt)))
 def getid():
  nonlocal last_id_length
  n=get('H')[0];last_id_length=n
  if n>32:return None
  # SourceLoad strlen truncates at embeddedNUL; no new text invariant.
  return take(n).split(b'\0',1)[0]
 def error(code,cb='CheckLoadError3'):return HeaderLoad(h,code,p,present,cb)
 if initial_error:return HeaderLoad(old,initial_error,0)
 if take(1)!=b'\xc4':return error(0x200)
 identifier=getid()
 if identifier is None:return error(0x200)
 copy,w7c,w7e,w80,w82=get('I4H');h=replace(h,identifier=identifier,file_copy=copy,word7c=w7c,word7e=w7e,word80=w80,word82=w82)
 if take(1)!=b'\xcb':return error(0x200)
 present=bool(take(1)[0])
 if not present:return HeaderLoad(h,0,p,False)
 parentid=getid()
 if parentid is None:return error(0x200)
 parentcopy,parentword=get('IH')
 parentfieldid=getid()
 if parentfieldid is None:return error(0x200)
 parent_field_wire_length=last_id_length
 if parent_field_wire_length:h=replace(h,parent_field_id=parentfieldid)
 index=get('H')[0];h=replace(h,parent_field_index=index)
 if index and not parent_field_wire_length:return error(0x200)
 element=get('H')[0];h=replace(h,parent_element=element)
 parent=next((x for x in parents if x.file_copy==parentcopy),None)
 h=replace(h,parent=parent)
 if parent is None or parent.identifier!=parentid:return error(0x1f5,'FormLoadError2')
 # Parentword7c is read into a local and not compared to lookedupparent.
 return HeaderLoad(h,0,p,True)

@dataclass(frozen=True)
class Map:
 marker:int
 capacity:int=0
 used:int=65535
 offsets:tuple=()
 base:int=0xffffffff
@dataclass(frozen=True)
class MapResult:
 mapping:Map
 code:int
 index:int=65535
 wire:bytes=b''
 consumed:int=0
 position:object=None
 phases:tuple=()
 limitation:object=None

def new_map(marker,count=None,*,initial_error=0):
 if type(marker) is not int or not 0<=marker<256:raise UnsupportedProfile('Native u8mark')
 if count is None or initial_error:return Map(marker)
 cap=max(1,u16(count));return Map(marker,cap,0,(0xffffffff,)*cap)

def append_position(m,position,*,initial_error=0):
 if initial_error:return MapResult(m,initial_error)
 u32(position)
 check=0 if m.used==65535 else m.used
 if check>=m.capacity:return MapResult(m,2)
 if m.used>=len(m.offsets):raise UnsupportedProfile('Native sentinelused65535 canaddressoutsideallocatedarray; finiteguard')
 out=list(m.offsets);out[m.used]=(position-m.base)&0xffffffff
 return MapResult(replace(m,used=(m.used+1)&65535,offsets=tuple(out)),0,m.used)

def store_map(m,position,*,initial_error=0):
 if initial_error:return MapResult(m,initial_error)
 u32(position);u16(m.capacity);u16(m.used)
 if m.capacity>64 or len(m.offsets)!=m.capacity:raise UnsupportedProfile('Independent boundedoffsetarray64')
 updated=replace(m,base=position)
 wire=bytes([m.marker])+struct.pack('>2H',m.capacity,m.used)+struct.pack('<'+'I'*m.capacity,*m.offsets)
 return MapResult(updated,0,wire=wire,position=(position+len(wire))&0xffffffff)

def load_map(wire,marker,position=0,*,swap=False,initial_error=0):
 if initial_error:return MapResult(new_map(marker),initial_error)
 if type(wire) is not bytes or type(swap) is not bool:raise UnsupportedProfile('Explicit finitebytes/processorSwapflag')
 if not wire:raise UnsupportedProfile('Finitecomplete map tag')
 if wire[0]!=marker:
  return MapResult(new_map(marker),0x25c,consumed=1,phases=('read tag mismatch','base=-1','diagnostic seek0/read40'),limitation='Native diagnostic seeks0 andreads40; boundedparser consumed1 is not nativefinalcursor')
 if len(wire)<5:raise UnsupportedProfile('Finitecomplete map scalarheader')
 cap,used=struct.unpack_from('>2H',wire,1)
 if cap==0:return MapResult(Map(marker,0,65535,(),u32(position)),0,consumed=5)
 if cap>64 or len(wire)<5+cap*4:raise UnsupportedProfile('Independent capacity64/complete array')
 offsets=list(struct.unpack_from('<'+'I'*cap,wire,5))
 if swap:
  for i in range(min(cap,used)):offsets[i]=int.from_bytes(offsets[i].to_bytes(4,'little'),'big')
 return MapResult(Map(marker,cap,used,tuple(offsets),u32(position)),0,consumed=5+cap*4)

def get_position(m,index):
 u16(index)
 if index>=m.used:return 0xffffffff
 if index>=len(m.offsets):raise UnsupportedProfile('Native GetPosition indexes<used withoutcapacityguard; finiteoutofbounds refused')
 return (m.base+m.offsets[index])&0xffffffff

def seek_map(m,index,current,*,initial_error=0,prepared_seek_error=0):
 if initial_error:return MapResult(m,initial_error,position=current)
 target=get_position(m,index)
 if target==0xffffffff:return MapResult(m,5,position=current)
 if current==target:return MapResult(m,0,position=current,phases=('GetPosition current','clear error0'))
 return MapResult(m,prepared_seek_error,position=target if not prepared_seek_error else current,phases=('GetPosition current','Seek target'))

def seek_end(m,current,*,initial_error=0,prepared_seek_error=0):
 if initial_error:return MapResult(m,initial_error,position=current)
 if m.used==0:
  target=(m.base+m.capacity*4+5)&0xffffffff
  return MapResult(m,prepared_seek_error,position=target if not prepared_seek_error else current,phases=('Seek mapheader end',))
 i=(m.used-1)&65535
 if i>=m.capacity:return MapResult(m,0x6f,position=current)
 return seek_map(m,i,current,prepared_seek_error=prepared_seek_error)

def update_map(m,current,*,initial_error=0,first_seek_error=0,store_error=0,restore_error=0):
 if initial_error:return MapResult(m,initial_error,position=current)
 if m.base==0xffffffff:return MapResult(m,0x93,position=current)
 first=first_seek_error or store_error
 if first:return MapResult(m,first,position=None if restore_error else current,phases=('GetPosition save','Seek mapbase','restoreattempt ignoringrestoreerror'))
 r=store_map(m,m.base)
 return MapResult(r.mapping,restore_error,wire=r.wire,position=None if restore_error else current,phases=('GetPosition save','Seek mapbase','Store offsets','Restore saved'))

@dataclass(frozen=True)
class CoreSections:
 header:bytes
 table_id:bytes
 map_wire:bytes
 value_hash:bytes
 string_table:bytes
 wire_prefix:bytes
 mapping:Map
 phase_log:tuple
 whole_form_proven:bool=False
 native_execution_count:int=0

def store_core_sections(header,table,buffers,*,table_id,prepared_value_hash_bytes,base_position=0):
 if type(prepared_value_hash_bytes) is not bytes:raise UnsupportedProfile('OpaquepreparedValueHashbytes, not a recoveredvalue writer')
 h,code=store_header(header)
 if code:raise UnsupportedProfile('Preparedsuccessfulheader')
 s=store_selected_section(table,buffers,table_id=table_id,requested_share=0,actual_share=0)
 pos=u32(base_position)+len(h)+len(s.table_id_wire)
 m=store_map(new_map(0xc9,4),pos).mapping
 values_at=pos+21;m=append_position(m,values_at).mapping
 values_end=values_at+len(prepared_value_hash_bytes);m=append_position(m,values_end).mapping
 # Actualcaller Appendtwice aftervalues, yieldingzero intermediate section.
 m=append_position(m,values_end).mapping
 m=append_position(m,values_end+len(s.string_section)).mapping
 mapped=store_map(m,pos);prefix=h+s.table_id_wire+mapped.wire+prepared_value_hash_bytes+s.string_section
 phases=('FormHeader.Store','tableID.Store','C9.Store placeholder','C9.Append0','ValueHash prepared','C9.Append1','C9.Append2')+s.phase_log+('C9.Append3','C9.Update seekback/restore')
 return CoreSections(h,s.table_id_wire,mapped.wire,prepared_value_hash_bytes,s.string_section,prefix,m,phases)
