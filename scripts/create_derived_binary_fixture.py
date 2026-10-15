"""Owned complete ValueForms; no original program/resource/return is an input."""
from pathlib import Path
from dataclasses import fields,replace
import base64,json,struct,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import create_binary_fixture as old
from interop.derived_form.source_bound_value_document_reference import (
 Document,FormNode,FormSetNode,TableRecord,TemplateContext,LinkRecord,store_document_bytes)
from interop.derived_form.entity_formset_reference import EntityHeader,FormSetHeader
from interop.derived_form.form_header_map_reference import Header,Parent
from interop.derived_form.string_wire_reference import Table,Chunk
from interop.derived_form.value_hash_wire_reference import Node,hash_for_nodes,NULL
from interop.derived_form.value_form_tail_reference import load_value_form_tail
from interop.derived_form.persistent_uuid_body_reference import NAME,store_form_uuid_body
from interop.derived_form.cx_string_wire_reference import Buffers,initialize

def copy_as(cls,value,**changes):
 names={f.name for f in fields(cls)}
 return cls(**{f.name:getattr(value,f.name) for f in fields(value) if f.name in names}|changes)

def tail(template,copy,*,opaque=False):
 values=sorted((field.field_id.encode().ljust(32,b' '),field.ordinal+100) for field in template.fields)
 payload=b''.join(b'\xff'+identifier+struct.pack('<H',ordinal) for identifier,ordinal in values)
 out=b'\xd2'+struct.pack('>HI',len(values),len(payload))+b'\x0f'+struct.pack('>I',len(payload))+payload
 uuid=('00000000-0000-0000-0000-%012x'%copy).encode()
 obj=bytes([0xd0,len(NAME)])+NAME+store_form_uuid_body(uuid)
 objects=[[obj],[],[]]
 if opaque:
  for group,name in enumerate((b'OWNED_FORM_NOTE',b'OWNED_ROW_NOTE',b'OWNED_VALUE_NOTE')):
   envelope=bytes([(0xd0,0xdd,0xdb)[group],len(name)])+name
   if group:envelope+=struct.pack('>HH',1,1)+b'\xff'+b'OWNED_ATTACHMENT'.ljust(32,b' ')
   objects[group].append(envelope+b'OWNED\0\xff\x80body')
 for group,items in enumerate(objects):
  capacity=max(1,len(items)*2);start=5+4*capacity;positions=[];body=b''
  for item in items:positions.extend((start+len(body),start+len(body)+len(item)));body+=item
  positions.extend([0xffffffff]*(capacity-len(positions)))
  out+=bytes([(0xd1,0xde,0xdf)[group]])+struct.pack('>HH',capacity,len(items)*2)+struct.pack('<'+'I'*capacity,*positions)+body
 return load_value_form_tail(out)

def fixture(*,used_array=False,opaque=False,hash_mode=None,hash_mutator=None):
 fsid,templates,_,profile,carriers,_=old.value_table_inputs()
 baseline=old.value_table_document(templates,fsid)
 ids={};counter=[0]
 def convert(form):
  counter[0]+=1;table_id=counter[0];name=form.header.identifier.decode();template=templates[name]
  spec={f.ordinal:f for f in template.fields}
  parent=copy_as(Parent,form.header.parent) if form.header.parent else None
  header=copy_as(Header,form.header,parent=parent,parent_field_index=form.header.parent_field_index+100 if parent else 0)
  nodes=[]
  for block in form.hash_state.buffers:
   for value in block.nodes:
    field=spec[value.field_index];attrs=value.specific_attributes
    if field.is_array and not used_array:attrs=2
    raw=(value.raw&~65535)|table_id if value.kind_byte==7 else value.raw
    nodes.append(copy_as(Node,value,next_index=NULL,field_index=value.field_index+100,
                         flag10=field.format,raw=raw,specific_attributes=attrs))
  strings=copy_as(Table,form.string_table,chunks=tuple(copy_as(Chunk,c) for c in form.string_table.chunks))
  tables=tuple(TableRecord(t.identifier,t.word28+100,t.word2a+100,last_used_record_index=t.last_used_record_index) for t in form.tables)
  links=tuple(copy_as(LinkRecord,l) for l in form.links)
  ids[fsid.encode(),form.header.file_copy]=table_id
  children=tuple(convert(child) for child in form.children)
  state=hash_for_nodes(tuple(nodes))
  if hash_mode:
   heads=list(state.heads)
   if hash_mode=='null':heads=[NULL]*len(heads)
   elif name=='FW2':
    wage=next(n for n in nodes if spec[n.field_index-100].field_id=='WAGES');bucket=(wage.field_index*3+wage.element_index*5)%len(heads)
    if hash_mode=='wrong_bucket':heads[(bucket+1)%len(heads)]=heads[bucket];heads[bucket]=NULL
    elif hash_mode=='out_of_range':heads[bucket]=999999
    else:raise ValueError('Owned test-only hash mode')
   state=replace(state,heads=tuple(heads))
  if hash_mutator is not None:state=hash_mutator(state)
  return FormNode(header,state,strings,table_id,tables=tables,
      children=children,links=links,derived_tail=tail(template,form.header.file_copy,opaque=opaque and name=='FW2'))
 forms=tuple(convert(f) for f in baseline.formsets[0].forms)
 doc=Document(copy_as(EntityHeader,baseline.entity_header),
     (FormSetNode(copy_as(FormSetHeader,baseline.formsets[0].header),forms),))
 keys={(fsid.encode(),name.encode()):'value_form' for name in templates}
 context=TemplateContext(template_versions={fsid.encode():2025},field_ids={
     key:{f.ordinal+100:f.field_id.encode() for f in templates[key[1].decode()].fields} for key in keys},
     current_table_ids=ids,form_factories=keys,table_factories={key:'value_table' for key in keys},
     relocatable_classes={key:frozenset((b'OWNED_FORM_NOTE',b'OWNED_ROW_NOTE',b'OWNED_VALUE_NOTE')) for key in keys} if opaque else {})
 buffers=initialize(Buffers(),prepared_compressed_pointer=1000,prepared_scratch_pointer=2000).buffers
 source=store_document_bytes(doc,buffers,template_context=context)
 arrays=[]
 for name,template in templates.items():
  rows=[dict(identifier='OWNED_ROWS',first_field=f.ordinal,last_field=f.ordinal,element_limit=10,flags=0) for f in template.fields if f.is_array]
  arrays.append(dict(formset_id=fsid,form_id=name,visible=rows,hidden=[]))
 profile={key:value for key,value in profile.items() if key!='table_factories'}
 profile.update(format='tax-reborn-binary-entity-profile-v4',
     form_factories=[dict(formset_id=fsid,form_id=name,form_kind='value_form',table_kind='value_table') for name in templates],
     compiled_arrays=arrays)
 return dict(base64=base64.b64encode(source).decode(),container='binary_entity',profile=profile,
             carriers=carriers,profile_acknowledged=True)

def build(destination):
 destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);entries={}
 for name,options in [('derived-income',{}),('derived-array',{'used_array':True}),('derived-opaque',{'opaque':True})]:
  request=fixture(**options);source=base64.b64decode(request['base64']);request_bytes=(json.dumps(request,sort_keys=True,indent=2)+'\n').encode()
  (destination/(name+'.taxbin')).write_bytes(source);(destination/(name+'-request.json')).write_bytes(request_bytes)
  entries[name]=dict(bytes=len(source),sha256=old.digest(source),request_sha256=old.digest(request_bytes))
 manifest=dict(vendor_resources_included=False,original_runtime_executions=0,original_tax_fixture=False,
     source_ordinals='current ordinal+100',source_checksum='explicit owned U32, not year validation',entries=entries)
 (destination/'derived-manifest.json').write_bytes((json.dumps(manifest,indent=2)+'\n').encode('utf-8'));return manifest

if __name__=='__main__':print(json.dumps(build(ROOT/'fixtures/binary-tax'),indent=2))
