"""Actual-v5 existing K1 current fields -> three bounded interest source families.

These maps use owned document-coordinate labels. They are not native UUIDs or
proof of the native qualified mapping inventory. Missing forms are refused.
"""
import hashlib
from current_dollars_input_reference import StoredDollars,current_dollars_input,render_current_dollars
from finite_K1_interest_families_reference import K1InterestFamilies
from interop.derived_form.value_hash_wire_reference import find_value
from strict_actual_array_interest_reference import _raw_header_ids


def project_K1_interest_families(request,*,binary_loader,approved_profile,program,expected_program_sha256):
    if type(request)is not dict or request.get('source',{}).get('profile',{}).get('format')!='tax-reborn-binary-entity-profile-v5':raise ValueError('Actual v5 current source required')
    if type(approved_profile)is not dict or set(approved_profile)!={'forms','fields'}or set(approved_profile['forms'])!={'FK1EW','FK1PW','FK1SW'}:raise ValueError('External complete three-form authority required')
    plans=approved_profile['fields']
    if type(plans)is not list or{p.get('reference')for p in plans}!={5227,5345,5568,6317,6318,6787,6802,7509}or len(plans)!=8:raise ValueError('All eight exact source field plans required')
    loaded=binary_loader(request['source']);doc,buffers,bound,registry,selected,wire=loaded;digest=hashlib.sha256(wire).hexdigest()
    if digest!=request.get('expected_source_sha256')or getattr(bound,'document',None)is not doc:raise ValueError('One source digest/current binding snapshot required')
    index=request.get('source_formset_index')
    if type(index)is not int or not 0<=index<len(doc.formsets):raise ValueError('Existing source FormSet index required')
    fs=doc.formsets[index];fsid=fs.header.identifier.decode('ascii').rstrip(' ');located={}
    def walk(form,path):
        yield path,form
        for i,child in enumerate(form.children):yield from walk(child,path+(i,))
    all_forms=[item for i,form in enumerate(fs.forms)for item in walk(form,(index,i))]
    for form_id,identity in approved_profile['forms'].items():
        matches=[(path,form)for path,form in all_forms if form.header.identifier.ljust(32,b' ')==form_id.encode().ljust(32,b' ')]
        if len(matches)!=1:raise ValueError('Exactly one existing source '+form_id+' required; missing never means an empty native family')
        path,form=matches[0];raw,parent=_raw_header_ids(form)
        if len(path)!=2 or raw.ljust(32,b' ')!=form_id.encode().ljust(32,b' ')or parent is not None or form.header.word7c!=1:raise ValueError('Exact existing root K1 runtime copy1 profile required; file_copy is separate')
        if tuple(selected.get((fsid,form_id),()))!=tuple(identity):raise ValueError('Current template carrier/resource differs from external authority')
        key=(fs.header.identifier,form.header.identifier)
        if bound.context.form_factories.get(key)!='value_form'or bound.context.table_factories.get(key)!='value_table':raise ValueError('Explicit caller ValueForm/ValueTable factory boundary required')
        located[form_id]=(path,form,registry.resolve(fsid,form_id,identity))
    inputs={};trace=[]
    for plan in plans:
        if set(plan)!={'reference','form_id','field_id','ordinal','kind','format','template_attributes'}or(plan['kind'],plan['format'])!=(12,0):raise ValueError('Exact reviewed kind12/format0 field metadata required')
        path,form,template=located[plan['form_id']];fields=[f for f in template.fields if f.field_id==plan['field_id']]
        if len(fields)!=1 or tuple(getattr(fields[0],k)for k in('ordinal','kind','format','attributes'))!=tuple(plan[k]for k in('ordinal','kind','format','template_attributes')):raise ValueError('Reviewed/current K1 field metadata differs')
        fid=plan['field_id'].encode('ascii').ljust(32,b' ');entries=[e for e in form.derived_tail.field_map.entries if e.identifier==fid]
        if len(entries)>1:raise ValueError('Ambiguous full source field ID')
        ordinal=entries[0].source_field_index if entries else None;node=find_value(form.hash_state,ordinal,0)if ordinal is not None else None
        bindings=[b for b in bound.bindings.get(path,())if b.field_id==fid or b.current_field_index==plan['ordinal']]
        state=None
        if node is not None:
            if len(bindings)!=1:raise ValueError('Exactly one current K1 scalar binding required')
            b=bindings[0]
            if(b.field_id,b.source_field_index,b.current_field_index,b.element_index,b.source_kind,b.source_format,b.fv_attributes)!=(fid,ordinal,plan['ordinal'],0,12,0,node.specific_attributes)or(node.kind_byte,node.flag10)!=(12,0):raise ValueError('K1 source/current full-ID/index/kind/format/attrs mismatch')
            if b.native_action not in('preserve','requires_additional_scalar_codec','drop_empty_storage'):raise ValueError('Unclosed K1 current conversion refused')
            state=StoredDollars(node.kind_byte,node.raw,node.specific_attributes,node.header,node.flag10,node.flag11,node.exponent_byte)
        elif bindings:raise ValueError('K1 binding points to missing source scalar')
        value=current_dollars_input(state);label='owned-'+plan['form_id']+'-document:'+':'.join(map(str,path));inputs[plan['reference']]={label:value}
        trace.append(dict(reference=plan['reference'],form_id=plan['form_id'],field_id=plan['field_id'],document_path=list(path),source_ordinal=ordinal,current_ordinal=plan['ordinal'],
            document_file_copy=form.header.file_copy,runtime_copy_number=form.header.word7c,source_node_exists=node is not None,present=state is not None and bool(state.attributes&1),
            raw64=None if node is None else str(node.raw),packed_exponent=None if node is None else node.exponent_byte,FV_attributes=0 if node is None else node.specific_attributes,
            rendered_current_text=render_current_dollars(state),supplied_numeric=None if value is None else format(value,'f')))
    engine=K1InterestFamilies(program,expected_sha256=expected_program_sha256,inputs=inputs,prior_values={});roots=engine.run()
    return dict(source_sha256=digest,program_content_sha256=expected_program_sha256,roots=roots,current_input_trace=trace,evaluated_references=engine.trace,
        actual_current_fields_projected=True,three_source_families_recomputed=True,source_complete14725=False,other_source_families_assumed_empty=False,
        native_qualified_uuid_mapping_executed=False,owned_labels_are_native_UUIDs=False,native_record_inventory_verified=False,native_GetValueFor_executed=False,
        caller_declared_ValueForm_factory=True,native_post_Load_defaults_executed=False,comparison_only=True,writeback_allowed=False,
        original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)
