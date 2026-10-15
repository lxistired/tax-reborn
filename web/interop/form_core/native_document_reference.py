"""Independent recursive native document bytes, finite modern ordinary profile.

Actual C0/DC/C7/C8/C4/CB/C9/E0/E1/D7 structures; explicit template context.
Scalar primitives are BE, packed nodes and StreamMap arrays LE; swaptrue and
streamed-value branches are refused. Vendor runtime and taxpayer fixtures are
not executed. Limits inherited from bounded hash/string codecs are explicit.
"""
from dataclasses import dataclass,field,replace
import struct
from .entity_formset_reference import (EntityHeader,FormSetHeader,store_entity_header,
 load_entity_header,store_formset_header,load_formset_header,formset_swap_after,
 matches_platform,UnsupportedProfile)
from .form_header_map_reference import (Header,Parent,load_header,store_header,
 new_map,store_map,append_position,load_map,get_position,valid_id,u16,u32)
from .value_hash_wire_reference import (Hash,load_form_core_bytes,store_hash)
from .native_mode4_reference import store_selected_section
from .string_wire_reference import Table
from .value_table_header_reference import (TableHeader as BoundTableHeader,
 load_table_header,store_table_header)

@dataclass(frozen=True)
class TableRecord:
 identifier:bytes
 word28:int=0
 word2a:int=0
 metadata:dict=field(default_factory=dict,compare=False)
 table_kind:str='base_e1'
 last_used_record_index:object=None
@dataclass(frozen=True)
class LinkRecord:
 form_id:bytes
 file_copy:int
 field_id:bytes
 element_index:int=0
 resolved:bool=False
 metadata:dict=field(default_factory=dict,compare=False)
@dataclass(frozen=True)
class FormNode:
 header:Header
 hash_state:Hash
 string_table:Table
 table_id:int
 source_table_id:object=None
 tables:tuple=()
 children:tuple=()
 links:tuple=()
 metadata:dict=field(default_factory=dict,compare=False)
@dataclass(frozen=True)
class FormSetNode:
 header:FormSetHeader
 forms:tuple=()
 metadata:dict=field(default_factory=dict,compare=False)
@dataclass(frozen=True)
class Document:
 entity_header:EntityHeader
 formsets:tuple=()
 metadata:dict=field(default_factory=dict,compare=False)
 source_bytes:object=field(default=None,compare=False,repr=False)
 @property
 def header(self):return self.entity_header
@dataclass(frozen=True)
class TemplateContext:
 # Keys: template_versions[formsetID]; field_ids[(formsetID,formID)]={ordinal:fieldID};
 # current_table_ids[(formsetID,file_copy)]=u16. No template fetching is implied.
 template_versions:dict=field(default_factory=dict)
 field_ids:dict=field(default_factory=dict)
 current_table_ids:dict=field(default_factory=dict)
 preserve_unresolved_links:bool=True
 max_formsets:int=64
 max_forms:int=65534
 max_depth:int=64
 # The owning form factory selects table class; wire length never selects it.
 table_factories:dict=field(default_factory=dict)
 default_table_factory:object='base_e1'

STRING_KINDS=frozenset((4,5,6,7,8,9,21,24))
def is_string_kind(kind):
 if type(kind) is not int or not 0<=kind<32:raise UnsupportedProfile('Known 32-byte StringTypes table only')
 return kind in STRING_KINDS

def walk_forms(doc):
 """Yield stable ordinal paths and forms, parent before children."""
 if not isinstance(doc,Document):raise UnsupportedProfile('Explicit Document')
 def walk(forms,prefix):
  for i,f in enumerate(forms):
   p=prefix+(i,);yield p,f;yield from walk(f.children,p)
 for i,fs in enumerate(doc.formsets):yield from walk(fs.forms,(i,))

def replace_form(doc,path,updated_form):
 """Replace one form immutably; all unselected records/references survive."""
 if not isinstance(updated_form,FormNode) or type(path) is not tuple or len(path)<2:
  raise UnsupportedProfile('Explicit tuple path and FormNode')
 def changed(forms,indices):
  i=indices[0]
  if type(i) is not int or not 0<=i<len(forms):raise UnsupportedProfile('Existing ordinal form path')
  out=list(forms);out[i]=updated_form if len(indices)==1 else replace(out[i],children=changed(out[i].children,indices[1:]))
  return tuple(out)
 i=path[0]
 if type(i) is not int or not 0<=i<len(doc.formsets):raise UnsupportedProfile('Existing FormSet ordinal')
 out=list(doc.formsets);out[i]=replace(out[i],forms=changed(out[i].forms,path[1:]));return replace(doc,formsets=tuple(out))

def _context(c):
 if not isinstance(c,TemplateContext):raise UnsupportedProfile('Explicit TemplateContext required')
 if any(type(v) is not int or v<0 for v in (c.max_formsets,c.max_forms,c.max_depth)) or c.max_formsets>65534 or c.max_forms>1000000 or c.max_depth>64:
  raise UnsupportedProfile('Finite context limits: FormSets<=65534/forms<=1000000/depth<=64')
 if type(c.preserve_unresolved_links) is not bool:raise UnsupportedProfile('Explicit unresolved-link policy')
 if not isinstance(c.table_factories,dict) or c.default_table_factory not in (None,'base_e1','value_table'):
  raise UnsupportedProfile('Explicit supported table factories required')
 for key,kind in c.table_factories.items():
  if type(key) is not tuple or len(key)!=2 or any(type(x) is not bytes for x in key) or kind not in ('base_e1','value_table'):
   raise UnsupportedProfile('Table factory keys require FormSet/Form byte IDs and a supported kind')
  for identifier in key:valid_id(identifier)

def _entity(h):
 if not isinstance(h,EntityHeader) or h.kind!=0x45 or h.platform!=7 or h.schema!=18 or not 95<=h.release<=100:
  raise UnsupportedProfile('Selected Entity platform7/schema18/supported release95..100')

def _formset(h,c):
 if not isinstance(h,FormSetHeader):raise UnsupportedProfile('Explicit FormSetHeader')
 valid_id(h.identifier)
 if not h.identifier or h.schema!=18 or h.endian_flag or h.flags&0x10:
  raise UnsupportedProfile('Modern ordinary DC schema18/flag0/unstreamed only')
 if h.identifier not in c.template_versions or c.template_versions[h.identifier]!=h.template_version:
  raise UnsupportedProfile('Caller must supply matching template_version for every FormSet')
 # Current vendor writer zeroes these unknown fields. Refuse to import rather
 # than silently normalize caller data whose semantics are not established.
 if h.reserved_byte or len(h.reserved_words)!=9 or any(h.reserved_words):
  raise UnsupportedProfile('Nonzero unknown FormSet metadata cannot be silently zeroed')

def _error(code,where):
 if code is None:raise UnsupportedProfile('Unsupported finite codec profile at '+where)
 if code!=0:raise UnsupportedProfile('Native format error '+hex(code)+' at '+where)

def _write_index(marker,base,parts):
 if type(parts) is not tuple or len(parts)>65534:raise UnsupportedProfile('Nativeu16 StreamMap max65534 records')
 m=store_map(new_map(marker,len(parts)+1),base).mapping
 at=base+5+4*(len(parts)+1)
 for part in parts:
  m=append_position(m,at).mapping;at+=len(part)
 m=append_position(m,at).mapping
 return store_map(m,base).wire+b''.join(parts)

def _read_index(wire,p,marker,limit):
 r=load_map(wire[p:limit],marker,p);_error(r.code,'index '+hex(marker));m=r.mapping
 # Independent eligibility, stronger than the native weak StreamMap reader.
 if m.capacity!=m.used or not 1<=m.used<=65535:raise UnsupportedProfile('Canonical used/capacity nativeu16 index required')
 positions=tuple(get_position(m,i) for i in range(m.used))
 if positions[0]!=p+r.consumed or positions[-1]>limit or any(a>b for a,b in zip(positions,positions[1:])):
  raise UnsupportedProfile('Ordered nonwrapping section bounds required')
 return tuple(zip(positions,positions[1:])),positions[-1]

def _id(wire,p,*,nonempty=False):
 if p+2>len(wire):raise UnsupportedProfile('Complete ID length')
 n=struct.unpack_from('>H',wire,p)[0];p+=2
 if n>32 or p+n>len(wire) or(nonempty and not n):raise UnsupportedProfile('Complete ID in selected0..32 range')
 value=wire[p:p+n];valid_id(value);return value,p+n

def _table_kind(c,fsid,fid):
 kind=c.table_factories.get((fsid,fid),c.default_table_factory)
 if kind not in ('base_e1','value_table'):raise UnsupportedProfile('Declare the owning form table factory before reading or writing tables')
 return kind

def _table_load(w,*,table_kind='base_e1',entity_schema=18):
 try:record=load_table_header(w,entity_schema=entity_schema,table_kind=table_kind)
 except ValueError as error:raise UnsupportedProfile(str(error)) from error
 return TableRecord(record.identifier,record.word28,record.word2a,{'source_wire':w},
                    table_kind=table_kind,last_used_record_index=record.last_used_record_index)

def _table_store(t,*,table_kind='base_e1',entity_schema=18):
 if not isinstance(t,TableRecord):raise UnsupportedProfile('Explicit TableRecord')
 if t.table_kind!=table_kind:raise UnsupportedProfile('Table record must match its declared owning form factory')
 try:return store_table_header(BoundTableHeader(t.identifier,t.word28,t.word2a,t.last_used_record_index),entity_schema=entity_schema,table_kind=table_kind)
 except ValueError as error:raise UnsupportedProfile(str(error)) from error

def _link_description(l):return (l.form_id,l.file_copy,l.field_id,l.element_index)
def _link_load(w):
 a,p=_id(w,0,nonempty=True)
 if p+4>len(w):raise UnsupportedProfile('Complete link file-copy')
 copy=struct.unpack_from('>I',w,p)[0];p+=4
 if copy==0:raise UnsupportedProfile('Native link file-copy0 error5')
 b,p=_id(w,p,nonempty=True)
 if p+4!=len(w):raise UnsupportedProfile('Exact link descriptor boundary')
 element=struct.unpack_from('>I',w,p)[0]
 l=LinkRecord(a,copy,b,element&65535)
 return replace(l,metadata={'source_wire':w,'source_description':_link_description(l),'source_element_u32':element})

def _resolve(l,fsid,registry,c):
 target=registry.get(l.file_copy)
 fields=c.field_ids.get((fsid,l.form_id),{})
 return bool(target and target.identifier==l.form_id and isinstance(fields,dict) and any(type(index) is int and 0<index<=65535 and value==l.field_id for index,value in fields.items()))

def _link_store(l,fsid,registry,c):
 if not isinstance(l,LinkRecord):raise UnsupportedProfile('Explicit LinkRecord')
 valid_id(l.form_id);valid_id(l.field_id)
 if not l.form_id or not l.field_id or not l.file_copy:raise UnsupportedProfile('Native nonempty link IDs/nonzero file-copy')
 u32(l.file_copy);u16(l.element_index)
 if l.metadata.get('source_description')==_link_description(l):
  original=l.metadata.get('source_wire')
  if type(original) is not bytes or _link_description(_link_load(original))!=_link_description(l):raise UnsupportedProfile('Valid original link descriptor required')
  if not _resolve(l,fsid,registry,c) and not c.preserve_unresolved_links:raise UnsupportedProfile('Unresolved original link forbidden by explicit context')
  return original
 if not _resolve(l,fsid,registry,c):raise UnsupportedProfile('New or changed link requires prepared target and field-ID mapping')
 return struct.pack('>H',len(l.form_id))+l.form_id+struct.pack('>IH',l.file_copy,len(l.field_id))+l.field_id+struct.pack('>I',l.element_index)

def _remap(h,source,target):
 u16(target)
 if target==65535:raise UnsupportedProfile('Invalid current StringTableID FFFF')
 if source==target:return h,False
 out=[];changed=False
 for b in h.buffers:
  nodes=[]
  for n in b.nodes:
   if is_string_kind(n.kind_byte):
    if n.raw&65535:n=replace(n,raw=(n.raw&~65535)|target)
    else:changed=True
   nodes.append(n)
  out.append(replace(b,nodes=tuple(nodes)))
 return replace(h,buffers=tuple(out)),changed

def _validate_header_wire(w,h,parents):
 # Native strlen would discard bytes after NUL. Reject those bytes explicitly.
 _,p=_id(w,1);p+=12
 if p+2>len(w) or w[p]!=0xcb:raise UnsupportedProfile('Complete CB header')
 present=w[p+1];p+=2
 if present not in (0,1):raise UnsupportedProfile('Canonical parent-presence byte0/1')
 if present:
  _,p=_id(w,p);p+=6;_,p=_id(w,p);p+=4
 if p!=len(w):raise UnsupportedProfile('Exact form header boundary')
 r=load_header(w,parents=parents);_error(r.code,'form header')
 if r.header!=h:raise UnsupportedProfile('Source header typed/raw mismatch')

def load_document_bytes(wire,buffers,*,template_context):
 """Parse one buffer; retain metadata/references or refuse unsupported data."""
 c=template_context;_context(c)
 if type(wire) is not bytes or len(wire)>0xffffffff:raise UnsupportedProfile('Finite binary document bytes')
 eh=load_entity_header(wire);_error(eh.code,'C0')
 if not eh.recognized_C0:raise UnsupportedProfile('C0 eligibility; native wrongtag clearsheader and returns0')
 _entity(eh.header)
 if wire[:eh.consumed]!=store_entity_header(eh.header):raise UnsupportedProfile('Unrepresented Entity header metadata')
 ranges,end=_read_index(wire,eh.consumed,0xc7,len(wire))
 if end!=len(wire) or len(ranges)>c.max_formsets:raise UnsupportedProfile('Exact Entity bounds / explicit FormSet limit')
 formsets=[];seen_fs=set();total=0;used_ids=set()
 def load_form(start,end,fsid,registry,depth,path):
  nonlocal total
  total+=1
  if total>c.max_forms or depth>c.max_depth:raise UnsupportedProfile('Explicit total-form/depth limit')
  parents=tuple(registry.values())
  header=load_header(wire[start:end],parents=parents);_error(header.code,'C4/CB')
  h=header.header;valid_id(h.identifier)
  if not h.identifier or h.file_copy in registry:raise UnsupportedProfile('Nonempty form ID / duplicate file-copy (native205)')
  raw_header=wire[start:start+header.consumed];_validate_header_wire(raw_header,h,parents)
  pos=start+header.consumed
  if pos+2>end:raise UnsupportedProfile('Complete form saved StringTableID')
  saved=struct.unpack_from('>H',wire,pos)[0]
  requested=c.current_table_ids.get((fsid,h.file_copy),saved)
  if type(requested) is not int or not 0<=requested<65535:raise UnsupportedProfile('Explicit current per-form StringTableID0..FFFE')
  # Registry IDs are document-global. Preserve a unique saved ID by default;
  # duplicate saved IDs require caller-provided, unambiguous current IDs.
  if requested in used_ids:raise UnsupportedProfile('Duplicate current StringTableID; supply per-form current_table_ids')
  used_ids.add(requested)
  core=load_form_core_bytes(wire[start:end],buffers,base_position=start,current_table_id=saved,prepared_parents=parents)
  _error(core.code,'C9/value/string core')
  state,changed=_remap(core.hash_state,saved,requested)
  registry[h.file_copy]=Parent(h.identifier,h.file_copy,h.word7c)
  p=start+core.consumed
  tables_ranges,p=_read_index(wire,p,0xe0,end)
  tables=tuple(_table_load(wire[a:b],table_kind=_table_kind(c,fsid,h.identifier),
                          entity_schema=eh.header.schema) for a,b in tables_ranges)
  child_ranges,p=_read_index(wire,p,0xc8,end)
  children=tuple(load_form(a,b,fsid,registry,depth+1,path+(i,)) for i,(a,b) in enumerate(child_ranges))
  link_ranges,p=_read_index(wire,p,0xd7,end)
  links=tuple(_link_load(wire[a:b]) for a,b in link_ranges)
  if p!=end:raise UnsupportedProfile('Entire selected form record must be consumed')
  return FormNode(h,state,core.string_table,requested,saved,tables,children,links,
   {'source_header':h,'source_header_wire':raw_header,'source_path':path,'source_range':(start,end),
    'string_handles_changed_flag':changed,'entire_selected_form_record_consumed':True})
 for fi,(start,end) in enumerate(ranges):
  fh=load_formset_header(wire[start:end]);_error(fh.code,'DC')
  fs=fh.header;_formset(fs,c)
  if fs.identifier in seen_fs:raise UnsupportedProfile('Unique FormSet identifiers required for explicit context keys')
  seen_fs.add(fs.identifier)
  if fh.marker!=0xdc or wire[start:start+fh.consumed]!=store_formset_header(fs):raise UnsupportedProfile('Unrepresented or noncanonical FormSet metadata')
  if formset_swap_after(current_swap=not matches_platform(eh.header.platform),entity_schema=eh.header.schema,formset_endian_flag=fs.endian_flag):raise UnsupportedProfile('Actual swaptrue branch requires another codec')
  franges,fend=_read_index(wire,start+fh.consumed,0xc8,end)
  if fend!=end:raise UnsupportedProfile('Exact FormSet form-index end')
  registry={};forms=tuple(load_form(a,b,fs.identifier,registry,0,(fi,i)) for i,(a,b) in enumerate(franges))
  def links_resolved(f):
   links=tuple(replace(l,resolved=_resolve(l,fs.identifier,registry,c)) for l in f.links)
   if not c.preserve_unresolved_links and any(not l.resolved for l in links):raise UnsupportedProfile('Unresolved link forbidden by explicit context')
   return replace(f,children=tuple(links_resolved(ch) for ch in f.children),links=links)
  formsets.append(FormSetNode(fs,tuple(links_resolved(f) for f in forms),{'source_range':(start,end),'template_version_verified':True}))
 return Document(eh.header,tuple(formsets),
  {'source_profile':'platform7/schema18/ordinary/BEscalar/rawLE/swapfalse',
   'entire_selected_entity_consumed':True,'whole_tax_compatibility':False,
   'native_execution_count':0,'original_taxpayer_fixture_count':0,'form_count':total},wire)

def store_document_bytes(doc,buffers,*,template_context):
 """Write all represented records; preserve original deferred descriptors."""
 c=template_context;_context(c)
 if not isinstance(doc,Document) or type(doc.formsets) is not tuple:raise UnsupportedProfile('Explicit Document with tuple FormSets')
 _entity(doc.entity_header)
 if len(doc.formsets)>c.max_formsets:raise UnsupportedProfile('Explicit FormSet limit')
 total=0;used_ids=set();seen_fs=set()
 # Validate complete identity/reference graph before producing any bytes.
 registries={}
 for fs in doc.formsets:
  _formset(fs.header,c);fsid=fs.header.identifier
  if fsid in seen_fs:raise UnsupportedProfile('Unique FormSet identifiers')
  seen_fs.add(fsid);registry={}
  def prepare(forms,parents,depth):
   nonlocal total
   if type(forms) is not tuple or depth>c.max_depth:raise UnsupportedProfile('Explicit tuple forms / depth limit')
   for f in forms:
    total+=1
    if total>c.max_forms or not isinstance(f,FormNode):raise UnsupportedProfile('Explicit FormNode / total-form limit')
    h=f.header;valid_id(h.identifier)
    if not h.identifier or h.file_copy in registry:raise UnsupportedProfile('Nonempty form ID / duplicate file-copy (native205)')
    if h.parent is not None:
     found=registry.get(h.parent.file_copy)
     if found is None or found.identifier!=h.parent.identifier:raise UnsupportedProfile('Parent must precede child in same FormSet (native1F5)')
    if type(f.table_id) is not int or not 0<=f.table_id<65535 or f.table_id in used_ids:raise UnsupportedProfile('Unique valid per-form StringTableID required')
    expected=c.current_table_ids.get((fsid,h.file_copy),f.table_id)
    if expected!=f.table_id:raise UnsupportedProfile('Form.table_id must match explicit current_table_ids')
    used_ids.add(f.table_id);registry[h.file_copy]=Parent(h.identifier,h.file_copy,h.word7c)
    prepare(f.children,parents+(registry[h.file_copy],),depth+1)
  prepare(fs.forms,(),0);registries[fsid]=registry
 eh=store_entity_header(doc.entity_header);base=len(eh);fsbase=base+5+4*(len(doc.formsets)+1);out=[]
 def store_form(f,base,fsid):
  canonical,code=store_header(f.header);_error(code,'header store')
  header=canonical
  if f.metadata.get('source_header')==f.header:
   source=f.metadata.get('source_header_wire')
   if type(source) is not bytes:raise UnsupportedProfile('Original source header bytes required')
   _validate_header_wire(source,f.header,tuple(registries[fsid].values()));header=source
  h=store_hash(f.hash_state,buffers,version=18);_error(h.code,'hash store')
  s=store_selected_section(f.string_table,buffers,table_id=f.table_id,requested_share=0,actual_share=0)
  pos=base+len(header)+2
  m=store_map(new_map(0xc9,4),pos).mapping;valuepos=pos+21
  for at in (valuepos,valuepos+len(h.wire),valuepos+len(h.wire),valuepos+len(h.wire)+len(s.string_section)):
   m=append_position(m,at).mapping
  data=bytearray(header+s.table_id_wire+store_map(m,pos).wire+h.wire+s.string_section)
  data.extend(_write_index(0xe0,base+len(data),tuple(_table_store(t,
       table_kind=_table_kind(c,fsid,f.header.identifier),entity_schema=doc.entity_header.schema) for t in f.tables)))
  cb=base+len(data);at=cb+5+4*(len(f.children)+1);children=[]
  for child in f.children:
   w=store_form(child,at,fsid);children.append(w);at+=len(w)
  data.extend(_write_index(0xc8,cb,tuple(children)))
  data.extend(_write_index(0xd7,base+len(data),tuple(_link_store(l,fsid,registries[fsid],c) for l in f.links)))
  return bytes(data)
 for fs in doc.formsets:
  fh=store_formset_header(fs.header);fb=fsbase+len(fh);at=fb+5+4*(len(fs.forms)+1);forms=[]
  for f in fs.forms:
   w=store_form(f,at,fs.header.identifier);forms.append(w);at+=len(w)
  part=fh+_write_index(0xc8,fb,tuple(forms));out.append(part);fsbase+=len(part)
 return eh+_write_index(0xc7,base,tuple(out))
