"""One real loaded v5 source -> all eight bounded interest families ->14725.

No request can supply an intermediate amount or Boolean. External authority
supplies authenticated local program/metadata content. All existing-source
refusals and retained UserEntered storage remain in the upstream helpers.
"""
import hashlib
from interest_snapshot_reference import read_snapshot
from finite_interest_prefix_reference import Prefix
from strict_bint_row_scope_reference import reject_extra_bint_rows
from strict_actual_array_interest_reference import exact_source_owner_ids
from current_OID_taxable_amount_reference import project_OID_taxable_amount
from current_F6252_interest_reference import project_F6252_interest
from current_K1_interest_reference import project_K1_interest_families
from current_STKBASIS_reference import project_STKBASIS_interest
from current_scalar_collection_reference import project_scalar_collection
from current_EE_MFS_reference import project_EE_MFS
from finite_disjoint_interest_reference import SourceCollection

def project_all_interest_sources(request,*,binary_loader,authorities,programs):
 keys={'source','expected_source_sha256','summary_path','source_formset_index','row_number','field_id','need_native_row_uuid'}
 if type(request)is not dict or set(request)!=keys or type(request['summary_path'])is not list or len(request['summary_path'])!=2 or request['source_formset_index']!=request['summary_path'][0]or request['row_number']!=1 or request['field_id']!='L1'or request['need_native_row_uuid']is not False:raise ValueError('Exact same-source single-row interest request required; no manual cut-points')
 if type(authorities)is not dict or set(authorities)!={'scalar','K1','STKBASIS','F6252','EE'}:raise ValueError('All external authenticated source current profiles required')
 if type(programs)is not dict or set(programs)!={'prefix','OIDtaxable','K1','STKBASIS','F6252','scalar','collection','EE'}or any(type(programs[k])is not dict or set(programs[k])!={'model','sha256'}for k in programs if k!='scalar'):raise ValueError('All external authenticated source program identities required')
 loaded=binary_loader(request['source']);digest=hashlib.sha256(loaded[-1]).hexdigest()
 if digest!=request['expected_source_sha256']:raise ValueError('Exact original source byte snapshot required')
 def same_loader(source):
  if source!=request['source']:raise ValueError('Current source changed during complete source comparison')
  return loaded
 a=authorities['scalar'];bank_request={k:v for k,v in request.items()if k!='source_formset_index'};snapshot=read_snapshot(bank_request,binary_loader=same_loader,approved_profile=a['bank_profile']);doc,buffers,bound,registry,selected,wire=loaded;exact_source_owner_ids(doc,snapshot['owner_proof']);scope=reject_extra_bint_rows(doc,bound,request['summary_path']);bp=programs['prefix'];engine=Prefix(bp['model'],expected_sha256=bp['sha256'],inputs=snapshot['inputs'],prior_values=snapshot['prior_values']);bank=engine.run()
 if 14484 not in bank:raise ValueError('Original regular bank source output not actually computed')
 def call(fn,profile,program):
  spec=programs[program];return fn(request,binary_loader=same_loader,approved_profile=authorities[profile],program=spec['model'],expected_program_sha256=spec['sha256'])
 op=programs['OIDtaxable'];OID=project_OID_taxable_amount(bank_request,binary_loader=same_loader,approved_bank_profile=a['bank_profile'],approved_OID=a['OID'],program=op['model'],expected_program_sha256=op['sha256'])
 installment=call(project_F6252_interest,'F6252','F6252');K1=call(project_K1_interest_families,'K1','K1');stock=call(project_STKBASIS_interest,'STKBASIS','STKBASIS');scalar=project_scalar_collection(request,binary_loader=same_loader,authorities=a,programs=programs['scalar'])
 ep=programs['EE'];ee_request={k:request[k]for k in('source','expected_source_sha256','source_formset_index','need_native_row_uuid')};EE=project_EE_MFS(ee_request,binary_loader=same_loader,approved_profiles=authorities['EE'],program=ep['model'],expected_program_sha256=ep['sha256'])
 reports={'OID':OID,'F6252':installment,'K1':K1,'STKBASIS':stock,'scalar':scalar,'EE':EE}
 if any(o['source_sha256']!=digest for o in reports.values()):raise ValueError('Every source family and EE must share one loaded source snapshot')
 components={14484:bank[14484],**OID['roots'],**installment['roots'],**K1['roots'],**stock['roots'],**scalar['roots']};cp=programs['collection'];combined=SourceCollection(cp['model'],expected_sha256=cp['sha256'],components=components);roots=combined.run()
 return dict(source_sha256=digest,roots=roots,source_family_values=components,source_family_projections=reports,regular_bank_projection=dict(roots=bank,evaluated_references=engine.trace,proposed_assignments=engine.assignments,current_field_trace=snapshot['current_field_trace'],actual_array_proof=snapshot['actual_array_proof'],strict_row_scope=scope),
  concatenation_key_family_origins=combined.origins,evaluated_collection_references=combined.trace,fresh_EE_15167=EE['roots'][15167],
  all_eight_source_families_actually_computed=True,all_source_facts_share_one_loaded_document=True,missing_source_families_filled_empty=False,no_manual_Boolean_or_amount_cutpoints=True,original14725_from_bounded_current_source_recomputed=True,
  current_scalar_INPUT10770_fresh_reaggregation=False,disjoint_owned_key_numerical_projection_only=True,owned_labels_are_native_UUIDs=False,native_record_inventory_verified=False,native_qualified_UUID_mapping_executed=False,BINT_to_INT_row_identity_verified=False,
  native_autoiteration_executed=False,native_dependency_schedule_executed=False,original_assignment_flag_mutations_executed=False,TPS_output_conversion_executed=False,full_L4_R2_executed=False,comparison_only=True,writeback_allowed=False,original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)
