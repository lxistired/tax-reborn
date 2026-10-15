"""Independent physical 16-byte StringTable registry and constructor config.

Allocation success uses an explicit fresh backing image; opaque bytes are kept.
This is no whole allocator/native pointer/controller simulation.
"""
from dataclasses import dataclass,replace
import struct
class UnsupportedProfile(ValueError):pass
def uint(x,bits):
 if type(x) is not int or not 0<=x<1<<bits:raise UnsupportedProfile('Raw unsigned integer required')
 return x
@dataclass(frozen=True)
class Registry:
 image:bytes
 count:int
 capacity:int

def valid(r):
 if not isinstance(r,Registry) or type(r.image) is not bytes:raise UnsupportedProfile('Physical registry image required')
 uint(r.count,16);uint(r.capacity,16)
 if r.count>r.capacity or len(r.image)!=r.capacity*16:raise UnsupportedProfile('Prepared consistent registry words/storage required')
 return r

def entry(r,i):
 valid(r)
 if not 0<=i<r.count:raise UnsupportedProfile('Existing active registry entry only')
 return struct.unpack_from('<H',r.image,i*16)[0],struct.unpack_from('<Q',r.image,i*16+8)[0]
@dataclass(frozen=True)
class Added:
 registry:Registry
 handle:int
 error_code:int
 allocation_called:bool
 new_table_created:object=None

def add_table(r,*,pointer,requested_handle=65535,new_backing=None):
 valid(r);uint(pointer,64);uint(requested_handle,16);allocated=False
 if r.count>=r.capacity:
  if r.capacity>=65520:return Added(r,65535,2,False)
  newcap=r.capacity+16
  if type(new_backing) is not bytes or len(new_backing)!=newcap*16:raise UnsupportedProfile('Explicit successful new[] backing bytes required')
  d=bytearray(new_backing);d[:len(r.image)]=r.image;r=Registry(bytes(d),r.count,newcap);allocated=True
 handle=requested_handle
 if requested_handle==65535:handle=1 if not r.count else (max(entry(r,i)[0] for i in range(r.count))+1)&65535
 elif any(entry(r,i)[0]==handle for i in range(r.count)):return Added(r,65535,5,allocated)
 d=bytearray(r.image);struct.pack_into('<H',d,r.count*16,handle);struct.pack_into('<Q',d,r.count*16+8,pointer)
 return Added(Registry(bytes(d),r.count+1,r.capacity),handle,0,allocated)

def lookup(r,handle):
 valid(r);uint(handle,16)
 if not r.count or not r.capacity:return None
 for i in range(r.count):
  h,p=entry(r,i)
  if h==handle:return p
 return None
@dataclass(frozen=True)
class Removed:
 registry:Registry
 found:bool
 returned_pointer:int
 node_error:int=0
 storage_freed:bool=False

def remove_table(r,handle):
 valid(r);uint(handle,16)
 for i in range(r.count):
  h,p=entry(r,i)
  if h!=handle:continue
  # Actual RemoveNode copies last16 bytes to selected index, not tree erase.
  d=bytearray(r.image);last=(r.count-1)*16
  if r.count>=2:d[i*16:i*16+16]=r.image[last:last+16]
  struct.pack_into('<H',d,last,65535);struct.pack_into('<Q',d,last+8,0)
  return Removed(Registry(bytes(d),r.count-1,r.capacity),True,p)
 return Removed(r,False,0)
@dataclass(frozen=True)
class NewTableConfig:
 raw_40:int
 raw_44:int
 raw_114:int
 raw_118:int
 chunk_count:int=0
 live_strings:int=0
 free_head:int=65535
 allocated_slots:int=0
 access_depth:int=0
 modify_byte:int=0
 chunk_and_slot_data_pointers_null:bool=True

def construct_table(a,b,c,d):
 for x in (a,b,c,d):uint(x,16)
 return NewTableConfig(a,b,c,d)
@dataclass(frozen=True)
class FormRegistration:
 registry:Registry
 embedded_table:NewTableConfig
 table_handle:int
 error_code:int
 table_deleted:object=None

def register_form_table(r,*,embedded_pointer,new_backing=None,prior_constructor_error=0):
 uint(prior_constructor_error,16);config=construct_table(512,512,64,64)
 if prior_constructor_error:return FormRegistration(r,config,65535,prior_constructor_error)
 result=add_table(r,pointer=embedded_pointer,requested_handle=65535,new_backing=new_backing)
 # Native form ctor assigns returned handle before copying the registration qp.
 return FormRegistration(result.registry,config,result.handle,result.error_code)

def set_form_handle(form,handle):
 uint(handle,16)
 if not isinstance(form,FormRegistration):raise UnsupportedProfile('Prepared form table descriptor required')
 return replace(form,table_handle=handle)
