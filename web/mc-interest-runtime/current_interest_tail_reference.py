"""One validated current document -> scalar prior facts -> conditional tax tail.

Five complete upstream cut-point results remain caller-supplied and are labelled
as such. These APIs never infer absent native inventories, recover row UUIDs,
write source fields, or claim a complete original return recalculation.
"""
from decimal import Decimal
import hashlib
from interest_snapshot_reference import read_snapshot
from strict_bint_row_scope_reference import reject_extra_bint_rows
from strict_actual_array_interest_reference import exact_source_owner_ids
from fresh_amt_prior_reference import require_all_saved_amt_priors_absent
from numeric_current_input_reference import StoredCents,current_numeric_input
from interop.derived_form.value_hash_wire_reference import find_value
from finite_interest_total_reference import TotalTail


def read_tail_priors(request,*,binary_loader,approved_profile,approved_targets):
    if type(request)is not dict or type(request.get('source'))is not dict:
        raise ValueError('Explicit current source request required')
    if type(approved_targets)is not list or len(approved_targets)!=8:
        raise ValueError('Trusted complete eight-target source metadata required')
    wanted={14726,14874,14879,14880,15169,15170,15173,15174}
    if any(type(p)is not dict or set(p)!={'reference','field_id','ordinal','kind','format','template_attributes'}for p in approved_targets):
        raise ValueError('Exact approved current target metadata required')
    if {p['reference']for p in approved_targets}!=wanted:raise ValueError('Complete original target set required')
    loaded=binary_loader(request['source']);doc,buffers,bound,registry,selected,wire=loaded
    if getattr(bound,'document',None)is not doc:raise ValueError('One identical document/current binding required')
    def same_loader(source):
        if source!=request['source']:raise ValueError('Source changed during one snapshot read')
        return loaded
    snapshot=read_snapshot(request,binary_loader=same_loader,approved_profile=approved_profile)
    proof=snapshot['owner_proof'];path=tuple(proof['summary_path']);summary=doc.formsets[path[0]].forms[path[1]]
    ids=exact_source_owner_ids(doc,proof)
    scope=reject_extra_bint_rows(doc,bound,path);uniform=require_all_saved_amt_priors_absent(doc,bound,path)
    source_sha=hashlib.sha256(wire).hexdigest()
    if source_sha!=proof['source_sha256']:raise ValueError('Source snapshot digest changed')
    fsid=proof['source_formset_id'];template=registry.resolve(fsid,'FSCHB',selected[fsid,'FSCHB'])
    priors={};traces=[];field_ids=set();ordinals=set()
    for plan in approved_targets:
        if type(plan['field_id'])is not str or not plan['field_id'].isascii()or not plan['field_id']or len(plan['field_id'])>32 or '\0'in plan['field_id']:
            raise ValueError('Exact finite field identifier required')
        fid=plan['field_id'].encode().ljust(32,b' ')
        if fid in field_ids or plan['ordinal']in ordinals:raise ValueError('Unique target ID and ordinal required')
        field_ids.add(fid);ordinals.add(plan['ordinal'])
        current=[f for f in template.fields if f.field_id==plan['field_id']]
        if len(current)!=1 or tuple(getattr(current[0],k)for k in('ordinal','kind','format','attributes'))!=tuple(plan[k]for k in('ordinal','kind','format','template_attributes')):
            raise ValueError('Exact approved target/current metadata mismatch')
        if(plan['kind'],plan['format'])!=(11,0):raise ValueError('Only exact source-reviewed current cents targets supported')
        if plan['reference']==14726:continue
        d2=[e for e in summary.derived_tail.field_map.entries if e.identifier==fid]
        if len(d2)>1:raise ValueError('Ambiguous source D2 full identifier')
        ordinal=d2[0].source_field_index if d2 else None
        node=find_value(summary.hash_state,ordinal,0)if ordinal is not None else None
        # Scalar target fields must not have a saved alternative array coordinate.
        for binding in bound.bindings[path]:
            if binding.field_id==fid and binding.element_index!=0:raise ValueError('Unexpected non-scalar target coordinate requires native interpretation')
        trace=dict(reference=plan['reference'],field_id=plan['field_id'],document_path=list(path),
            source_ordinal=ordinal,current_ordinal=plan['ordinal'],element_index=0,
            source_storage='D2_absent'if ordinal is None else'hash_node_absent'if node is None else'stored')
        attrs=0;value=None
        if node is not None:
            bindings=[b for b in bound.bindings[path]if b.field_id==fid and b.element_index==0]
            if len(bindings)!=1:raise ValueError('Exact scalar current binding required')
            binding=bindings[0]
            if(binding.source_field_index,binding.current_field_index,binding.source_kind,binding.source_format,binding.fv_attributes)!=(ordinal,plan['ordinal'],node.kind_byte,node.flag10,node.specific_attributes):
                raise ValueError('Current binding/D2/hash mismatch')
            if(node.kind_byte,node.flag10)!=(11,0)or binding.native_action not in('preserve','requires_additional_scalar_codec','drop_empty_storage'):
                raise ValueError('Unknown source/current scalar conversion refused')
            attrs=node.specific_attributes
            if attrs not in(0,1,2,3):raise ValueError('Prior scalar Override/Itemized/unknown attributes require native exterior assignment')
            value=current_numeric_input(StoredCents(node.kind_byte,node.raw,attrs,node.header,node.flag10,node.flag11,node.exponent_byte))
            trace.update(FV_attributes=attrs,raw64=str(node.raw),packed_exponent=node.exponent_byte,
                format_flag10=node.flag10,flag11=node.flag11,value_header=node.header)
        prior=dict(value=value,computed=bool(attrs&2),overridden=False,itemized=False)
        priors[plan['reference']]=prior
        trace.update(present=bool(attrs&1),prior_value=None if value is None else format(value,'f'),computed=bool(attrs&2))
        traces.append(trace)
    return dict(source_sha256=source_sha,scalar_priors=priors,scalar_prior_trace=traces,uniform_AMT_prior=uniform,
        strict_BINT_source_scope=scope,exact_source_owner_IDs=ids,prefix_snapshot=snapshot,
        current_source_storage_only=True,native_post_Load_defaults_verified=False,BINT_to_INT_row_identity_verified=False)


def compare_tail(request,*,binary_loader,approved_profile,approved_targets,program,expected_program_sha256,upstream_results):
    snapshot=read_tail_priors(request,binary_loader=binary_loader,approved_profile=approved_profile,approved_targets=approved_targets)
    engine=TotalTail(program,expected_sha256=expected_program_sha256,inputs=upstream_results,
        scalar_priors=snapshot['scalar_priors'],uniform_amt_prior=snapshot['uniform_AMT_prior'])
    roots=engine.run()
    def emit(value):
        if type(value)is Decimal:return format(value,'f')
        if type(value)is dict:return{str(k):emit(v)for k,v in value.items()}
        if type(value)is list:return[emit(v)for v in value]
        return value
    target_by_ref={p['reference']:p for p in approved_targets}
    proposals=[]
    for row in engine.assignments:
        plan=target_by_ref[row['reference']]
        proposals.append(dict(reference=row['reference'],field_id=plan['field_id'],current_ordinal=plan['ordinal'],
            computed_value=emit(row['computed_value']),proposed_value=emit(row['result']),retained_existing_Used=row['retained'],
            physical_row_identity_verified=False if row['reference']==14726 else None,can_commit_to_source=False))
    return dict(source_sha256=snapshot['source_sha256'],program_content_sha256=expected_program_sha256,roots=emit(roots),
        proposed_values=proposals,current_scalar_prior_trace=snapshot['scalar_prior_trace'],
        uniform_AMT_prior=snapshot['uniform_AMT_prior'],strict_BINT_source_scope=snapshot['strict_BINT_source_scope'],
        exact_source_owner_IDs=snapshot['exact_source_owner_IDs'],
        evaluated_references=engine.trace,upstream_cut_points=sorted(upstream_results),upstream_results_are_explicitly_supplied=True,
        source_complete_calculation=False,source_14725_complete_current_supply_verified=False,
        original_runtime=0,original_taxpayer_fixture=0,physical_writes=0,comparison_only=True,writeback_allowed=False,
        not_computed=['other7 concatenation source families','ThereAreAdjustments producer','manual adjustment current inventory',
            'EE8815 producer','main-form selector current supply','INT alphabetical native row-key mapping','native post-Load/defaults/global queue','R2 join'])
