"""Independent finite caller lifecycle, compaction and table-ID repair.

Only actual ordinary ValueForm, prepared successful header/C9/value sections,
no streamed-values mode/children/links, one finite v2/raw0f StringTable profile.
Output segments are discontiguous in original form; never a whole form/.tax.
The underlying accepted60 codec models buffer bytes. Here explicit phase logs
account for actual BeginModify1/Load/Clear/EndModify0 without confusing its
idle eligibility guard with the original flag state inside native Load.
"""
from dataclasses import dataclass,replace
import struct
from .string_wire_reference import Table,Chunk,validate,records,store,load,read,UnsupportedProfile,FFFF
from .string_registry_reference import Registry,add_table,remove_table

def pack(table):
 validate(table)
 if not table.chunks:return table
 c=table.chunks[0];out=bytearray(c.data);slots=bytearray(table.slots);p=0
 # Native Pack walks records in-order; deleted recordFFFF skipped.
 for offset,(handle,text,size) in records(c).items():
  if handle==FFFF:continue
  rec=struct.pack('<H',handle)+text+b'\0';out[p:p+len(rec)]=rec
  # Native updates only slot second word; chunk first word stays1.
  struct.pack_into('<H',slots,handle*4+2,p+2);p+=len(rec)
 return replace(table,slots=bytes(slots),chunks=(Chunk(bytes(out),p,0),))

def share_status(*,runtime_enabled,template_flags):
 if type(runtime_enabled) is not bool or type(template_flags) is not int or not 0<=template_flags<1<<32:raise UnsupportedProfile('Explicit runtime flag and source template flags')
 if not runtime_enabled:return 0
 return 2 if template_flags&0x20 else (template_flags>>4)&1

@dataclass(frozen=True)
class StoreSection:
 table:Table
 table_id_wire:bytes
 string_section:object
 phase_log:tuple
 code:int=0
 whole_form_wire:object=None
 native_execution_count:int=0

def store_section(table,*,table_id,requested_share,actual_share,
                  context_is_null=True,context_v28_zero=True,
                  field_table_available=True,initial_stream_error=0):
 if type(table_id) is not int or not 0<=table_id<=FFFF:raise UnsupportedProfile('u16 tableID')
 if type(requested_share) is not int or type(actual_share) is not int or requested_share not in (0,1,2) or actual_share not in (0,1,2):
  raise UnsupportedProfile('Actual ordinary share0/1/2 profile')
 if any(type(v) is not bool for v in (context_is_null,context_v28_zero,field_table_available)):
  raise UnsupportedProfile('Explicit finite opaque callback predicates')
 if initial_stream_error:return StoreSection(table,b'',None,(),initial_stream_error)
 if requested_share!=actual_share:return StoreSection(table,b'',None,())
 if not field_table_available or table_id==FFFF:return StoreSection(table,b'',None,(),0x67)
 if not context_is_null and not context_v28_zero:
  return StoreSection(table,struct.pack('>H',table_id),None,('StreamValues','skip StringTable'),0)
 packed=pack(table)
 phases=('BeginModify1','Pack','EndModify0','BeginAccess1','StringTable.Store','EndAccess0')
 wire=store(packed,successful_begin_access=True)
 return StoreSection(packed,struct.pack('>H',table_id),wire,phases)

@dataclass(frozen=True)
class ValueCell:
 kind:int
 raw:int
 header:int=0
 FV_word:int=0
 exponent:int=0
@dataclass(frozen=True)
class Remap:
 cells:tuple
 changed_flag:bool
 code:int=0

def reset_handles(cells,new_table):
 if type(new_table) is not int or not 0<=new_table<=FFFF or type(cells) is not tuple or len(cells)>64:raise UnsupportedProfile('Prepared finite loaded field entries/u16 ID')
 out=[];changed=False
 for cell in cells:
  if cell is None:out.append(None);continue
  if not isinstance(cell,ValueCell) or cell.kind not in (7,11,12):raise UnsupportedProfile('Explicit kind7 StringTypes1/numeric11,12 StringTypes0 only')
  if not 0<=cell.raw<1<<64:raise UnsupportedProfile('Raw64 value')
  if cell.kind!=7:out.append(cell);continue
  if cell.raw&FFFF==0:
   changed=True;out.append(cell)
  else:
   out.append(replace(cell,raw=(cell.raw&~FFFF)|new_table))
 return Remap(tuple(out),changed)

@dataclass(frozen=True)
class RegistryPreparation:
 registry:Registry
 current_handle:int
 add_code:int
 action_log:tuple

def prepare_registry(registry,*,current_handle,saved_handle,current_pointer,
                     just_get_objects=False):
 if any(type(x) is not int or not 0<=x<=FFFF for x in (current_handle,saved_handle)):raise UnsupportedProfile('u16 handles')
 if just_get_objects:return RegistryPreparation(registry,FFFF,0,('objects-only skip',))
 if current_handle==FFFF:return RegistryPreparation(registry,FFFF,0x67,('invalid current handle',))
 # Actual signed16 saved>=0 and differs is the re-registration gate.
 if saved_handle>32767 or saved_handle==current_handle:
  return RegistryPreparation(registry,current_handle,0,('keep current handle',))
 a=add_table(registry,pointer=current_pointer,requested_handle=saved_handle)
 if a.handle==saved_handle:
  removed=remove_table(a.registry,current_handle)
  if removed.returned_pointer:
   return RegistryPreparation(removed.registry,saved_handle,a.error_code,('Add saved','Remove old','Form.SetHandle saved'))
  return RegistryPreparation(removed.registry,current_handle,a.error_code,('Add saved','Remove old returnedNULL','keep current handle'))
 return RegistryPreparation(a.registry,current_handle,a.error_code,('Add saved failed','keep current handle'))

@dataclass(frozen=True)
class LoadSection:
 table:Table
 cells:tuple
 current_handle:int
 phase_log:tuple
 code:object
 changed_flag:bool=False
 limitation:object=None
 native_execution_count:int=0
 whole_form_load_proven:bool=False
 string_section_loaded:bool=False

def load_section(wire,old,*,cells,current_handle,saved_handle,
                 before_string_section_error=0,modify_acquired=True,
                 just_get_objects=False,streamed_values=False):
 # Header, duplicate-copy validation, C9 seeks and hash-table loader remain
 # explicit prepared successful predecessors, not implemented/observed.
 if before_string_section_error:
  return LoadSection(old,cells,current_handle,(),before_string_section_error)
 if just_get_objects or streamed_values:
  return LoadSection(old,cells,current_handle,('skip StringTable.Load',),0)
 if modify_acquired is not True:
  return LoadSection(old,cells,current_handle,('BeginModify failed guard',),0,limitation='Prepared earlier error0 remains0 at native guard return; string section not loaded')
 # Accepted60 pure-byte model is composed here; actual native flag remains1
 # duringClear/Load and cleared by caller afterward, no extra native attach.
 o=load(wire,old)
 phases=('BeginModify1','guard modify byte1','Clear keeps modify1','StringTable.Load','EndModify0')
 if o.code!=0:return LoadSection(o.table,cells,current_handle,phases,o.code,limitation=o.limitation)
 if saved_handle!=current_handle:
  r=reset_handles(cells,current_handle)
  return LoadSection(o.table,r.cells,current_handle,phases+('ResetStringTableHandles',),r.code,r.changed_flag,string_section_loaded=True)
 return LoadSection(o.table,cells,current_handle,phases,0,string_section_loaded=True)
