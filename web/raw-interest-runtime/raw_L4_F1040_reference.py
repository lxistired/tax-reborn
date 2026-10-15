"""Same-source proposed L4 -> caller-resource field section -> proposed L8A.

The current source target is read through full D2/hash binding. Source section
instructions and dependency IDs are decoded from host-authenticated caller
bytes. This is a read-only staged comparison, not a document or TPS write.
"""
from decimal import Decimal as D
import struct
from current_raw_source_L4_reference import project_raw_source_L4
import source_calculation_reference as fields
from field_template_reference import read_id
from interop.derived_form.value_hash_wire_reference import find_value
from interop.form_core.hash_structure_reference import validate_document_hashes


def prepare_L8A_section(carrier,*,authority):
 if type(authority)is not dict or set(authority)!={'carrier_sha256','resource_id','records','source_form','source_field','target_form','target_field'}:raise ValueError('Externally approved exact L8A source-section authority required')
 if(authority['source_form'],authority['source_field'],authority['target_form'],authority['target_field'])!=('FSCHB','L4','F1040','L8A'):raise ValueError('Reviewed cross-form field pair required')
 data,frames=fields.index_carrier(fields.CarrierBytes('caller-resource',carrier,authority['carrier_sha256']));rid=authority['resource_id']
 if type(rid)is not int or type(authority['records'])is not dict or set(authority['records'])!={13100,3100}:raise ValueError('Exact field section and dependency records required')
 for typ,digest in authority['records'].items():
  if(typ,rid)not in frames or fields.sha(frames[typ,rid])!=digest:raise ValueError('Caller section/dependency record differs from approved identity')
 raw=data[3100,rid]
 if len(raw)<2:raise ValueError('Complete source dependency list required')
 count=struct.unpack_from('<H',raw)[0];at=2;dependencies=[]
 for _ in range(count):
  token,at=read_id(raw,at);dependencies.append(token.rstrip(b' ').decode('ascii'))
 if at!=len(raw):raise ValueError('Complete source dependencies required')
 program=fields._decode_program(data[13100,rid])
 if program.local_types or program.arrays or program.parameter_types:raise ValueError('Finite scalar section only')
 if any(row.opcode not in(0x88,0x89,0x86,0x52,0x12,3,0x85,0x72)for row in program.instructions):raise ValueError('Unknown cross-form instruction refused')
 return program,tuple(dependencies),dict(carrier_sha256=authority['carrier_sha256'],resource_type=13100,resource_id=rid,record_sha256=authority['records'][13100],body_sha256=fields.sha(data[13100,rid]),dependencies_record_sha256=authority['records'][3100])


def execute_L8A_section(program,dependencies,*,L4,prior,target_ordinal):
 if L4 is not None and(type(L4)is not D or not L4.is_finite()or abs(L4)>10**9 or L4*100!=(L4*100).to_integral_value()):raise ValueError('Finite exact source cents required')
 if prior is not None and(not isinstance(prior,fields.Record)or prior.kind!=12 or type(prior.amount)is not D or not prior.amount.is_finite()or abs(prior.amount)>10**9 or prior.amount!=prior.amount.to_integral_value()or type(prior.attributes)is not int or prior.attributes not in fields.ATTRS or prior.header!=0):raise ValueError('Actual current whole-dollar target prior required')
 rows={row.pc:row for row in program.instructions};stack=[];pc=program.start;trace=[];reads=[];assignments=[];value=prior;steps=0
 while pc<program.end:
  if pc not in rows or steps>64:raise ValueError('Finite aligned field-section flow required')
  steps+=1;row=rows[pc];op,payload=row.opcode,row.payload;next_pc=pc+len(row.raw)
  if op==0x88:
   index=struct.unpack('<H',payload)[0]
   if index>=len(dependencies)or dependencies[index]!='FSCHB':raise ValueError('Actual dependency must select same-owner FSCHB')
   stack.append(('form',dependencies[index]))
  elif op==0x89:
   if not stack or stack.pop()!=('form','FSCHB')or payload!=b'\1\0':raise ValueError('Existing ordinary same-owner form address required')
   stack.append(('address','FSCHB'))
  elif op==0x86:
   identifier,end=read_id(payload,0)
   if not stack or stack.pop()!=('address','FSCHB')or identifier.rstrip(b' ')!=b'L4'or payload[end:]!=bytes(3):raise ValueError('Exact current scalar FSCHB.L4 source required')
   stack.append(L4);reads.append(dict(form='FSCHB',field='L4',value=L4,origin='same_source_proposed_graph_result15174'))
  elif op==0x52:stack.append(D(struct.unpack('<i',payload)[0]))
  elif op==0x12:
   right,left=stack.pop(),stack.pop();stack.append((D(0)if left is None else left)>=(D(0)if right is None else right))
  elif op==3:
   condition=stack.pop()
   if type(condition)is not bool:raise ValueError('Exact section Boolean branch required')
   if not condition:next_pc=struct.unpack('<H',payload)[0]
  elif op==0x85:
   ordinal,flag=struct.unpack('<HB',payload)
   if flag or ordinal!=target_ordinal:raise ValueError('Source enterable target must match actual current L8A metadata')
   stack.append(('target','L8A'))
  elif op==0x72:
   proposed,target=stack.pop(),stack.pop()
   if target!=('target','L8A'):raise ValueError('Exact enterable L8A target required')
   if proposed is None:action='null_enterable_keeps_storage'
   elif value is not None and value.attributes&8:action='override8_keeps_storage'
   else:
    # Existing independently audited decimal -> kind12 conversion, preserving
    # the actual signed HALF_UP behavior of the finite source Assign path.
    exponent=max(0,-proposed.as_tuple().exponent);coefficient=int(proposed.scaleb(exponent));rounded=fields.function.typed(12,fields.function.Number(25,coefficient,exponent)).amount;value=fields.Record(12,rounded,3);action='computed_Used1_even_zero'
   assignments.append(dict(pc=pc,action=action,before=prior,after=value,physical_write=False))
  else:raise ValueError('Unsupported field-section instruction')
  trace.append(dict(pc=pc,opcode=op,next_pc=next_pc,raw_sha256=fields.sha(row.raw)));pc=next_pc
 if pc!=program.end or stack:raise ValueError('Exact normal section end and empty stack required')
 return dict(result=value,visible_value=None if value is None or not value.attributes&1 else value.amount,reads=reads,assignments=assignments,instructions=trace)


def project_raw_L4_into_F1040(request,*,binary_loader,authorities,caller_resource,resource_authority,field_carrier,field_authority):
 program,dependencies,section_source=prepare_L8A_section(field_carrier,authority=field_authority)
 loaded=None
 def same_loader(source):
  nonlocal loaded
  if source!=request['source']:raise ValueError('One unchanged source request required')
  if loaded is None:loaded=binary_loader(source)
  return loaded
 projected=project_raw_source_L4(request,binary_loader=same_loader,authorities=authorities,caller_resource=caller_resource,resource_authority=resource_authority)
 doc,buffers,bound,registry,selected,wire=loaded
 if getattr(bound,'document',None)is not doc or fields.sha(wire)!=projected['result']['source_sha256']:raise ValueError('Actual same-source full-ID current snapshot required')
 validate_document_hashes(doc);summary_path=tuple(request['summary_path']);fsindex=summary_path[0];fs=doc.formsets[fsindex];fsid=fs.header.identifier.decode('ascii').rstrip(' ');matches=[(i,f)for i,f in enumerate(fs.forms)if f.header.identifier.ljust(32,b' ')==b'F1040'.ljust(32,b' ')]
 if len(matches)!=1:raise ValueError('Exactly one actual existing F1040 source copy required')
 index,form=matches[0]
 if form.header.parent is not None or form.header.word7c!=0:raise ValueError('Root ordinary F1040 current copy0 required')
 identity=(field_authority['carrier_sha256'],field_authority['resource_id'])
 if selected.get((fsid,'F1040'))!=identity:raise ValueError('Actual F1040 current metadata differs from approved section home')
 template=registry.resolve(fsid,'F1040',identity);specs=[s for s in template.fields if s.field_id=='L8A']
 if len(specs)!=1 or(specs[0].kind,specs[0].format,specs[0].is_array)!=(12,0,False):raise ValueError('Actual current L8A whole-dollar metadata required')
 spec=specs[0];fid=b'L8A'.ljust(32,b' ');entries=[e for e in form.derived_tail.field_map.entries if e.identifier==fid]
 if len(entries)>1:raise ValueError('Unique full-ID source target binding required')
 source_ordinal=entries[0].source_field_index if entries else None;bindings=[b for b in bound.bindings.get((fsindex,index),())if b.field_id==fid or b.current_field_index==spec.ordinal]
 if len(bindings)>1:raise ValueError('Scalar target source cannot have extra array/current bindings')
 node=None if source_ordinal is None else find_value(form.hash_state,source_ordinal,0);prior=None
 if node is not None:
  if len(bindings)!=1:raise ValueError('Reachable target needs one actual full-ID binding')
  b=bindings[0]
  if(b.field_id,b.source_field_index,b.current_field_index,b.element_index,b.source_kind,b.source_format,b.fv_attributes)!=(fid,source_ordinal,spec.ordinal,0,12,0,node.specific_attributes)or b.native_action not in('preserve','requires_additional_scalar_codec','drop_empty_storage'):raise ValueError('Actual source/current target binding differs')
  if node.kind_byte!=12 or node.header!=0 or node.flag10!=0 or node.flag11 not in(0,204)or node.specific_attributes not in fields.ATTRS:raise ValueError('Unsupported actual target numeric header/kind/format/attributes')
  signed=node.raw if node.raw<1<<63 else node.raw-(1<<64)
  if abs(signed)>10**9:raise ValueError('Finite current whole target range exceeded')
  prior=fields.Record(12,D(signed),node.specific_attributes)
 elif bindings:raise ValueError('Target bindings without current reachable storage refused')
 section=execute_L8A_section(program,dependencies,L4=projected['result']['roots'][15174],prior=prior,target_ordinal=spec.ordinal)
 return dict(source_sha256=projected['result']['source_sha256'],raw_L4_projection=projected,proposed_L8A=section,source_section=section_source,target_identity=dict(document_path=[fsindex,index],document_file_copy_U32=form.header.file_copy,runtime_copy_number_U16=form.header.word7c,current_ordinal=spec.ordinal,source_ordinal=source_ordinal,stored_node_present=node is not None),owned_proposed_graph_result_as_external_field_operand=True,native_current_FSCHB_L4_writeback_executed=False,original_13100_reads_proposed_operand_not_reloaded_TPS=True,F1040_R2_whole_sequence_executed=False,native_factory_or_queue_executed=False,original_native_runtime=0,physical_writes=0,comparison_only=True,writeback_allowed=False)
