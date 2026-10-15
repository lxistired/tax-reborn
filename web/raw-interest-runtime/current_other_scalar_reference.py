"""One actual-v5 source -> bank/OID OtherAdjustment -> actual H/UH scalar branch.

This does not treat unknown SellerFinanced/Canadian branches as empty, and does
not emit a complete14724 collection. All numeric/Boolean results originate in
internal authenticated programs and actual current source storage.
"""
import hashlib
from current_bank_adjustment_reference import project_normal_adjustments
from current_OID_snapshot_reference import read_OID_snapshot
from finite_OID_adjustment_reference import OIDAdjustment
from finite_other_scalar_reference import OtherScalar
from numeric_current_input_reference import StoredCents,current_numeric_input
from interop.derived_form.value_hash_wire_reference import find_value


def _read_H_targets(loaded,request,approved_bank_profile,approved_targets):
    if type(approved_targets)is not list or len(approved_targets)!=2 or{p.get('reference')for p in approved_targets}!={14694,14717}:raise ValueError('Exact two externally authenticated H/UH field plans required')
    doc,buffers,bound,registry,selected,wire=loaded;path=tuple(request['summary_path']);fs=doc.formsets[path[0]];form=fs.forms[path[1]];fsid=fs.header.identifier.decode().rstrip(' ')
    if tuple(selected.get((fsid,'FSCHB'),()))!=tuple(approved_bank_profile['summary_identity']):raise ValueError('Exact approved current FSCHB required')
    template=registry.resolve(fsid,'FSCHB',approved_bank_profile['summary_identity']);priors={};trace=[]
    for p in approved_targets:
        if set(p)!={'reference','form_id','field_id','ordinal','kind','format','template_attributes'}or p['form_id']!='FSCHB'or(p['kind'],p['format'],p['template_attributes'])!=(11,0,0):raise ValueError('Exact reviewed H/UH kind11 scalar metadata required')
        fields=[f for f in template.fields if f.field_id==p['field_id']]
        if len(fields)!=1 or tuple(getattr(fields[0],k)for k in('ordinal','kind','format','attributes'))!=tuple(p[k]for k in('ordinal','kind','format','template_attributes')):raise ValueError('H/UH current metadata differs from reviewed bytes')
        fid=p['field_id'].encode().ljust(32,b' ');entries=[e for e in form.derived_tail.field_map.entries if e.identifier==fid]
        if len(entries)>1:raise ValueError('Ambiguous H/UH complete D2 ID')
        source=entries[0].source_field_index if entries else None;node=find_value(form.hash_state,source,0)if source is not None else None;bs=[b for b in bound.bindings.get(path,())if b.field_id==fid or b.current_field_index==p['ordinal']];attrs=0;value=None
        if node is not None:
            if len(bs)!=1:raise ValueError('Stored H/UH scalar needs unique current binding')
            b=bs[0]
            if(b.field_id,b.source_field_index,b.current_field_index,b.element_index,b.source_kind,b.source_format,b.fv_attributes)!=(fid,source,p['ordinal'],0,11,0,node.specific_attributes)or(node.kind_byte,node.flag10)!=(11,0):raise ValueError('H/UH source/current D2 hash binding differs')
            if b.native_action not in('preserve','requires_additional_scalar_codec')and not(b.native_action=='drop_empty_storage'and not node.specific_attributes&1):raise ValueError('Unclosed H/UH native current conversion')
            attrs=node.specific_attributes
            if attrs not in(0,1,2,3,8,9,10,11)or attrs&8:raise ValueError('Exterior H/UH Override protocol remains unclosed')
            value=current_numeric_input(StoredCents(node.kind_byte,node.raw,attrs,node.header,node.flag10,node.flag11,node.exponent_byte))
        elif bs:raise ValueError('H/UH current binding points to missing source value')
        priors[p['reference']]=dict(value=value,computed=bool(attrs&2),overridden=False,itemized=False)
        trace.append(dict(reference=p['reference'],field_id=p['field_id'],document_path=list(path),source_ordinal=source,current_ordinal=p['ordinal'],element_index=0,
            source_storage='D2_absent'if source is None else'hash_node_absent'if node is None else'stored',present=bool(attrs&1),FV_attributes=attrs,raw64=None if node is None else str(node.raw),packed_exponent=None if node is None else node.exponent_byte,value_decimal=None if value is None else format(value,'f')))
    return priors,trace


def project_other_scalar(request,*,binary_loader,approved_bank_profile,approved_entries,approved_bank_targets,approved_OID,approved_H_targets,programs):
    if type(programs)is not dict or set(programs)!={'bank','OID','scalar'}or any(type(p)is not dict or set(p)!={'model','sha256'}for p in programs.values()):raise ValueError('Three external authenticated source programs required')
    loaded=binary_loader(request['source']);digest=hashlib.sha256(loaded[-1]).hexdigest()
    def same_loader(source):
        if source!=request['source']:raise ValueError('Source changed during H/UH comparison')
        return loaded
    bp,op,sp=(programs[k]for k in('bank','OID','scalar'))
    bank=project_normal_adjustments(request,binary_loader=same_loader,approved_profile=approved_bank_profile,approved_entries=approved_entries,approved_targets=approved_bank_targets,program=bp['model'],expected_program_sha256=bp['sha256'])
    oid_source=read_OID_snapshot(request,binary_loader=same_loader,approved_bank_profile=approved_bank_profile,approved_OID=approved_OID)
    oid_engine=OIDAdjustment(op['model'],expected_sha256=op['sha256'],inputs=oid_source['typed_inputs'],prior_values=oid_source['current_assignment_storage']);oid_roots=oid_engine.run()
    if any(d!=digest for d in(bank['source_sha256'],oid_source['source_sha256'])):raise ValueError('Same current source snapshot required')
    if set(bank['roots'])!={14664,14704}or set(oid_roots)!={14692,14715}:raise ValueError('Exact four actually evaluated H/UH producers required')
    priors,trace=_read_H_targets(loaded,request,approved_bank_profile,approved_H_targets)
    engine=OtherScalar(sp['model'],expected_sha256=sp['sha256'],components={**bank['roots'],**oid_roots},prior_values=priors);roots=engine.run()
    return dict(source_sha256=digest,roots=roots,current_H_target_trace=trace,proposed_H_target_writes=engine.assignments,evaluated_scalar_references=engine.trace,
        bank_projection=bank,OID_projection=dict(roots=oid_roots,evaluated_references=oid_engine.trace,current_source_snapshot=oid_source,proposed_graph_assignments=oid_engine.assignments,blank_condition_trace=oid_engine.blank_trace,rounding_trace=oid_engine.rounding),
        original_program_content_sha256={k:p['sha256']for k,p in programs.items()},actual_N_branch_condition_and_amount_recomputed=True,no_manual_Boolean_or_amount_cutpoints=True,
        full14724_executed=False,other_scalar_branches_assumed_empty=False,source_complete14725=False,source_complete_L4_or_R2_calculation=False,
        all_current_facts_share_one_loaded_document=True,stored_absence_is_not_native_runtime_absence=True,native_record_inventory_verified=False,native_qualified_UUID_mapping_executed=False,
        original_assignment_flag_mutations_executed=False,original_scheduler_executed=False,TPS_output_conversion_executed=False,owned_labels_are_native_UUIDs=False,
        comparison_only=True,writeback_allowed=False,original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)
