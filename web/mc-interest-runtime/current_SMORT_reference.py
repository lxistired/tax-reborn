"""Actual-v5 FSCHBTIN current row1/F6252 scalars -> original POR74 comparison.

TEMPS is read as original INPUT10770. It is not recomputed or called fresh.
Missing forms/tables are not native absence. Labels are owned comparison keys.
"""
import hashlib
from actual_array_blocks_reference import verify_actual_array_blocks
from current_dollars_input_reference import StoredDollars,current_dollars_input
from numeric_current_input_reference import StoredCents,current_numeric_input
from current_string_input_reference import current_string_input
from current_ssn_string_reference import current_ssn_input
from strict_actual_array_interest_reference import _raw_header_ids
from finite_SMORT_reference import SellerInterest
from interop.derived_form.value_hash_wire_reference import find_value
from interop.form_core.hash_structure_reference import validate_document_hashes


def project_seller_interest(request,*,binary_loader,approved_profile,program,expected_program_sha256):
    if type(request)is not dict or request.get('source',{}).get('profile',{}).get('format')!='tax-reborn-binary-entity-profile-v5':raise ValueError('Actual-v5 current source required')
    if type(approved_profile)is not dict or set(approved_profile)!={'identities','fields','array_blocks'}:raise ValueError('External complete seller-financed source authority required')
    plans=approved_profile['fields']
    if type(plans)is not list or len(plans)!=19 or len({p.get('reference')for p in plans})!=19 or set(approved_profile['identities'])!={'FSCHBTIN','F6252'}:raise ValueError('All nineteen current source field plans required')
    doc,buffers,bound,registry,selected,wire=binary_loader(request['source']);digest=hashlib.sha256(wire).hexdigest()
    if digest!=request.get('expected_source_sha256')or getattr(bound,'document',None)is not doc:raise ValueError('Same source/current binding snapshot required')
    hr=validate_document_hashes(doc);index=request.get('source_formset_index')
    if type(index)is not int or not 0<=index<len(doc.formsets)or request.get('row_number')!=1 or request.get('need_native_row_uuid',False)is not False:raise ValueError('Existing source FormSet and owned row1 required')
    fs=doc.formsets[index];fsid=fs.header.identifier.decode('ascii').rstrip(' ');forms={}
    def walk(f,path):
        yield path,f
        for i,c in enumerate(f.children):yield from walk(c,path+(i,))
    for formid in('FSCHBTIN','F6252'):
        matches=[(p,f)for i,f in enumerate(fs.forms)for p,f in walk(f,(index,i))if f.header.identifier.ljust(32,b' ')==formid.encode().ljust(32,b' ')]
        if len(matches)!=1:raise ValueError('Exactly one existing '+formid+' required; missing is not a blank native family')
        path,form=matches[0];raw,parent=_raw_header_ids(form)
        if len(path)!=2 or raw.ljust(32,b' ')!=formid.encode().ljust(32,b' ')or parent is not None or form.header.word7c!=(0 if formid=='FSCHBTIN'else 1):raise ValueError('Exact current root/copy identity required; saved U32 file_copy is separate')
        identity=selected.get((fsid,formid))
        if tuple(identity or())!=tuple(approved_profile['identities'][formid]):raise ValueError('Selected current template differs from reviewed original identity')
        key=(fs.header.identifier,form.header.identifier)
        if bound.context.form_factories.get(key)!='value_form'or bound.context.table_factories.get(key)!='value_table':raise ValueError('Explicit caller ValueForm/ValueTable class boundary required')
        forms[formid]=(path,form,registry.resolve(fsid,formid,identity))
    array_proof=verify_actual_array_blocks(bound,registry,formset_id=fsid,form_id='FSCHBTIN',approved_blocks=approved_profile['array_blocks']);arrays=[a for b in array_proof['blocks']for a in b['records']if a['identifier']=='ADDR']
    if arrays!=[dict(identifier='ADDR',first_field=5,last_field=13,element_limit=65520,flags=49,byte27=0)]:raise ValueError('Exact actual ADDR5..13 array descriptor required')
    path,form,_=forms['FSCHBTIN'];es={e.identifier:e.source_field_index for e in form.derived_tail.field_map.entries};first=es.get(b'NAME1'.ljust(32,b' '));last=es.get(b'AMT'.ljust(32,b' '));tables=[t for t in form.tables if t.identifier.ljust(32,b' ')==b'ADDR'.ljust(32,b' ')]
    if first is None or last is None or first>last or len(tables)!=1 or(tables[0].word28,tables[0].word2a,tables[0].last_used_record_index)!=(first,last,1):raise ValueError('Existing saved ADDR row1/header and exact source D2 endpoints required')
    for b in bound.bindings.get(path,()):
        if 5<=b.current_field_index<=13 or first<=b.source_field_index<=last:
            if not 5<=b.current_field_index<=13 or b.element_index!=1:raise ValueError('Any additional ADDR coordinate, even Unused or zero, requires native inventory')
    facts={};trace=[]
    for p in plans:
        if set(p)!={'reference','form_id','field_id','ordinal','kind','format','template_attributes','element_index'}or p['form_id']not in forms:raise ValueError('Exact source field plan protocol required')
        path,form,template=forms[p['form_id']];fields=[f for f in template.fields if f.field_id==p['field_id']]
        if len(fields)!=1 or tuple(getattr(fields[0],k)for k in('ordinal','kind','format','attributes'))!=tuple(p[k]for k in('ordinal','kind','format','template_attributes')):raise ValueError('Source current metadata differs from reviewed original field')
        expected_element=1 if p['form_id']=='FSCHBTIN'and p['reference']!=10770 else 0
        if p['element_index']!=expected_element:raise ValueError('Original scalar/table coordinate differs')
        fid=p['field_id'].encode().ljust(32,b' ');entries=[e for e in form.derived_tail.field_map.entries if e.identifier==fid]
        if len(entries)>1:raise ValueError('Ambiguous source full-ID D2 field')
        source=entries[0].source_field_index if entries else None;node=find_value(form.hash_state,source,expected_element)if source is not None else None;bs=[b for b in bound.bindings.get(path,())if b.field_id==fid];value=None;attrs=0
        if node is not None:
            if len(bs)!=1:raise ValueError('Unique current source field binding required')
            b=bs[0];attrs=node.specific_attributes
            if(b.source_field_index,b.current_field_index,b.element_index,b.source_kind,b.source_format,b.fv_attributes)!=(source,p['ordinal'],expected_element,p['kind'],p['format'],attrs)or(node.kind_byte,node.flag10)!=(p['kind'],p['format']):raise ValueError('Current/source full-ID kind/format/hash binding differs')
            if b.native_action not in('preserve','requires_additional_scalar_codec','requires_string_or_identity_context','drop_empty_storage'):raise ValueError('Unclosed native source conversion')
            if attrs not in(0,1,2,3,8,9,10,11):raise ValueError('Unknown current source attributes')
            if(p['kind'],p['format'])in((7,3),(21,1)):
                if attrs&1:raise ValueError('Used state/ZIP native formatter remains unsupported')
            elif p['format']:raise ValueError('Unsupported current source formatter')
            elif p['kind']==11:value=current_numeric_input(StoredCents(node.kind_byte,node.raw,attrs,node.header,node.flag10,node.flag11,node.exponent_byte))
            elif p['kind']==12:value=current_dollars_input(StoredDollars(node.kind_byte,node.raw,attrs,node.header,node.flag10,node.flag11,node.exponent_byte))
            elif p['kind']==8:value=current_ssn_input(node,table=form.string_table,table_id=form.table_id)
            elif p['kind']==7:value=current_string_input(node,table=form.string_table,table_id=form.table_id)
            else:raise ValueError('Unsupported current source kind')
        elif bs:raise ValueError('Binding without source hash value')
        label='owned-seller-document:'+':'.join(map(str,path))+(':ADDRrow1'if expected_element else':scalar')
        facts[p['reference']]={label:value};trace.append(dict(reference=p['reference'],form_id=p['form_id'],field_id=p['field_id'],document_path=list(path),source_ordinal=source,current_ordinal=p['ordinal'],element_index=expected_element,
            source_node_exists=node is not None,present=bool(attrs&1),FV_attributes=attrs,raw64=None if node is None else str(node.raw),kind=p['kind'],format=p['format'],value_hex=value.hex()if type(value)is bytes else None,value_decimal=None if value is None or type(value)is bytes else format(value,'f')))
    engine=SellerInterest(program,expected_sha256=expected_program_sha256,inputs=facts,prior_values={});roots=engine.run()
    return dict(source_sha256=digest,roots=roots,current_source_trace=trace,evaluated_references=engine.trace,actual_array_proof=array_proof,hash_structure_validation=hr,
        original_POR14631_recomputed=True,source10770_is_existing_current_INPUT=True,source10770_fresh_reaggregation=False,single_nonempty_concatenate_only=True,unsupported_Used_state_or_ZIP_refused=True,
        full14724_executed=False,other_scalar_branches_assumed_empty=False,native_record_inventory_verified=False,native_qualified_UUID_mapping_executed=False,native_autoiteration_executed=False,owned_labels_are_native_UUIDs=False,
        comparison_only=True,writeback_allowed=False,original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)
