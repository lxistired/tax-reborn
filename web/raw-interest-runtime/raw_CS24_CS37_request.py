"""Private source-first prospective CS24 -> CS37 -> ADJUST amount consequence.

The only amounts enter from an actual current document and raw caller-owned
resources. Graph proposals are prospective operands, never declared reloaded
TPS storage. A graph blank that would need to clear a loaded Used temporary is
refused because the native blank/deletion branch has not executed here.
"""
from pathlib import Path
from decimal import Decimal as D
import sys,json,hashlib
B=Path(__file__).resolve().parent
import raw_interest_request as original
from raw_L4_F1040_reference import project_raw_L4_into_F1040,prepare_L8A_section,execute_L8A_section
from raw_interest_program_reference import compile_current_interest_programs
from current_interest_tail_reference import read_tail_priors
from finite_interest_total_reference import TotalTail
from current_ADJUST_CS37_reference import project_request as project_stored,execute,Current,Number,_prepare
from CS24_declarations_reference import decode
import source_calculation_reference as source
_JOIN=json.loads((B/'CS24-runtime-authority.json').read_text());_CS37=json.loads((B/'CS37-resource-authority.json').read_text());_AUTH=original._AUTHORITY

def calculate_request(request):
 if type(request)is not dict or set(request)!=original.KEYS:raise ValueError('Exact raw-resource/current document request only; no program, temporary or ADJUST arguments')
 raw=original._bytes(request['local_resource'],_AUTH['resource']['carrier_sha256']);source_request=request['source'];entries=source_request.get('carriers')
 if type(entries)is not list:raise ValueError('Same-source complete carrier set required')
 home=[e for e in entries if e.get('sha256')==_CS37['carrier_sha256']]
 if len(home)!=1:raise ValueError('One exact same-source CS24/CS37 field-program carrier required')
 field15=original._bytes(home[0],_CS37['carrier_sha256']);data,frames=source.index_carrier(source.CarrierBytes('same-source CS24 home',field15,_CS37['carrier_sha256']))
 if source.sha(frames.get((13023,42),b''))!=_JOIN['CS24_resource']['record_sha256']:raise ValueError('Actual CS24 record differs')
 declarations=decode(data[13023,42],_JOIN['CS24_resource']['body_sha256']);field_entries=[e for e in entries if e.get('sha256')==_AUTH['L8A_field']['carrier_sha256']]
 if len(field_entries)!=1:raise ValueError('One same-source F1040 section carrier required')
 field01=original._bytes(field_entries[0],_AUTH['L8A_field']['carrier_sha256']);current={k:v for k,v in request.items()if k!='local_resource'};loaded=None;actual_context_calls=0
 def loader(payload):
  nonlocal loaded,actual_context_calls
  if payload!=source_request:raise ValueError('One unchanged source request required')
  if loaded is None:actual_context_calls+=1;loaded=original.binary_tax._context(payload)
  return loaded
 baseline=project_raw_L4_into_F1040(current,binary_loader=loader,authorities=_AUTH['fields'],caller_resource=raw,resource_authority=_AUTH['resource'],field_carrier=field01,field_authority=_AUTH['L8A_field'])
 loaded_projection=project_stored(dict(source=source_request,expected_source_sha256=current['expected_source_sha256'],source_formset_index=current['source_formset_index']),binary_loader=loader,authority=_CS37)
 if loaded_projection['source_identity']['document_path']!=current['summary_path']:raise ValueError('Same actual root FSCHB owner required')
 if any(f['current_ordinal']==28 and f['current']is not None and f['current'].Used for f in loaded_projection['loaded_current_facts']):raise ValueError('Existing Used ADJUST amounts need the unexecuted complete native cleanup/inventory protocol; prospective source profile refused')
 produced=baseline['raw_L4_projection']['result']['adjustment_presence_projection']['proposed_temporary_writes'];byref={p['reference']:p for p in produced}
 if len(produced)!=9 or len(byref)!=9 or set(byref)!={p['reference']for p in _JOIN['targets']}:raise ValueError('All nine temporary nodes must actually be recomputed')
 actual={f['current_ordinal']:f['current']for f in loaded_projection['loaded_current_facts']if f['current_ordinal']in(172,173,174,175,176,181,182,183,187)};operands={};propagation=[]
 for p in _JOIN['targets']:
  row=byref[p['reference']];value=row['result'];prior=actual[p['ordinal']];visible=None if prior is None or not prior.Used else prior.value
  if prior is not None and prior.Override:raise ValueError('Native forced-output/temporary Override branch not supported by this source chain')
  if value is None and visible is not None:raise ValueError('Blank TKE output would need native deletion of a Used temporary; source propagation refused')
  if value is not None and(type(value)is not D or not value.is_finite()or abs(value)>10**9 or value*100!=(value*100).to_integral_value()):raise ValueError('Exact finite computed temporary cents required')
  prospective=None if value is None else Number(11,int(value*100),2)
  operands[p['ordinal']]=Current(11,prospective,value is not None,False,None,'owned_prospective_CS24_graph_operand')
  propagation.append(dict(reference=p['reference'],field_id=p['field_id'],ordinal=p['ordinal'],loaded_prior=prior,computed_value=row['computed_value'],graph_assignment_result=value,graph_retained_existing_Used=row['retained_existing_Used'],CS24_declared_scalar_element_operand=0,prospective_operand=prospective,native_TPS_written_or_reloaded=False,physical_Used_attributes_certified=False))
 _,program=_prepare(source_request,_CS37);priors={}
 for f in loaded_projection['loaded_current_facts']:
  if f['current_ordinal']in(27,28):priors[f['current_ordinal'],f['element']]=f['current']
 prospective=execute(program,operands,priors)
 # The consumer is the already reviewed raw14727/14875/L4 graph. These owned
 # labels carry proposed row values only. No native UUID/row inventory is read
 # or fabricated, and no proposed value is written into the source document.
 adjustments={f'owned-proposed-CS37-row:{row}':None if state is None or not state.Used else state.value.amount for(field,row),state in prospective['proposed_ADJUST_current'].items()if field==28}
 compiled=compile_current_interest_programs(raw,authority=_AUTH['resource']);bank=_AUTH['fields']['all_sources']['scalar'];bank_request={k:v for k,v in current.items()if k!='source_formset_index'};pri=read_tail_priors(bank_request,binary_loader=loader,approved_profile=bank['bank_profile'],approved_targets=_AUTH['fields']['tail_targets']);base_result=baseline['raw_L4_projection']['result'];inputs=dict(base_result['actual_internal_producer_values']);inputs[4263]=adjustments;tp=compiled['programs']['tail'];engine=TotalTail(tp['model'],expected_sha256=tp['sha256'],inputs=inputs,scalar_priors=pri['scalar_priors'],uniform_amt_prior=pri['uniform_AMT_prior']);roots=engine.run()
 section,dependencies,section_identity=prepare_L8A_section(field01,authority=_AUTH['L8A_field']);before=baseline['proposed_L8A'];prior=before['assignments'][0]['before']if before['assignments']else before['result'];l8a=execute_L8A_section(section,dependencies,L4=roots[15174],prior=prior,target_ordinal=baseline['target_identity']['current_ordinal'])
 if actual_context_calls!=1:raise ValueError('One actual current binary parse required')
 return original._json(dict(source_sha256=current['expected_source_sha256'],one_actual_binary_context=True,binary_context_calls=actual_context_calls,baseline_observed_ADJUST_result=dict(L4=base_result['roots'][15174],L8A=before['visible_value']),CS24_original_body_sha256=declarations['body_sha256'],CS24_scalar_output_declarations=declarations['output_declarations'],nine_source_TKE_producers_actually_evaluated=True,temporary_operand_propagation=propagation,prospective_CS37=prospective,proposed_ADJUST_numeric_values=adjustments,prospective_tail_roots=roots,prospective_F1040_L8A=l8a,tail_evaluated_references=engine.trace,proposed_tail_assignments=engine.assignments,raw_resource_provenance=baseline['raw_L4_projection']['resource_provenance'],same_snapshot_identity=loaded_projection['source_identity'],no_manual_program_amount_or_Boolean_arguments=True,owned_prospective_program_order=True,native_CS24_executed=False,native_temporary_TPS_write_reload_executed=False,native_CS37_executed=False,source_4263_reloaded=False,native_TPS_output_conversion_executed=False,native_record_inventory=False,native_UUIDs=False,native_queue_executed=False,current_INPUT10770_fresh=False,full_R2_executed=False,comparison_only=True,writeback_allowed=False,physical_writes=0,original_runtime=0,original_fixture=0,remaining=['Prospective scalar graph outputs are not actual TPS current storage; write/blank deletion/queue still unexecuted','Actual INT LastIndex query success remains a condition; dead result never replaced by0','Existing Used ADJUST amounts are refused; Unused/Override follows exact source CS37 projection','INPUT10770 remains loaded prior; SELLFIN14619 output mapping/CS5/CS11 not executed','EE MFS invariant, previous current targets and native inventory/UUID/fullR2 limitations remain']))
