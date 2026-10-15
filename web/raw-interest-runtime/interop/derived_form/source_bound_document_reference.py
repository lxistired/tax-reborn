"""Explicit current-ID bindings over a document whose source ordinals stay intact."""
from dataclasses import dataclass,replace
from .source_bound_value_document_reference import (load_document_bytes,store_document_bytes,
 walk_forms,replace_form,TemplateContext,UnsupportedProfile)
from .source_field_binding_reference import (identifier,bind_source_nodes,UnsupportedBindingProfile)

@dataclass(frozen=True)
class BoundDocument:
 document:object
 context:object
 current_fields:dict
 arrays:dict
 bindings:dict
 native_fixup_performed:bool=False
 source_ordinals_preserved:bool=True

def _bindings(doc,fields,arrays):
 result={}
 for path,form in walk_forms(doc):
  if form.derived_tail is None:continue
  fs=doc.formsets[path[0]];key=(fs.header.identifier,form.header.identifier)
  if key not in fields or key not in arrays:raise UnsupportedProfile('Complete explicit current fields and both array lists for every ValueForm')
  try:result[path]=bind_source_nodes(form.derived_tail.field_map.entries,tuple(n for b in form.hash_state.buffers for n in b.nodes),fields[key],arrays=arrays[key])
  except UnsupportedBindingProfile as error:raise UnsupportedProfile(str(error)) from error
 return result

def load_source_bound_document_bytes(wire,buffers,*,template_context,current_fields,arrays):
 """Read one entire Entity with explicit current metadata, preserving source IDs.

    No source ordinal is assumed equal to a current ordinal. Source checksum
    expectations remain separate explicit TemplateContext inputs. This does not
    execute native load-recovery, conversion, events or current cache creation.
 """
 if type(current_fields) is not dict or type(arrays) is not dict:raise UnsupportedProfile('Explicit complete current field/array maps')
 if not isinstance(template_context,TemplateContext):raise UnsupportedProfile('Explicit source-bound TemplateContext')
 current_fields=dict(current_fields);arrays=dict(arrays);ids=dict(template_context.field_ids)
 for key,values in current_fields.items():
  if type(values) is not tuple:raise UnsupportedProfile('Explicit immutable CurrentField tuple')
  ids[key]={value.ordinal:identifier(value.identifier).rstrip(b' ') for value in values}
 context=replace(template_context,field_ids=ids,preserve_source_ordinals=True)
 doc=load_document_bytes(wire,buffers,template_context=context)
 return BoundDocument(doc,context,current_fields,arrays,_bindings(doc,current_fields,arrays))

def correct_bound_scalar(bound,path,field_id,element_index,raw64,*,exponent=None):
 """Correct only the selected ordinary Used/non-Override kind13 wire scalar.

    ID lookup uses D2 source identity. Original key, attrs, metadata, graph and
    every other node remain unchanged. It is not native SetValue/recalculation.
 """
 if not isinstance(bound,BoundDocument):raise UnsupportedProfile('Explicit source-bound document')
 full=identifier(field_id);matches=[v for v in bound.bindings.get(path,()) if v.field_id==full and v.element_index==element_index]
 if len(matches)!=1 or not matches[0].can_correct_source_scalar:raise UnsupportedProfile('Exact ordinary Used/non-Override source kind13 binding required')
 if type(raw64) is not int or not 0<=raw64<1<<64:raise UnsupportedProfile('Explicit U64 raw bits')
 if exponent is not None and (type(exponent) is not int or not 0<=exponent<=255):raise UnsupportedProfile('Explicit exponent byte')
 selected=matches[0];form=dict(walk_forms(bound.document))[path];blocks=[];changed=0
 for block in form.hash_state.buffers:
  values=[]
  for node in block.nodes:
   if (node.field_index,node.element_index)==(selected.source_field_index,element_index):
    node=replace(node,raw=raw64,**({} if exponent is None else {'exponent_byte':exponent}));changed+=1
   values.append(node)
  blocks.append(replace(block,nodes=tuple(values)))
 if changed!=1:raise UnsupportedProfile('Unambiguous original node required')
 doc=replace_form(bound.document,path,replace(form,hash_state=replace(form.hash_state,buffers=tuple(blocks))))
 return replace(bound,document=doc,bindings=_bindings(doc,bound.current_fields,bound.arrays))

def store_source_bound_document_bytes(bound,buffers):
 if not isinstance(bound,BoundDocument):raise UnsupportedProfile('Explicit source-bound document')
 if _bindings(bound.document,bound.current_fields,bound.arrays)!=bound.bindings:raise UnsupportedProfile('Bindings must match current source document')
 return store_document_bytes(bound.document,buffers,template_context=bound.context)
