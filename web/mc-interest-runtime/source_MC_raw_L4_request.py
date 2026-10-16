"""One complete source/local resource -> owned actual MC -> raw L4/L8A.

Only selected L1 is moved through the actual owned MC receiver here. Other
formula suppliers and the previously documented retained cuts stay explicit.
"""
import json,hashlib
from pathlib import Path
import binary_tax,raw_interest_request as legacy
from source_mc import source_current_supplier as supplier
from source_mc_input import AUTHORITY_SHA256
from owned_MC_graph_bridge import ActualMCState,SourceSnapshot
from raw_L4_F1040_reference import project_raw_L4_into_F1040

def _calculate_request(request):
    if type(request)is not dict or set(request)!=legacy.KEYS or request.get('field_id')!='L1':
        raise ValueError('Exact source/local-resource L1 request required; no prepared MC/cache/program/amount arguments')
    raw=Path(__file__).with_name('source-mc-authority.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=AUTHORITY_SHA256:raise ValueError('Installed source MC authority changed')
    authority=json.loads(raw)
    result,loaded=supplier._read_source(request,authority)
    result,loaded,registry,compiled_fs=supplier._namespace(request,result,loaded,authority)
    result=supplier._root_UUID(request,result,loaded,registry,compiled_fs)
    result,(leaf,receiver,value,query)=supplier._MC(request,result,return_owned_objects=True)
    if len(value.rows)!=1:raise ValueError('One actual selected current MC source row required')
    state=ActualMCState(loaded[0],result['current_source'],receiver,value,leaf,next(iter(value.rows)))
    captured=SourceSnapshot(loaded,state)
    resource=legacy._bytes(request['local_resource'],legacy._AUTHORITY['resource']['carrier_sha256'])
    matches=[c for c in request['source']['carriers']if c['sha256']==legacy._AUTHORITY['L8A_field']['carrier_sha256']]
    if len(matches)!=1:raise ValueError('Actual same-source F1040 consumer carrier required')
    field=legacy._bytes(matches[0],legacy._AUTHORITY['L8A_field']['carrier_sha256'])
    current={k:v for k,v in request.items()if k!='local_resource'}
    def same_context(source):
        if source!=request['source']:raise ValueError('Source changed within actual MC/formula join')
        return captured
    joined=project_raw_L4_into_F1040(current,binary_loader=same_context,authorities=legacy._AUTHORITY['fields'],caller_resource=resource,
        resource_authority=legacy._AUTHORITY['resource'],field_carrier=field,field_authority=legacy._AUTHORITY['L8A_field'])
    if not state.consumptions:raise ValueError('Actual MC was not consumed by the raw formula')
    return legacy._json(dict(source_SHA256=result['current_source']['source_sha256'],binary_context_calls=result['binary_context_calls'],
        owned_MC_source_projection=result,original_raw_program_projection=joined,actual_MC_into_raw_prefix_consumptions=state.consumptions,
        selected_current_L1_supplied_by_executed_MC=True,original_programs_from_caller_resource=True,no_program_or_intermediate_arguments=True,
        other_prefix_inputs_still_direct_current_typed_suppliers=True,remaining_inputs_not_upgraded_to_full_GetMultiCopyInputValue=True,
        current_INPUT10770_fresh=False,saved_ADJUST_rebuilt=False,EE_MFS_only=True,native_Record_UUID_binding=False,
        native_active_cache_inventory=False,native_queue_executed=False,complete_original_GetMultiCopyInputValue=False,
        full_R2_executed=False,physical_TPS_writes=0,native_runtime=0,comparison_only=True,writeback_allowed=False))


def calculate_request(request):
    try:return _calculate_request(request)
    except ValueError as error:raise ValueError(str(error))from None
