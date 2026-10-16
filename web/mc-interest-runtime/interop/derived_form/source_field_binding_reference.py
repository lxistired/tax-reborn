"""Independent source-ID view; keeps source ordinals and never rebuilds native FV.

The loader's D2 map identifies the source field. Current metadata and complete
prepared array lists are separate explicit inputs. This is a wire-preserving
binding/decision view, not execution of FixupFields or its error/event callbacks.
"""
from dataclasses import dataclass,field

class UnsupportedBindingProfile(ValueError):pass

def identifier(value):
 if type(value) is not bytes or not 0<len(value)<=32:raise UnsupportedBindingProfile('Explicit nonempty <=32-byte field ID')
 value=value.ljust(32,b' ')
 if not value.rstrip(b' '):raise UnsupportedBindingProfile('Nonempty full field ID')
 return value

def unsigned(value,bits):
 if type(value) is not int or not 0<=value<1<<bits:raise UnsupportedBindingProfile('Explicit U'+str(bits))
 return value

@dataclass(frozen=True)
class CurrentField:
 identifier:bytes
 ordinal:int
 kind:int
 format:int
 attributes:int=0
 source:object=field(default=None,compare=False)

@dataclass(frozen=True)
class CompiledArray:
 identifier:bytes
 first_field:int
 last_field:int
 element_limit:int
 flags:int=0

@dataclass(frozen=True)
class FieldInfoView:
 field:CurrentField
 array_member:bool
 array_index:int=0
 array:object=None
 attribute100:bool=False

@dataclass(frozen=True)
class NodeBinding:
 source_field_index:int
 element_index:int
 field_id:object
 current_field_index:object
 source_kind:int
 source_format:int
 fv_attributes:int
 native_action:str
 can_correct_source_scalar:bool=False
 array_index:int=0
 element_limit:object=None
 native_effects_performed:bool=False


def prepared_field_info(current,arrays):
 """Ordinary successful UseFields/GetField view, including actual array join.

    arrays is exactly (visible_array_tuple, hidden_array_tuple), already decoded
    and range-checked by the caller. The native first range match wins. Missing
    array for attributes40 clears array-member state; attributes100 is a separate
    bit and does not make a field an array member. No template registry is read.
 """
 if not isinstance(current,CurrentField):raise UnsupportedBindingProfile('Explicit CurrentField')
 identifier(current.identifier)
 unsigned(current.ordinal,16);unsigned(current.kind,8);unsigned(current.format,8);unsigned(current.attributes,32)
 if not current.ordinal:raise UnsupportedBindingProfile('Current ordinal must be nonzero')
 if type(arrays) is not tuple or len(arrays)!=2 or any(type(x) is not tuple for x in arrays):raise UnsupportedBindingProfile('Both complete prepared array lists required')
 ordered=arrays[0]+arrays[1]
 if len(ordered)>65535:raise UnsupportedBindingProfile('Finite U16 combined array list')
 for array in ordered:
  if not isinstance(array,CompiledArray):raise UnsupportedBindingProfile('Explicit compiled array descriptor')
  identifier(array.identifier)
  for value in (array.first_field,array.last_field,array.element_limit):unsigned(value,16)
  unsigned(array.flags,8)
  if not array.first_field or array.first_field>array.last_field:raise UnsupportedBindingProfile('Ordinary nonempty inclusive array field range')
 selected=None;index=0
 if current.attributes&0x40:
  for i,array in enumerate(ordered,1):
   if array.first_field<=current.ordinal<=array.last_field:selected=array;index=i;break
 return FieldInfoView(current,selected is not None,index,selected,bool(current.attributes&0x100))


def bind_source_nodes(entries,nodes,current_fields,*,arrays,retain_calculated_values=True,
                      persistent_value_keys=frozenset()):
 """Return strict per-node source/current identities and native branch decisions.

    entries are immutable81 FieldEntry-like values; nodes are immutable69 Node-
    like values. Values remain untouched, including native-dropped/unused data.
    Numeric scalar correction eligibility excludes box/string/special kinds and
    Override8; it is not native SetValue permission or error-check success.
 """
 if type(entries) is not tuple or type(nodes) is not tuple or type(current_fields) is not tuple:
  raise UnsupportedBindingProfile('Explicit source-entry/node/current-field tuples')
 if type(retain_calculated_values) is not bool or type(persistent_value_keys) is not frozenset:
  raise UnsupportedBindingProfile('Explicit retain-calculated and persistent-value presence inputs')
 by_source={};source_ids=set()
 for entry in entries:
  index=unsigned(entry.source_field_index,16);full=identifier(entry.identifier)
  if not index or index in by_source or full in source_ids:raise UnsupportedBindingProfile('Unambiguous nonzero D2 source ordinal/ID required')
  by_source[index]=full;source_ids.add(full)
 current={};current_ordinals=set()
 for field_value in current_fields:
  info=prepared_field_info(field_value,arrays);full=identifier(field_value.identifier)
  if full in current or field_value.ordinal in current_ordinals:raise UnsupportedBindingProfile('Unique current full IDs and ordinals')
  current[full]=info;current_ordinals.add(field_value.ordinal)
 # Missing current membership blocks the finite import; never silently discard.
 if not source_ids<=current.keys():raise UnsupportedBindingProfile('Source D2 field absent from explicit current metadata')
 for key in persistent_value_keys:
  if type(key) is not tuple or len(key)!=2:raise UnsupportedBindingProfile('Explicit persistent (source field,element) keys')
  unsigned(key[0],16);unsigned(key[1],16)
 result=[];seen=set()
 for node in nodes:
  index=unsigned(node.field_index,16);element=unsigned(node.element_index,16)
  kind=unsigned(node.kind_byte,8);fmt=unsigned(node.flag10,8);attrs=unsigned(node.specific_attributes,16);header=unsigned(node.header,8)
  if (index,element) in seen:raise UnsupportedBindingProfile('Duplicate node keys need native first-match context')
  seen.add((index,element))
  significant=bool(attrs&9 or (index,element) in persistent_value_keys)
  if not significant and attrs==0 and header==0:
   # Identity is an inspector view even though native takes the pre-lookup drop.
   full=by_source.get(index);info=current.get(full)
   result.append(NodeBinding(index,element,full,info.field.ordinal if info else None,kind,fmt,attrs,'drop_empty_storage',False,info.array_index if info else 0,info.array.element_limit if info and info.array else None));continue
  full=by_source.get(index)
  if full is None:raise UnsupportedBindingProfile('Retained source node missing D2 ordinal')
  info=current[full];target=info.field
  action='ordinary_same_kind_format'
  if not retain_calculated_values and attrs&0xa==2:action='drop_computed_only'
  elif bool(element)!=info.array_member:action='requires_array_shape_recovery'
  elif kind!=target.kind or fmt!=target.format:action='requires_kind_format_conversion'
  elif kind==2:action='requires_box_group_fixup'
  elif kind in (6,7,8):action='requires_string_or_identity_context'
  elif kind!=13:action='requires_additional_scalar_codec'
  elif info.array is not None and element>info.array.element_limit:action='blocked_by_finite_array_limit_guard'
  eligible=action=='ordinary_same_kind_format' and bool(attrs&1) and not attrs&8
  result.append(NodeBinding(index,element,full,target.ordinal,kind,fmt,attrs,action,eligible,info.array_index,info.array.element_limit if info.array else None))
 return tuple(result)


def current_fields_from_template(template):
 """Adapter for an independently validated effective79 Template descriptor.

    Full carrier validation/order/selection and source provenance stay with the
    caller. This performs no XPRF IO, native registry/cache load or checksum join.
 """
 return tuple(CurrentField(identifier(value.field_id.encode('ascii')),value.ordinal,
                 value.kind,value.format,value.attributes) for value in template.fields)
