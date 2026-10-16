"""Saved current FINFOWKS.PR1040NR and FSCHB.L1C source projections.

Only an existing Used canonical0/1 integer can supply the Boolean. All physical
saved L1C rows are read through full-ID D2 bindings; symbolic labels identify
saved coordinates, never native RecordUUIDs. Native post-Load/default/record
inventory completeness remains unverified and is exposed in the result.
"""
from decimal import Decimal
from current_interest_tail_reference import read_tail_priors,compare_tail
from numeric_current_input_reference import StoredCents,current_numeric_input
from interop.derived_form.value_hash_wire_reference import find_value
from strict_actual_array_interest_reference import _raw_header_ids


def read_current_controls(request,*,binary_loader,approved_profile,approved_targets,approved_controls):
    if type(approved_controls)is not dict or set(approved_controls)!={'information_identity','fields'}:
        raise ValueError('External trusted exact current control profile required')
    fields=approved_controls['fields']
    if type(fields)is not list or len(fields)!=2 or{p.get('reference')for p in fields}!={4263,9801}:
        raise ValueError('Both complete source current control fields required')
    loaded=binary_loader(request['source']);doc,buffers,bound,registry,selected,wire=loaded
    def same_loader(source):
        if source!=request['source']:raise ValueError('Source changed within current control read')
        return loaded
    snapshot=read_tail_priors(request,binary_loader=same_loader,approved_profile=approved_profile,approved_targets=approved_targets)
    summary_path=tuple(request['summary_path']);fs=doc.formsets[summary_path[0]];fsid=fs.header.identifier.decode().rstrip(' ')
    summary=fs.forms[summary_path[1]];matches=[(i,f)for i,f in enumerate(fs.forms)if f.header.identifier.ljust(32,b' ')==b'FINFOWKS'.ljust(32,b' ')]
    if len(matches)!=1:raise ValueError('One existing same-FormSet FINFOWKS root is required; absence cannot mean false')
    index,info=matches[0];info_path=(summary_path[0],index);rid=selected.get((fsid,'FINFOWKS'))
    if rid is None or tuple(rid)!=tuple(approved_controls['information_identity']):raise ValueError('Exact approved FINFOWKS template identity required')
    raw_id,parent=_raw_header_ids(info)
    if raw_id.ljust(32,b' ')!=b'FINFOWKS'.ljust(32,b' ')or parent is not None or info.header.word7c!=0:
        raise ValueError('Existing exact FINFOWKS copy0 root required; U32 file_copy is separate')
    key=(fs.header.identifier,info.header.identifier)
    if bound.context.form_factories.get(key)!='value_form'or bound.context.table_factories.get(key)!='value_table':
        raise ValueError('Explicit caller ValueForm/ValueTable boundary required')
    facts={};trace=[]
    for plan in fields:
        if set(plan)!={'reference','form_id','field_id','ordinal','kind','format','template_attributes'}:
            raise ValueError('Exact approved source field metadata required')
        ref=plan['reference'];form,path=(info,info_path)if ref==9801 else(summary,summary_path)
        expected=('FINFOWKS','PR1040NR',612,10,0,0)if ref==9801 else('FSCHB','L1C',28,11,0,3652)
        if tuple(plan[k]for k in('form_id','field_id','ordinal','kind','format','template_attributes'))!=expected:raise ValueError('Exact source-reviewed current control identity required')
        template=registry.resolve(fsid,plan['form_id'],selected[fsid,plan['form_id']]);current=[f for f in template.fields if f.field_id==plan['field_id']]
        if len(current)!=1 or tuple(getattr(current[0],k)for k in('ordinal','kind','format','attributes'))!=tuple(plan[k]for k in('ordinal','kind','format','template_attributes')):
            raise ValueError('Control current metadata differs from approved bytes')
        fid=plan['field_id'].encode().ljust(32,b' ');entries=[e for e in form.derived_tail.field_map.entries if e.identifier==fid]
        if len(entries)>1:raise ValueError('Ambiguous source full-ID D2 entry')
        source=entries[0].source_field_index if entries else None
        bs=[b for b in bound.bindings.get(path,())if b.field_id==fid or b.current_field_index==plan['ordinal']]
        values={}
        for b in bs:
            if b.field_id!=fid or b.current_field_index!=plan['ordinal']or b.source_field_index!=source:raise ValueError('Control full-ID/current coordinate collision')
            node=find_value(form.hash_state,source,b.element_index)
            if node is None or(node.kind_byte,node.flag10,b.source_kind,b.source_format,b.fv_attributes)!=(plan['kind'],0,plan['kind'],0,node.specific_attributes):
                raise ValueError('Control source/current kind, format or attributes mismatch')
            if b.native_action not in('preserve','requires_additional_scalar_codec','drop_empty_storage'):raise ValueError('Unclosed control conversion refused')
            if node.specific_attributes not in(0,1,2,3,8,9,10,11):raise ValueError('Unknown source current control attributes')
            present=bool(node.specific_attributes&1)
            row=dict(reference=ref,document_path=list(path),field_id=plan['field_id'],source_ordinal=source,current_ordinal=plan['ordinal'],
                element_index=b.element_index,FV_attributes=node.specific_attributes,present=present,raw64=str(node.raw),
                packed_exponent=node.exponent_byte,value_header=node.header,format_flag10=node.flag10,flag11=node.flag11)
            if ref==9801:
                if b.element_index!=0:raise ValueError('Current PR1040NR scalar coordinate required')
                if present and(node.raw not in(0,1)or node.header or node.flag11):raise ValueError('Finite current kind10 canonical0/1 normal renderer profile required')
                value=bool(node.raw)if present else None
                row.update(rendered_integer_text=str(node.raw)if present else None,case10_MEF_boolean_text=('true'if node.raw else'false')if present else None)
            else:
                if not 1<=b.element_index<=65520:raise ValueError('Existing ordinary ADJUST row coordinates required')
                value=current_numeric_input(StoredCents(node.kind_byte,node.raw,node.specific_attributes,node.header,node.flag10,node.flag11,node.exponent_byte))
                values['owned-saved-ADJUST-row:'+str(b.element_index)]=value
            row['value']=None if value is None else value if type(value)is bool else format(value,'f');trace.append(row)
        if ref==9801:
            if len(bs)!=1 or not trace[-1]['present']:raise ValueError('PR1040NR must be an actual existing Used source value; missing/Unused is not false')
            facts[ref]=trace[-1]['value']
        else:
            if len(values)>64:raise ValueError('At most64 explicit saved ADJUST amount rows supported')
            key=(fs.header.identifier,summary.header.identifier);arrays=[a for block in bound.arrays[key]for a in block if a.identifier.ljust(32,b' ')==b'ADJUST'.ljust(32,b' ')]
            if len(arrays)!=1 or(arrays[0].first_field,arrays[0].last_field,arrays[0].element_limit,arrays[0].flags)!=(27,28,65520,49):raise ValueError('Exact actual ADJUST27..28 array required')
            tables=[t for t in summary.tables if t.identifier.ljust(32,b' ')==b'ADJUST'.ljust(32,b' ')]
            if len(tables)>1:raise ValueError('Ambiguous saved ADJUST header')
            if tables:
                by_id={e.identifier:e.source_field_index for e in summary.derived_tail.field_map.entries}
                if(tables[0].word28,tables[0].word2a)!=(by_id.get(b'L1CD'.ljust(32,b' ')),source):raise ValueError('Saved ADJUST endpoints must bind through complete D2 IDs')
            facts[ref]=values
    return dict(source_sha256=snapshot['source_sha256'],projected_inputs=facts,current_control_trace=trace,
        PR1040NR_source_used_verified=True,information_document_file_copy=info.header.file_copy,information_runtime_copy_number=info.header.word7c,
        PR1040NR_CS113_producer_recomputed=False,native_generic_mapping_constraints_executed=False,
        actual_all_stored_L1C_rows_examined=True,saved_coordinate_labels_are_native_UUIDs=False,
        native_complete_MultiCopy_4263_inventory_verified=False,native_post_Load_defaults_verified=False,
        comparison_only=True,writeback_allowed=False,source_complete_calculation=False)


def compare_with_current_controls(request,*,binary_loader,approved_profile,approved_targets,approved_controls,program,expected_program_sha256,remaining_upstream_results):
    if type(remaining_upstream_results)is not dict or set(remaining_upstream_results)!={14725,14873,15167}:
        raise ValueError('Three remaining upstream cut results must be explicit; no default supplies')
    controls=read_current_controls(request,binary_loader=binary_loader,approved_profile=approved_profile,approved_targets=approved_targets,approved_controls=approved_controls)
    inputs={**remaining_upstream_results,**controls['projected_inputs']}
    result=compare_tail(request,binary_loader=binary_loader,approved_profile=approved_profile,approved_targets=approved_targets,
        program=program,expected_program_sha256=expected_program_sha256,upstream_results=inputs)
    if result['source_sha256']!=controls['source_sha256']:raise ValueError('Source changed between controls and tail')
    return dict(result,current_control_source_projection=controls,remaining_explicit_upstream_cut_points=[14725,14873,15167],
        native_complete_MultiCopy_4263_inventory_verified=False,source_complete_calculation=False)
