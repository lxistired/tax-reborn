"""One exact same-label cache-miss path; no native cache state is supplied."""
import re

def _single(path,style):
    if type(path)is not bytes or not 1<=len(path)<=1024 or b'\0'in path or any(c>=128 for c in path):
        raise ValueError('Bounded ordinary ASCII source path required')
    if style not in(0,1):raise ValueError('Actual TPS0/MEF1 path style required')
    if style==1:
        if not path.startswith(b'/')or path.endswith(b'/')or b'//'in path:raise ValueError('Exact normal slash path only')
        parts=path[1:].split(b'/')
    else:
        parts=re.split(rb'[$:.!]',path)
        if any(not p for p in parts):raise ValueError('Exact normal nonempty TPS components only')
    if len(parts)!=4:raise ValueError('Exact reviewed four-component source shape required')
    mc=[]
    for index,part in enumerate(parts):
        m=re.fullmatch(rb'([A-Za-z_][A-Za-z_0-9]*)(?:\[([^\[\]]+)\])?',part)
        if m is None:raise ValueError('Normal one-level bracket grammar required')
        if m[2]is not None:mc.append((index,m[2]))
    if len(mc)!=1 or mc[0][0]!=2:raise ValueError('Exactly one third-component MC required')
    return tuple(parts),tuple(mc)

def same_label_cache_miss(mapping,tps_path):
    """Compute the conditional miss branch only, never choose current hit/miss.

    All three paths are supplied internally by the authenticated raw XML and
    saved149 source supplier. No row1, fileCopyID, random value or callback is
    used. This pure primitive is also exercised with explicit diagnostic paths.
    """
    if type(mapping)is not dict or mapping.get('Mapping_class')!='ordinary Mapping'or mapping.get('read_constraint_count')!=0:
        raise ValueError('Authenticated normal no-constraint Mapping shape required')
    mef_template=mapping['mef_path'].encode('ascii');tps_template=mapping['tps_path'].encode('ascii')
    mef_parts,mef_mc=_single(mef_template,1);_,tps_mc=_single(tps_template,0);actual_parts,actual_mc=_single(tps_path,0)
    # Real prefix literal is uuid_. Equality is exact length+memcmp, and lookup
    # picks the first MCInfo with the stored int32 component index.
    if mef_mc[0][1]!=b'uuid_1'or tps_mc[0][1]!=mef_mc[0][1]:
        raise ValueError('Unmatched/literal/multiple labels require excluded fallback branches')
    if tuple(p.split(b'[',1)[0]for p in actual_parts)!=tuple(p.split(b'[',1)[0]for p in _single(tps_template,0)[0]):
        raise ValueError('Actual TPS address must keep the authenticated source owner/field shape')
    index=next((i for i,label in tps_mc if label==mef_mc[0][1]),None)
    value=next((value for i,value in actual_mc if i==index),None)
    if not value:raise ValueError('No matching actual nonempty MC component at source definition index')
    # Request path is generated from canonical149; keep that finite condition,
    # rather than interpreting arbitrary opaque graph keys as native FormUUID.
    if re.fullmatch(rb'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',value)is None:
        raise ValueError('Canonical same-source FormUUID149 component required')
    out=list(mef_parts);mi=mef_mc[0][0];out[mi]=out[mi].split(b'[',1)[0]+b'['+value+b']'
    result=b''.join(b'/'+p for p in out)
    return dict(conditional_MEF_path=result.decode('ascii'),TPS_component_index=index,MEF_component_index=mi,
        actual_component_source='same selected child saved149 prospective TPS address',
        matched_definition_label='uuid_1',original_same_label_direct_branch='0x10156048b',
        original_find_by_index='0x10157ab10',original_replace_component='0x10157a990',
        UUIDCreationPolicy_consumed_on_this_direct_branch=False,group_UUID_map_consulted_on_this_direct_branch=False,
        random_UUID_generation_on_this_direct_branch=False,
        requires_current_14F_empty_lookup_result=True,requires_native_source149_current_path_equivalence=True,
        actual_current_lookup_or_path_equivalence_verified=False,
        native_map_update_and_Instance_return_executed=False,
        requires_normal_update_success_before_whole_reader_returns=True,
        conditional_branch_only=True,final_current_MEF_path=None,final_current_MEF_path_supplied=False,
        native_Mapping_executed=False,comparison_only=True,writeback_allowed=False)
