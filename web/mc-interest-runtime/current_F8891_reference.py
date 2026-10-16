"""Actual F8891 current scalar fields/ValueMappings -> bounded Canadian outputs."""
import hashlib
from current_string_input_reference import current_string_input
from current_dollars_input_reference import StoredDollars,current_dollars_input
from strict_actual_array_interest_reference import _raw_header_ids
from finite_F8891_reference import CanadianInterest
from interop.derived_form.value_hash_wire_reference import find_value
from interop.form_core.hash_structure_reference import validate_document_hashes


def project_Canadian_interest(request,*,binary_loader,approved_profile,program,expected_program_sha256):
    if type(request)is not dict or request.get('source',{}).get('profile',{}).get('format')!='tax-reborn-binary-entity-profile-v5':raise ValueError('Actual-v5 current source required')
    if type(approved_profile)is not dict or set(approved_profile)!={'identity','fields'}or type(approved_profile['fields'])is not list or len(approved_profile['fields'])!=7:raise ValueError('Seven externally authenticated Canadian current field plans required')
    plans=approved_profile['fields'];doc,buffers,bound,registry,selected,wire=binary_loader(request['source']);digest=hashlib.sha256(wire).hexdigest()
    if digest!=request.get('expected_source_sha256')or getattr(bound,'document',None)is not doc:raise ValueError('Same source/current binding snapshot required')
    hr=validate_document_hashes(doc);index=request.get('source_formset_index')
    if type(index)is not int or not 0<=index<len(doc.formsets)or request.get('need_native_row_uuid',False)is not False:raise ValueError('Existing source FormSet and owned comparison identity required')
    fs=doc.formsets[index];fsid=fs.header.identifier.decode('ascii').rstrip(' ')
    def walk(f,p):
        yield p,f
        for i,c in enumerate(f.children):yield from walk(c,p+(i,))
    matches=[(p,f)for i,f in enumerate(fs.forms)for p,f in walk(f,(index,i))if f.header.identifier.ljust(32,b' ')==b'F8891'.ljust(32,b' ')]
    if len(matches)!=1:raise ValueError('One existing source F8891 required; a missing form is not native blank')
    path,form=matches[0];raw,parent=_raw_header_ids(form)
    if len(path)!=2 or raw.ljust(32,b' ')!=b'F8891'.ljust(32,b' ')or parent is not None or form.header.word7c!=1:raise ValueError('Exact existing F8891 rootcopy1 required; U32file_copy is separate')
    identity=selected.get((fsid,'F8891'))
    if tuple(identity or())!=tuple(approved_profile['identity']):raise ValueError('Actual current F8891 template differs from reviewed original')
    key=(fs.header.identifier,form.header.identifier)
    if bound.context.form_factories.get(key)!='value_form'or bound.context.table_factories.get(key)!='value_table':raise ValueError('Explicit caller ValueForm/ValueTable boundary required')
    template=registry.resolve(fsid,'F8891',identity);values={};selector={1639:[],1653:[]};trace=[]
    for p in plans:
        if set(p)!={'reference','field_id','ordinal','kind','format','template_attributes','selector_literal'}or p['format']!=0 or p['kind']not in(3,7,12):raise ValueError('Exact Canadian field plan/type protocol required')
        fields=[f for f in template.fields if f.field_id==p['field_id']]
        if len(fields)!=1 or tuple(getattr(fields[0],k)for k in('ordinal','kind','format','attributes'))!=tuple(p[k]for k in('ordinal','kind','format','template_attributes')):raise ValueError('Current Canadian field metadata differs from source witness')
        fid=p['field_id'].encode().ljust(32,b' ');entries=[e for e in form.derived_tail.field_map.entries if e.identifier==fid]
        if len(entries)>1:raise ValueError('Ambiguous Canadian source full-ID D2 field')
        source=entries[0].source_field_index if entries else None;node=find_value(form.hash_state,source,0)if source is not None else None;bs=[b for b in bound.bindings.get(path,())if b.field_id==fid or b.current_field_index==p['ordinal']];attrs=0;value=None
        if node is not None:
            attrs=node.specific_attributes
            if len(bs)!=1 or(bs[0].source_field_index,bs[0].current_field_index,bs[0].element_index,bs[0].source_kind,bs[0].source_format,bs[0].fv_attributes)!=(source,p['ordinal'],0,p['kind'],0,attrs)or(node.kind_byte,node.flag10)!=(p['kind'],0):raise ValueError('Exact current/source Canadian scalar hash binding required')
            if bs[0].native_action not in('preserve','requires_additional_scalar_codec','requires_string_or_identity_context')and not(bs[0].native_action=='drop_empty_storage'and not attrs&1):raise ValueError('Unclosed Canadian current conversion')
            if attrs not in(0,1,2,3,8,9,10,11):raise ValueError('Unknown Canadian current attributes')
            if p['kind']==7:value=current_string_input(node,table=form.string_table,table_id=form.table_id)
            elif p['kind']==12:value=current_dollars_input(StoredDollars(node.kind_byte,node.raw,attrs,node.header,node.flag10,node.flag11,node.exponent_byte))
            elif attrs&1:
                if node.header or node.flag10 or node.flag11 or node.raw not in(0,1):raise ValueError('Canonical used current Canadian checkbox required')
                value=bool(node.raw)
        elif bs:raise ValueError('Current binding points to missing Canadian source value')
        ref=p['reference'];literal=p['selector_literal']
        if ref in selector:
            allowed=('true','false')if ref==1639 else('Beneficiary','Annuitant')
            if p['kind']!=3 or literal not in allowed:raise ValueError('Exact original Canadian checkbox ValueMapping required')
            if value is True:selector[ref].append(literal)
        else:
            if literal is not None or ref in values:raise ValueError('Unknown ordinary Canadian field mapping')
            values[ref]=value
        trace.append(dict(reference=ref,field_id=p['field_id'],source_ordinal=source,current_ordinal=p['ordinal'],document_path=list(path),element_index=0,
            source_node_exists=node is not None,present=bool(attrs&1),FV_attributes=attrs,raw64=None if node is None else str(node.raw),selector_literal=literal,selected_literal=value is True if literal else None,
            value_decimal=None if value is None or type(value)in(bytes,bool)else format(value,'f'),value_hex=value.hex()if type(value)is bytes else None,value_boolean=value if type(value)is bool else None))
    if set(values)!={1633,1642,1652}or any(len(x)>1 for x in selector.values()):raise ValueError('Complete unique ordinary and checkbox current supply required')
    if len(selector[1653])!=1:raise ValueError('A source-selected Canadian plan status is required; no default status is inferred')
    if type(values[1652])is not bool:raise ValueError('Explicit present source spouse checkbox required')
    values[1639]=None if not selector[1639]else selector[1639][0]=='true';values[1653]=selector[1653][0].encode('ascii');label='owned-F8891-document:'+':'.join(map(str,path));facts={r:{label:v}for r,v in values.items()}
    engine=CanadianInterest(program,expected_sha256=expected_program_sha256,inputs=facts);roots=engine.run()
    return dict(source_sha256=digest,roots=roots,current_field_trace=trace,evaluated_references=engine.trace,blank_applicability_invariant_proofs=engine.invariants,identity_rounding_trace=engine.rounding,hash_structure_validation=hr,
        fresh11797_recomputed_from_actual_status_and_defer=True,fresh_form_complete_values=engine.cache.get(11797),stored_ENDFORM_not_used_as_fresh=True,current_typed_inputs_from_source=True,
        MFJ12204_supplied=False,MFJ12204_recomputed=False,whole318_cone_executed=False,spouse_nonblank_requires_unclosed_MFJ_and_refuses=True,full14724_executed=False,
        document_file_copy=form.header.file_copy,runtime_copy_number=form.header.word7c,native_record_inventory_verified=False,native_qualified_UUID_mapping_executed=False,native_autoiteration_executed=False,
        owned_labels_are_native_UUIDs=False,comparison_only=True,writeback_allowed=False,original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)
