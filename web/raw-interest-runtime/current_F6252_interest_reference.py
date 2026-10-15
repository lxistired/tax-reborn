"""Actual F6252 scalar payment group -> original20-node taxable-source filter.

PaymentRecivedWks is not a schema multiCopy group. Its selected TPS fields are
scalars on F6252[uuid1]; the unrelated PAYTABLE array is not this input path.
Only an existing single root source copy is projected. No native UUID mapping
or post-Load inventory is inferred from this saved document.
"""
import hashlib
from current_dollars_input_reference import StoredDollars,current_dollars_input,render_current_dollars
from current_string_input_reference import current_string_input
from current_ssn_string_reference import current_ssn_input
from finite_OID_taxable_amount_reference import OIDTaxableAmount
from strict_actual_array_interest_reference import _raw_header_ids
from interop.derived_form.value_hash_wire_reference import find_value
from interop.form_core.hash_structure_reference import validate_document_hashes


def project_F6252_interest(request,*,binary_loader,approved_profile,program,expected_program_sha256):
    if type(request)is not dict or request.get('source',{}).get('profile',{}).get('format')!='tax-reborn-binary-entity-profile-v5':raise ValueError('Actual-v5 current source required')
    if type(approved_profile)is not dict or set(approved_profile)!={'identity','fields'}:raise ValueError('Complete externally authenticated F6252 authority required')
    plans=approved_profile['fields']
    if type(plans)is not list or len(plans)!=7 or{p.get('reference')for p in plans}!={8360,8362,8363,8364,8366,8368,8371}:raise ValueError('All seven actual scalar source field plans required')
    doc,buffers,bound,registry,selected,wire=binary_loader(request['source']);digest=hashlib.sha256(wire).hexdigest()
    if digest!=request.get('expected_source_sha256')or getattr(bound,'document',None)is not doc:raise ValueError('Same source/current binding digest required')
    receipt=validate_document_hashes(doc);index=request.get('source_formset_index')
    if type(index)is not int or not 0<=index<len(doc.formsets)or request.get('need_native_row_uuid',False)is not False:raise ValueError('Existing source FormSet and owned comparison labels required')
    fs=doc.formsets[index];fsid=fs.header.identifier.decode('ascii').rstrip(' ')
    def walk(f,path):
        yield path,f
        for i,c in enumerate(f.children):yield from walk(c,path+(i,))
    matches=[(path,f)for i,f in enumerate(fs.forms)for path,f in walk(f,(index,i))if f.header.identifier.ljust(32,b' ')==b'F6252'.ljust(32,b' ')]
    if len(matches)!=1:raise ValueError('Exactly one existing F6252 required; missing form is not an empty native family')
    path,form=matches[0];raw,parent=_raw_header_ids(form)
    if len(path)!=2 or raw.ljust(32,b' ')!=b'F6252'.ljust(32,b' ')or parent is not None or form.header.word7c!=1:raise ValueError('Exact existing root F6252 runtime copy1 profile required; file_copy is separate')
    identity=selected.get((fsid,'F6252'))
    if identity is None or tuple(identity)!=tuple(approved_profile['identity']):raise ValueError('Current F6252 template differs from external source identity')
    key=(fs.header.identifier,form.header.identifier)
    if bound.context.form_factories.get(key)!='value_form'or bound.context.table_factories.get(key)!='value_table':raise ValueError('Explicit caller ValueForm/ValueTable class boundary required')
    template=registry.resolve(fsid,'F6252',identity);inputs={};trace=[];label='owned-F6252-document:'+':'.join(map(str,path))
    for p in plans:
        if set(p)!={'reference','field_id','ordinal','kind','format','template_attributes'}or p['format']!=0 or p['kind']not in(7,8,12):raise ValueError('Exact source-reviewed scalar metadata required')
        fields=[f for f in template.fields if f.field_id==p['field_id']]
        if len(fields)!=1 or tuple(getattr(fields[0],k)for k in('ordinal','kind','format','attributes'))!=tuple(p[k]for k in('ordinal','kind','format','template_attributes')):raise ValueError('Actual/current field metadata differs from reviewed bytes')
        fid=p['field_id'].encode().ljust(32,b' ');entries=[e for e in form.derived_tail.field_map.entries if e.identifier==fid]
        if len(entries)>1:raise ValueError('Ambiguous complete source field ID')
        source=entries[0].source_field_index if entries else None;node=find_value(form.hash_state,source,0)if source is not None else None;bs=[b for b in bound.bindings.get(path,())if b.field_id==fid or b.current_field_index==p['ordinal']]
        if node is not None:
            if len(bs)!=1 or(bs[0].field_id,bs[0].source_field_index,bs[0].current_field_index,bs[0].element_index,bs[0].source_kind,bs[0].source_format,bs[0].fv_attributes)!=(fid,source,p['ordinal'],0,p['kind'],0,node.specific_attributes)or(node.kind_byte,node.flag10)!=(p['kind'],0):raise ValueError('Exact current/source scalar D2/hash binding required; PAYTABLE is not this path')
            if bs[0].native_action not in('preserve','requires_additional_scalar_codec','requires_string_or_identity_context','drop_empty_storage'):raise ValueError('Unknown current conversion refused')
        elif bs:raise ValueError('Current binding points to missing source value')
        if p['kind']==12:
            state=None if node is None else StoredDollars(node.kind_byte,node.raw,node.specific_attributes,node.header,node.flag10,node.flag11,node.exponent_byte);value=current_dollars_input(state);text=render_current_dollars(state)
        elif p['kind']==8:value=current_ssn_input(node,table=form.string_table,table_id=form.table_id);text=None
        else:value=current_string_input(node,table=form.string_table,table_id=form.table_id);text=None
        inputs[p['reference']]={label:value};trace.append(dict(reference=p['reference'],field_id=p['field_id'],document_path=list(path),source_ordinal=source,current_ordinal=p['ordinal'],element_index=0,kind=p['kind'],
            source_node_exists=node is not None,present=node is not None and bool(node.specific_attributes&1),FV_attributes=0 if node is None else node.specific_attributes,raw64=None if node is None else str(node.raw),
            rendered_numeric_text=text,supplied_bytes_hex=value.hex()if type(value)is bytes else None,supplied_numeric=None if value is None or type(value)is bytes else format(value,'f')))
    engine=OIDTaxableAmount(program,expected_sha256=expected_program_sha256,inputs=inputs,prior_values={});roots=engine.run()
    return dict(source_sha256=digest,roots=roots,current_input_trace=trace,evaluated_references=engine.trace,hash_structure_validation=receipt,
        document_file_copy=form.header.file_copy,runtime_copy_number=form.header.word7c,
        source_F6252_14557_recomputed=True,PaymentRecivedWks_is_schema_multiCopy=False,selected_TPS_fields_are_scalars=True,source_complete14725=False,
        other_source_families_assumed_empty=False,native_qualified_UUID_mapping_executed=False,native_record_inventory_verified=False,native_GetValueFor_executed=False,
        caller_declared_ValueForm_factory=True,saved_absence_is_not_native_runtime_absence=True,owned_labels_are_native_UUIDs=False,
        comparison_only=True,writeback_allowed=False,original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)
