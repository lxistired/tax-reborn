"""Finite actual-current CS37 visible-value projection; no native writes.

Nine original temporary inputs are read from one actual v5 document. The
program body/metadata/arrays come only from complete SHA-bound source carriers.
The native INT LastIndex call is retained as a normal-success/error cut; its
numeric result is dead and is not replaced by zero. CS6/CS24 are not executed.
"""
from dataclasses import dataclass
from decimal import Decimal as D
import base64,hashlib,struct
import source_calculation_reference as source
from ADJUST_CS37_program_reference import decode
from native_tax_function_reference_private import Number,checked,typed,arithmetic,compare,whole
from numeric_current_input_reference import StoredCents,current_numeric_input
from actual_array_blocks_reference import verify_actual_array_blocks
from interop.form_core.effective_registry_fields_reference import Carrier,register_records
from interop.derived_form.value_hash_wire_reference import find_value
from interop.derived_form.string_wire_reference import read as read_string
from interop.form_core.hash_structure_reference import validate_document_hashes

FS='S2025US1040PER';ATTRS=(0,1,2,3,8,9,10,11);INPUTS=(172,173,174,175,176,181,182,183,187)
def _id(s):return s.encode('ascii').ljust(32,b' ')
@dataclass(frozen=True)
class Current:
 kind:int
 value:object
 Used:bool
 Override:bool
 source_attributes:int|None
 origin:str
@dataclass(frozen=True)
class Ref:
 local:int|None=None
 array:int|None=None
 row:int|None=None
 field:int|None=None
 enterable:bool=False
@dataclass(frozen=True)
class OpaqueNormalLastIndex:
 table:str='INT'
 minimum:int=0
 maximum:int=65535
 numeric_result_not_observed:bool=True

def _wire(entry):
 if type(entry)is not dict or set(entry)!={'base64','sha256'}:raise ValueError('Complete source-bound carrier bytes required')
 try:b=base64.b64decode(entry['base64'],validate=True)
 except Exception as e:raise ValueError('Invalid source carrier encoding')from e
 return b,entry['sha256']

def _prepare(request,authority):
 if type(authority)is not dict or set(authority)!={'carrier_sha256','resource_id','records','fields','arrays'}or authority['resource_id']!=42:raise ValueError('Host-approved exact CS37 resource authority required')
 entries=request.get('carriers')
 if type(entries)is not list or not 1<=len(entries)<=9:raise ValueError('Complete source carrier set required')
 maps=[];data=frames=None
 for entry in entries:
  wire,sha=_wire(entry);resources,records=source.index_carrier(source.CarrierBytes('source-resource',wire,sha));maps.append(Carrier(sha.encode(),resources))
  if sha==authority['carrier_sha256']:
   if data is not None:raise ValueError('Duplicate source program carrier refused')
   data,frames=resources,records
 if data is None:raise ValueError('Actual CS37 home must belong to the same source.carriers')
 for typ,digest in authority['records'].items():
  if source.sha(frames.get((int(typ),42),b''))!=digest:raise ValueError('Original CS37/metadata record differs')
 reg=register_records(tuple(maps));homes=[f for fs in reg.formsets if fs.identifier==_id(FS)for f in fs.forms if f.identifier==_id('FSCHB')]
 if len(homes)!=1 or len(homes[0].homes)!=1 or(homes[0].homes[0].source.carrier_key,homes[0].homes[0].source.resource_id)!=(authority['carrier_sha256'].encode(),42):raise ValueError('One complete same-source FSCHB metadata home required')
 program=decode(data[13036,42],hashlib.sha256(data[13036,42]).hexdigest())
 return {p['ordinal']:p for p in authority['fields']},program

def _state(node,form,kind):
 if node is None:return None
 used=bool(node.specific_attributes&1);override=bool(node.specific_attributes&8)
 if node.specific_attributes not in ATTRS or node.kind_byte!=kind or node.flag10!=0:raise ValueError('Exact current field kind/format/finite attributes required')
 if kind==11:
  amount=current_numeric_input(StoredCents(node.kind_byte,node.raw,node.specific_attributes,node.header,node.flag10,node.flag11,node.exponent_byte))
  value=None if amount is None else checked(Number(11,int(amount*100),2))
 elif kind==7:
  value=None
  if used:
   if node.header or node.raw>>32 or node.raw&0xffff!=form.table_id:raise ValueError('Current Used string requires exact own table and normal header')
   value=read_string(form.string_table,(node.raw>>16)&0xffff)
   if b'\0'in value or len(value)>4096:raise ValueError('Finite CString contents required')
 else:raise ValueError('Finite kind7/11 only')
 return Current(kind,value,used,override,node.specific_attributes,'loaded_current')

def _visible(state):return None if state is None or not state.Used else state.value

def execute(program,scalars,priors):
 """Normal allocation/conversion-success value semantics, no input callbacks.

 Opaque INT LastIndex supports only its actual dead local assignment. Any
 attempt to read/compare/use it refuses instead of inventing table inventory.
 """
 if set(scalars)!=set(INPUTS):raise ValueError('Every actual scalar source, including observed absence, required')
 rows=program['instructions'];by_pc={r['pc']:r for r in rows};nextpc={r['pc']:(rows[i+1]['pc']if i+1<len(rows)else 701)for i,r in enumerate(rows)}
 locals_={i:None for i in range(8)};arrays={6:{},7:{}};current=dict(priors);stack=[];trace=[];writes=[];pc=31;steps=0;query_count=0
 def pop():
  if not stack:raise ValueError('CS37 stack underflow')
  return stack.pop()
 def index(value,*,capacity):
  if not isinstance(value,Number)or value.kind!=10:raise ValueError('Actual whole kind10 array index required')
  n=whole(value)
  if not 1<=n<=capacity:raise ValueError('Exact one-based bounded CS37 index required')
  return n
 def assign_local(ref,value):
  if not isinstance(ref,Ref)or ref.field is not None:raise ValueError('Exact CS37 local reference required')
  if ref.array is not None:
   if ref.array not in(6,7):raise ValueError('Only actual fixed arrays6/7 required')
   row=index(Number(10,ref.row,0),capacity=7);kind=11 if ref.array==6 else 7
  else:kind=program['local_types'][ref.local]
  if isinstance(value,OpaqueNormalLastIndex):
   if ref.local!=4 or ref.array is not None:raise ValueError('Opaque INT query result may only inhabit its dead local4')
   assigned=value
  elif value is None:assigned=None
  elif kind==7:
   if type(value)is not bytes:raise ValueError('Actual String->String typed assignment required')
   assigned=value[:]
  else:
   if not isinstance(value,Number):raise ValueError('Actual finite numeric typed assignment required')
   assigned=typed(kind,value)
  if ref.array is not None:arrays[ref.array][row]=assigned
  else:locals_[ref.local]=assigned
 def write(ref,value,*,blank=False):
  if not isinstance(ref,Ref)or ref.field not in(27,28)or not 1<=ref.row<=64:raise ValueError('Exact bounded ADJUST current field reference required')
  key=(ref.field,ref.row);before=current.get(key);kind=7 if ref.field==27 else 11
  if before is not None and before.Override:after=before;action='Override8_retains_loaded_current'
  elif value is None and ref.enterable:after=before;action='null_enterable_retains_current'
  elif value is None:after=Current(kind,None,False,False,None,'proposed_visible_clear');action='nonenterable_CodeBlank_visible_clear'
  else:
   if kind==7 and type(value)is not bytes:raise ValueError('Actual ADJUST String assignment required')
   if kind==11:value=typed(11,value)
   after=Current(kind,value,True,False,None,'proposed_visible_value');action='normal_computed_visible_value'
  current[key]=after;writes.append(dict(pc=pc,field_ordinal=ref.field,element=ref.row,enterable=ref.enterable,operation='CodeBlank71'if blank else'AssignField72',value=value,before=before,after=after,action=action,native_SetCalcValue_flags=0 if value is None else 2,physical_attributes_or_node_removal_certified=False,can_commit_to_source=False))
 while pc!=701:
  steps+=1
  if steps>800 or pc not in by_pc:raise ValueError('Unknown instruction/loop bound refused')
  r=by_pc[pc];op=r['opcode'];payload=bytes.fromhex(r['payload_hex']);jump=nextpc[pc];entry=dict(pc=pc,opcode=op)
  if op==1:jump=struct.unpack('<H',payload)[0]
  elif op in(3,4):
   value=pop()
   if type(value)is not bool:raise ValueError('Actual comparison Boolean branch required')
   entry['condition']=value
   if op==3 and not value:jump=struct.unpack('<H',payload)[0]
   elif op==4 and value:stack.append(value);jump=struct.unpack('<H',payload)[0]
  elif op==0x52:stack.append(Number(10,struct.unpack('<i',payload)[0],0))
  elif op==0x51:stack.append(payload[:-1])
  elif op==0x56:stack.append(Ref(local=struct.unpack('<H',payload)[0]))
  elif op==0x58:
   i=struct.unpack('<H',payload)[0];value=locals_[i]
   if isinstance(value,OpaqueNormalLastIndex):raise ValueError('Dead native LastIndex became observable; unsupported')
   stack.append(value)
  elif op in(0x57,0x59):
   i=struct.unpack('<H',payload)[0];row=index(pop(),capacity=7)
   if i not in(6,7):raise ValueError('Only actual local arrays6/7 supported')
   stack.append(Ref(array=i,row=row)if op==0x57 else arrays[i].get(row))
  elif op==8:assign_local(pop(),None)
  elif op==7:
   value=pop();ref=pop();assign_local(ref,value)
  elif op==9:
   right,left=pop(),pop();value,arith=arithmetic(9,left,right);entry['arithmetic']=arith;stack.append(value)
  elif op in(0xf,0x10,0x11,0x13):
   right,left=pop(),pop();stack.append(compare(op,left,right))
  elif op==0x15:
   value=pop();stack.append(None if value is None else checked(Number(value.kind,-value.coefficient,value.exponent)))
  elif op==0x20:
   i=struct.unpack('<H',payload)[0];value=locals_[i]
   if i!=2 or not isinstance(value,Number)or value.kind!=10:raise ValueError('Exact native local2 index increment required')
   locals_[i]=typed(10,Number(10,whole(value)+1,0))
  elif op==0x83:
   field,mode=struct.unpack('<HB',payload)
   if field not in INPUTS or mode!=0:raise ValueError('Unknown current field read refused')
   value=_visible(scalars[field]);stack.append(value);entry.update(field=field,Used=scalars[field]is not None and scalars[field].Used,value=value)
  elif op in(0x84,0x85):
   field,mode=struct.unpack('<HB',payload)
   if field not in(27,28)or mode!=1:raise ValueError('Unknown current output address refused')
   stack.append(Ref(field=field,row=index(pop(),capacity=64),enterable=op==0x85))
  elif op==0x72:
   value=pop();write(pop(),value)
  elif op==0x71:write(pop(),None,blank=True)
  elif op==0x6d:
   if payload!=b'\0INT     ':raise ValueError('Exact original INT LastIndex query required')
   query_count+=1;stack.append(OpaqueNormalLastIndex());entry['native_query']='INT LastIndex normal-success value intentionally opaque; original query not executed'
  else:raise ValueError('Unsupported CS37 instruction refused')
  entry['next_pc']=jump;trace.append(entry);pc=jump
 if stack or query_count!=1:raise ValueError('Exact normal CS37 stack/query closure required')
 return dict(proposed_ADJUST_current=current,operations=writes,trace=trace,local_array_amounts=arrays[6],local_array_descriptions=arrays[7],selected_adjustment_count=len(arrays[6]),final_loop_limit=None if locals_[0]is None else whole(locals_[0]),normal_INT_LastIndex_result=locals_[4],normal_INT_query_success_is_a_condition=True,normal_INT_LastIndex_executed=False,source_or_storage_mutated=False)

def project_request(request,*,binary_loader,authority):
 if type(request)is not dict or set(request)!={'source','expected_source_sha256','source_formset_index'}or request['source'].get('profile',{}).get('format')!='tax-reborn-binary-entity-profile-v5':raise ValueError('Actual same-source v5 only; no prepared program/temporary amount/query result')
 plans,program=_prepare(request['source'],authority);doc,buffers,bound,registry,selected,wire=binary_loader(request['source']);digest=hashlib.sha256(wire).hexdigest()
 if digest!=request['expected_source_sha256']or getattr(bound,'document',None)is not doc:raise ValueError('One unchanged current source document required')
 validate_document_hashes(doc);fi=request['source_formset_index']
 if type(fi)is not int or not 0<=fi<len(doc.formsets):raise ValueError('Actual source FormSet index required')
 fs=doc.formsets[fi]
 if fs.header.identifier!=FS.encode():raise ValueError('Exact FSCHB current FormSet required')
 matches=[(i,f)for i,f in enumerate(fs.forms)if f.header.identifier==b'FSCHB']
 if len(matches)!=1:raise ValueError('Exactly one existing root FSCHB required')
 i,form=matches[0];path=(fi,i);identity=(authority['carrier_sha256'],42);key=(fs.header.identifier,form.header.identifier)
 if form.header.parent is not None or form.header.word7c!=0 or selected.get((FS,'FSCHB'))!=identity:raise ValueError('Exact selected root FSCHB current copy0 required')
 if bound.context.form_factories.get(key)!='value_form'or bound.context.table_factories.get(key)!='value_table':raise ValueError('Explicit current ValueForm/ValueTable factory required')
 template=registry.resolve(FS,'FSCHB',identity);arrays=verify_actual_array_blocks(bound,registry,formset_id=FS,form_id='FSCHB',approved_blocks=authority['arrays']);d2={};facts=[];byname={}
 for ordinal,p in plans.items():
  specs=[f for f in template.fields if f.field_id==p['field_id']]
  if len(specs)!=1 or tuple(getattr(specs[0],k)for k in('ordinal','kind','format','attributes'))!=tuple(p[k]for k in('ordinal','kind','format','attributes')):raise ValueError('Exact original current field metadata required')
  entries=[e for e in form.derived_tail.field_map.entries if e.identifier==_id(p['field_id'])]
  if len(entries)!=1:raise ValueError('Every consumed/target field requires explicit full-ID D2 binding')
  d2[ordinal]=entries[0].source_field_index;byname[p['field_id']]=ordinal
 if d2[28]!=d2[27]+1:raise ValueError('Finite contiguous source ADJUST field endpoints required')
 tables=[t for t in form.tables if t.identifier==b'ADJUST'];int_tables=[t for t in form.tables if t.identifier==b'INT']
 if len(tables)!=1 or(tables[0].word28,tables[0].word2a)!=(d2[27],d2[28])or not 0<=tables[0].last_used_record_index<=64:raise ValueError('Existing bounded ADJUST table required; missing is not native absence')
 # This is a precondition for the unexecuted normal INT query, not its value.
 if len(int_tables)!=1 or (int_tables[0].word28,int_tables[0].word2a)!=(d2[23],d2[24]):raise ValueError('Existing exact INT table endpoints required for the dead-value normal-query profile')
 scalar_nodes={};prior_nodes={};bindings=bound.bindings.get(path,())
 for b in bindings:
  name=b.field_id.rstrip(b' ').decode('ascii');ordinal=byname.get(name);is_adjust=(27<=b.current_field_index<=28 or d2[27]<=b.source_field_index<=d2[28])
  if ordinal is None:
   if is_adjust:raise ValueError('ADJUST source/current range intersects another field')
   continue
  p=plans[ordinal];element=b.element_index
  if ordinal in(23,24):continue
  if(ordinal in INPUTS and element!=0)or(ordinal in(27,28)and not 1<=element<=64):raise ValueError('Unsupported current scalar/table coordinate refused')
  node=find_value(form.hash_state,d2[ordinal],element)
  if node is None or(b.source_field_index,b.current_field_index,b.source_kind,b.source_format,b.fv_attributes)!=(d2[ordinal],ordinal,p['kind'],p['format'],node.specific_attributes):raise ValueError('Exact full-ID source/current binding required')
  if b.native_action not in('preserve','requires_additional_scalar_codec','requires_string_or_identity_context','drop_empty_storage'):raise ValueError('Unclosed field conversion refused')
  state=_state(node,form,p['kind']);facts.append(dict(field=name,source_ordinal=d2[ordinal],current_ordinal=ordinal,element=element,current=state,raw64=str(node.raw),packed_exponent_retained=node.exponent_byte))
  if ordinal in INPUTS:scalar_nodes[ordinal]=state
  else:prior_nodes[ordinal,element]=state
 # Reject a source hash node in the consumed intervals without a current binding.
 sources={v for k,v in d2.items()if k not in(23,24)}
 for block in form.hash_state.buffers:
  for node in block.nodes:
   if node.field_index in sources and not any(b.source_field_index==node.field_index and b.element_index==node.element_index and b.current_field_index in plans for b in bindings):raise ValueError('Unbound stored consumed coordinate refused')
 scalars={ordinal:scalar_nodes.get(ordinal)for ordinal in INPUTS}
 for ordinal,state in scalars.items():
  if state is None:facts.append(dict(field=plans[ordinal]['field_id'],source_ordinal=d2[ordinal],current_ordinal=ordinal,element=0,current=None,source_node_present=False))
 result=execute(program,scalars,prior_nodes)
 return dict(source_sha256=digest,source_identity=dict(document_path=list(path),document_file_copy_U32=form.header.file_copy,runtime_copy_number_U16=form.header.word7c),program_sha256=program['body_sha256'],actual_array_proof=arrays,loaded_current_facts=facts,**result,CS37_declared_dependencies=[6,24],CS6_CS24_executed=False,current_temporaries_fresh=False,ADJUST_physical_storage_written=False,source_4263_reloaded=False,source_14875_recomputed=False,normal_native_INT_query_executed=False,native_current_inventory=False,native_UUIDs=False,native_dependency_queue_executed=False,original_runtime=0,original_fixture=0,physical_writes=0,comparison_only=True,writeback_allowed=False,remaining=['Nine current temporary inputs are loaded priors, not fresh CS6 results','CS24 cleanup and native INT query failures are unexecuted','CodeBlank records proposed visible clear only; physical node/attributes/storage effects are not simulated','Untouched ADJUST rows and Override values remain; no table-wide clear is inferred','4263/14875/L4/R2 and native TPS row/UUID/queue execution are not performed'])
