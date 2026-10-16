"""Independent complete selected FormBase record with emptyE0/C8/D7 tails.

This consumes/emits an entire finite modern18+ ordinaryFormBase record under
preparedstream/runtime context. Entity/FormSet/.taxfile remains unimplemented.
Nonemptytables/children/links andruntime creation/resolution are refused.
"""
from dataclasses import dataclass
from .value_hash_wire_reference import (store_form_core,load_form_core_bytes,UnsupportedProfile)
from .form_header_map_reference import (new_map,store_map,append_position,update_map,load_map,get_position)
EMPTY_MARKERS=(0xe0,0xc8,0xd7)
@dataclass(frozen=True)
class RecordStore:
 wire:bytes
 core:object
 tail_maps:tuple
 entire_selected_form_record_emitted:bool=True
 whole_tax_compatibility:bool=False
 native_execution_count:int=0
@dataclass(frozen=True)
class RecordLoad:
 core:object
 code:object
 consumed:int
 tail_maps:tuple=()
 entire_selected_form_record_consumed:bool=False
 whole_tax_compatibility:bool=False
 native_execution_count:int=0

def empty_map(marker,position):
 m=store_map(new_map(marker,1),position).mapping
 m=append_position(m,position+9).mapping
 return update_map(m,position+9).mapping,store_map(m,position).wire

def store_selected_form_record(header,hash_state,string_table,buffers,*,table_id=2,base_position=0,version=18,tables=(),children=(),links=()):
 if any(type(x) is not tuple or x for x in (tables,children,links)):
  raise UnsupportedProfile('Selectedemptytables/children/links only; no silentdrop')
 if type(version) is not int or not 18<=version<=255:raise UnsupportedProfile('Selectedmodern18+outercontext supplied')
 core=store_form_core(header,hash_state,string_table,buffers,table_id=table_id,base_position=base_position,version=version)
 out=bytearray(core.prefix.wire_prefix);maps=[]
 for marker in EMPTY_MARKERS:
  position=base_position+len(out)
  if position+9>0xffffffff:raise UnsupportedProfile('Finite nonwrappingstreambase')
  m,w=empty_map(marker,position);maps.append(m);out.extend(w)
 return RecordStore(bytes(out),core,tuple(maps))

def load_selected_form_record(wire,buffers,*,base_position=0,current_table_id=3,prepared_parents=(),field_index=23,version=18,allow_trailing=False):
 if type(version) is not int or not 18<=version<=255 or type(allow_trailing) is not bool:
  raise UnsupportedProfile('Selectedmodern18+ordinaryrecord andexplicittrailingpolicy')
 core=load_form_core_bytes(wire,buffers,base_position=base_position,current_table_id=current_table_id,prepared_parents=prepared_parents,field_index=field_index)
 if core.code:return RecordLoad(core,core.code,core.consumed)
 p=core.consumed;maps=[]
 for marker in EMPTY_MARKERS:
  r=load_map(wire[p:],marker,base_position+p)
  if r.code:return RecordLoad(core,r.code,p+r.consumed,tuple(maps))
  m=r.mapping
  if m.capacity!=1 or m.used!=1 or m.offsets!=(9,):
   raise UnsupportedProfile('Independentselectedemptytailmapcap1/used1/offset9; native nonemptytable/child/link paths notparsed')
  end=get_position(m,0)-base_position
  if end!=p+r.consumed or end>len(wire):raise UnsupportedProfile('Independentexactemptytailbound')
  maps.append(m);p=end
 if p!=len(wire) and not allow_trailing:raise UnsupportedProfile('Independentselectedrecordexactlength; Entity/FormSet/tail outsideprofile')
 return RecordLoad(core,0,p,tuple(maps),p==len(wire))
