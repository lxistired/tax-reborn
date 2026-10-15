"""Same source actual-v5 fields -> bounded regular-bank adjustment graph.

All current fields are read through full-ID D2 bindings and reachable hash
lookup. The row/copy keys are owned comparison labels, never native UUIDs.
"""
from decimal import Decimal
import hashlib
from current_adjustment_reference import read_adjustment_selector
from interest_snapshot_reference import read_snapshot
from finite_normal_adjustment_reference import NormalAdjustment
from current_string_input_reference import current_string_input
from numeric_current_input_reference import StoredCents,current_numeric_input
from strict_bint_row_scope_reference import reject_extra_bint_rows
from strict_actual_array_interest_reference import exact_source_owner_ids
from interop.derived_form.value_hash_wire_reference import find_value


def read_current_adjustment_targets(loaded,request,*,approved_profile,approved_targets):
    if type(approved_targets)is not list or len(approved_targets)!=10 or len({p.get('reference')for p in approved_targets})!=10:
        raise ValueError('One current String prior and all nine temporary numeric target plans required')
    doc,buffers,bound,registry,selected,wire=loaded;path=tuple(request['summary_path']);fs=doc.formsets[path[0]]
    summary=fs.forms[path[1]];fsid=fs.header.identifier.decode().rstrip(' ')
    children=[(path+(i,),f)for i,f in enumerate(summary.children)if f.header.identifier.ljust(32,b' ')==b'F1099I'.ljust(32,b' ')]
    if len(children)!=1:raise ValueError('One existing direct F1099I required')
    childpath,child=children[0];result={};traces=[]
    for plan in approved_targets:
        keys={'reference','form_id','field_id','ordinal','kind','format','template_attributes'}
        if type(plan)is not dict or set(plan)!=keys:raise ValueError('Exact trusted current target metadata required')
        is_string=plan['form_id']=='F1099I'
        if is_string:
            if plan['kind']!=7:raise ValueError('Current String target kind required')
            form,formpath=child,childpath;identity=approved_profile['child_identity']
        elif plan['form_id']=='FSCHB'and plan['kind']==11:
            form,formpath=summary,path;identity=approved_profile['summary_identity']
        else:raise ValueError('Unknown target form or numeric kind')
        if tuple(selected.get((fsid,plan['form_id']),()))!=tuple(identity):raise ValueError('Exact target source template identity required')
        template=registry.resolve(fsid,plan['form_id'],identity);fields=[f for f in template.fields if f.field_id==plan['field_id']]
        if len(fields)!=1 or tuple(getattr(fields[0],k)for k in('ordinal','kind','format','attributes'))!=tuple(plan[k]for k in('ordinal','kind','format','template_attributes')):
            raise ValueError('Target current metadata differs')
        fid=plan['field_id'].encode().ljust(32,b' ');entries=[e for e in form.derived_tail.field_map.entries if e.identifier==fid]
        if len(entries)>1:raise ValueError('Ambiguous full-ID D2 target')
        source=entries[0].source_field_index if entries else None
        bindings=[b for b in bound.bindings.get(formpath,())if b.field_id==fid or b.current_field_index==plan['ordinal']]
        if len(bindings)>1 or any(b.element_index!=0 for b in bindings):raise ValueError('One exact scalar target coordinate required')
        node=find_value(form.hash_state,source,0)if source is not None else None
        trace=dict(reference=plan['reference'],form_id=plan['form_id'],field_id=plan['field_id'],document_path=list(formpath),
            source_ordinal=source,current_ordinal=plan['ordinal'],element_index=0,
            source_storage='D2_absent'if source is None else'hash_node_absent'if node is None else'stored')
        value=None;attrs=0
        if node is not None:
            if len(bindings)!=1:raise ValueError('Stored target needs exactly one current binding')
            b=bindings[0]
            if(b.source_field_index,b.current_field_index,b.field_id,b.source_kind,b.source_format,b.fv_attributes)!=(source,plan['ordinal'],fid,node.kind_byte,node.flag10,node.specific_attributes):raise ValueError('Source/current target binding differs')
            if(node.kind_byte,node.flag10)!=(plan['kind'],plan['format']):raise ValueError('Unclosed target conversion')
            action=b.native_action
            if action not in('preserve','requires_additional_scalar_codec','requires_string_or_identity_context')and not(action=='drop_empty_storage'and not node.specific_attributes&1):raise ValueError('Unclosed native target action')
            attrs=node.specific_attributes
            if attrs not in(0,1,2,3,8,9,10,11):raise ValueError('Unknown current target attributes')
            if attrs&8:raise ValueError('Exterior target Override protocol remains unclosed')
            value=current_string_input(node,table=form.string_table,table_id=form.table_id)if is_string else current_numeric_input(
                StoredCents(node.kind_byte,node.raw,attrs,node.header,node.flag10,node.flag11,node.exponent_byte))
            trace.update(kind=node.kind_byte,FV_attributes=attrs,raw64=str(node.raw),packed_exponent=node.exponent_byte,
                value_header=node.header,format_flag10=node.flag10,flag11=node.flag11,native_action=action)
        elif bindings:raise ValueError('Binding points at missing current target storage')
        trace.update(present=bool(attrs&1),value_hex=value.hex()if type(value)is bytes else None,
            value_decimal=format(value,'f')if type(value)is Decimal else None)
        traces.append(trace);result[plan['reference']]=dict(value=value,computed=bool(attrs&2),overridden=False,itemized=False)
    return dict(priors=result,current_target_trace=traces,source_sha256=hashlib.sha256(wire).hexdigest(),
        observed_saved_absence_is_not_native_runtime_blank=True)


def project_normal_adjustments(request,*,binary_loader,approved_profile,approved_entries,approved_targets,program,expected_program_sha256):
    loaded=binary_loader(request['source']);doc,buffers,bound,registry,selected,wire=loaded
    def same_loader(source):
        if source!=request['source']:raise ValueError('Source changed during current adjustment read')
        return loaded
    snapshot=read_snapshot(request,binary_loader=same_loader,approved_profile=approved_profile)
    exact_source_owner_ids(doc,snapshot['owner_proof']);rowproof=reject_extra_bint_rows(doc,bound,request['summary_path'],first_row=1)
    selector=read_adjustment_selector(request,binary_loader=same_loader,approved_profile=approved_profile,approved_entries=approved_entries)
    priors=read_current_adjustment_targets(loaded,request,approved_profile=approved_profile,approved_targets=approved_targets)
    digest=hashlib.sha256(wire).hexdigest()
    if any(x!=digest for x in(snapshot['owner_proof']['source_sha256'],selector['source_sha256'],priors['source_sha256'])):raise ValueError('Different current source snapshots')
    string_targets=[p['reference']for p in approved_targets if p['kind']==7]
    if len(string_targets)!=1:raise ValueError('One explicit source String UserEntered target required')
    ref=string_targets[0];current_priors={**snapshot['prior_values'],ref:{snapshot['source_label']:priors['priors'][ref]}}
    engine=NormalAdjustment(program,expected_sha256=expected_program_sha256,
        inputs={**snapshot['inputs'],selector['reference']:selector['input_value']},prior_values=current_priors)
    roots=engine.run()
    return dict(source_sha256=digest,program_content_sha256=expected_program_sha256,roots=roots,
        evaluated_references=engine.trace,proposed_graph_assignments=engine.assignments,product_blank_condition_trace=engine.blank_trace,
        rounding_trace=engine.rounding,current_field_trace=snapshot['current_field_trace'],current_target_trace=priors['current_target_trace'],
        nine_temporary_priors={p['reference']:priors['priors'][p['reference']]for p in approved_targets if p['kind']==11},
        selector_source_projection=selector,strict_saved_row_scope=rowproof,actual_array_proof=snapshot['actual_array_proof'],
        complete_selected_graph=True,ThereAreAdjustments14873_recomputed=False,
        native_record_inventory_verified=False,owned_labels_are_native_UUIDs=False,BINT_to_INT_row_identity_verified=False,
        TPS_output_conversion_executed=False,comparison_only=True,writeback_allowed=False,source_complete_calculation=False,
        original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)
