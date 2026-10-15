"""One loaded actual-v5 document -> original scalar source collection14724.

No prepared amount/Boolean cuts are accepted. Existing scalar INPUT10770 is
reported as saved/current storage rather than freshly reaggregated. The
Canadian MFJ invariant/refusal boundary and all upstream refusals remain.
"""
import hashlib
from current_other_scalar_reference import project_other_scalar
from current_SMORT_reference import project_seller_interest
from current_F8891_reference import project_Canadian_interest
from finite_scalar_collection_reference import ScalarCollection


def project_scalar_collection(request,*,binary_loader,authorities,programs):
    keys={'source','expected_source_sha256','summary_path','source_formset_index','row_number','field_id','need_native_row_uuid'}
    if type(request)is not dict or set(request)!=keys or type(request['summary_path'])is not list or len(request['summary_path'])!=2 or request['source_formset_index']!=request['summary_path'][0]or request['field_id']!='L1'or request['row_number']!=1:raise ValueError('Exact same-FormSet scalar collection request required')
    if type(authorities)is not dict or set(authorities)!={'bank_profile','bank_entries','bank_targets','OID','H_targets','seller','Canadian'}:raise ValueError('All external authenticated source field authorities required')
    if type(programs)is not dict or set(programs)!={'other','seller','Canadian','collection'}or any(type(programs[k])is not dict or set(programs[k])!={'model','sha256'}for k in('seller','Canadian','collection')):raise ValueError('All external authenticated source program identities required')
    loaded=binary_loader(request['source']);digest=hashlib.sha256(loaded[-1]).hexdigest()
    def same_loader(source):
        if source!=request['source']:raise ValueError('Current source changed during scalar collection comparison')
        return loaded
    other_request={k:request[k]for k in keys if k!='source_formset_index'}
    other=project_other_scalar(other_request,binary_loader=same_loader,approved_bank_profile=authorities['bank_profile'],approved_entries=authorities['bank_entries'],approved_bank_targets=authorities['bank_targets'],approved_OID=authorities['OID'],approved_H_targets=authorities['H_targets'],programs=programs['other'])
    seller=project_seller_interest(request,binary_loader=same_loader,approved_profile=authorities['seller'],program=programs['seller']['model'],expected_program_sha256=programs['seller']['sha256'])
    Canadian=project_Canadian_interest(request,binary_loader=same_loader,approved_profile=authorities['Canadian'],program=programs['Canadian']['model'],expected_program_sha256=programs['Canadian']['sha256'])
    if any(p['source_sha256']!=digest for p in(other,seller,Canadian)):raise ValueError('All producers must share exactly one current source snapshot')
    components={**other['roots'],**seller['roots'],**Canadian['roots']}
    if set(components)!={14631,14643,14719,10770,14641,14722}:raise ValueError('All actual scalar producer outputs required')
    spec=programs['collection'];engine=ScalarCollection(spec['model'],expected_sha256=spec['sha256'],components=components);roots=engine.run()
    return dict(source_sha256=digest,roots=roots,evaluated_collection_references=engine.trace,actual_scalar_components=components,
        unfiltered_original_values=engine.cache[14723],original_source_conditions=engine.cache[14720],other_projection=other,seller_projection=seller,Canadian_projection=Canadian,
        original14724_from_current_source_inputs_recomputed=True,no_manual_Boolean_or_amount_cutpoints=True,all_current_facts_share_one_loaded_document=True,
        source10770_fresh_reaggregation=False,source10770_is_current_original_INPUT=True,whole14725_executed=False,whole_L4_or_R2_executed=False,
        native_record_inventory_verified=False,native_qualified_UUID_mapping_executed=False,native_autoiteration_executed=False,native_dependency_schedule_executed=False,TPS_output_conversion_executed=False,
        original_scalar_configuration_keys_are_not_runtime_UUID_proof=True,comparison_only=True,writeback_allowed=False,original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)
