"""Existing actual source ACINTINC row1 -> current cents ->14581 graph copy.

The record label is owned and does not identify a native UUID. Missing forms or
tables refuse. The observed source row is not proof of native post-Load stock.
"""
import hashlib
from actual_array_blocks_reference import verify_actual_array_blocks
from numeric_current_input_reference import StoredCents,current_numeric_input,render_current_cents
from strict_actual_array_interest_reference import _raw_header_ids
from finite_K1_interest_families_reference import K1InterestFamilies
from interop.derived_form.value_hash_wire_reference import find_value
from interop.form_core.hash_structure_reference import validate_document_hashes


def project_STKBASIS_interest(request,*,binary_loader,approved_profile,program,expected_program_sha256):
    if type(request)is not dict or request.get('source',{}).get('profile',{}).get('format')!='tax-reborn-binary-entity-profile-v5':raise ValueError('Actual-v5 current source required')
    if type(approved_profile)is not dict or set(approved_profile)!={'identity','fields','array_blocks'}:raise ValueError('Complete external source authority required')
    plans=approved_profile['fields']
    if type(plans)is not list or len(plans)!=2 or{p.get('field_id')for p in plans}!={'AIPAYER','AIAMT'}:raise ValueError('Exact two source array endpoint field plans required')
    doc,buffers,bound,registry,selected,wire=binary_loader(request['source']);digest=hashlib.sha256(wire).hexdigest()
    if digest!=request.get('expected_source_sha256')or getattr(bound,'document',None)is not doc:raise ValueError('One source/current binding snapshot required')
    hash_receipt=validate_document_hashes(doc);index=request.get('source_formset_index')
    if type(index)is not int or not 0<=index<len(doc.formsets)or request.get('row_number')!=1 or request.get('need_native_row_uuid',False)is not False:raise ValueError('Existing source FormSet and bounded owned row1 required; native UUID unavailable')
    fs=doc.formsets[index];fsid=fs.header.identifier.decode('ascii').rstrip(' ')
    def walk(form,path):
        yield path,form
        for i,c in enumerate(form.children):yield from walk(c,path+(i,))
    matches=[(path,f)for i,f in enumerate(fs.forms)for path,f in walk(f,(index,i))if f.header.identifier.ljust(32,b' ')==b'STKBASIS'.ljust(32,b' ')]
    if len(matches)!=1:raise ValueError('Exactly one existing STKBASIS required; missing is not a blank native family')
    path,form=matches[0];raw,parent=_raw_header_ids(form)
    if len(path)!=2 or raw.ljust(32,b' ')!=b'STKBASIS'.ljust(32,b' ')or parent is not None or form.header.word7c!=0:raise ValueError('Exact STKBASIS root runtime copy0 profile required; saved U32 file_copy is separate')
    identity=selected.get((fsid,'STKBASIS'))
    if identity is None or tuple(identity)!=tuple(approved_profile['identity']):raise ValueError('Selected current STKBASIS template differs from external identity')
    array_proof=verify_actual_array_blocks(bound,registry,formset_id=fsid,form_id='STKBASIS',approved_blocks=approved_profile['array_blocks'])
    arrays=[a for b in array_proof['blocks']for a in b['records']if a['identifier']=='ACINTINC']
    if arrays!=[dict(identifier='ACINTINC',first_field=36,last_field=37,element_limit=65520,flags=49,byte27=0)]:raise ValueError('Exact original ACINTINC36..37 actual descriptor required')
    template=registry.resolve(fsid,'STKBASIS',identity);source={}
    for p in plans:
        if set(p)!={'field_id','ordinal','kind','format','template_attributes'}:raise ValueError('Exact source endpoint metadata protocol required')
        fields=[f for f in template.fields if f.field_id==p['field_id']]
        if len(fields)!=1 or tuple(getattr(fields[0],k)for k in('ordinal','kind','format','attributes'))!=tuple(p[k]for k in('ordinal','kind','format','template_attributes')):raise ValueError('Current endpoint metadata differs from reviewed source')
        if tuple(p[k]for k in('ordinal','kind','format','template_attributes'))!=((36,7,0,196)if p['field_id']=='AIPAYER'else(37,11,0,196)):raise ValueError('Exact original STKBASIS endpoint identity required')
        fid=p['field_id'].encode().ljust(32,b' ');entries=[e for e in form.derived_tail.field_map.entries if e.identifier==fid]
        if len(entries)!=1:raise ValueError('Both actual saved source D2 endpoint IDs required')
        source[p['field_id']]=entries[0].source_field_index
    tables=[t for t in form.tables if t.identifier.ljust(32,b' ')==b'ACINTINC'.ljust(32,b' ')]
    if len(tables)!=1 or(tables[0].word28,tables[0].word2a,tables[0].last_used_record_index)!=(source['AIPAYER'],source['AIAMT'],1)or source['AIPAYER']>source['AIAMT']:raise ValueError('Existing saved ACINTINC row1/header endpoints required; absent table cannot mean empty')
    bindings=bound.bindings.get(path,());examined=[]
    for b in bindings:
        inside=36<=b.current_field_index<=37 or source['AIPAYER']<=b.source_field_index<=source['AIAMT']
        if not inside:continue
        if b.current_field_index not in(36,37)or b.field_id not in(b'AIPAYER'.ljust(32,b' '),b'AIAMT'.ljust(32,b' '))or b.element_index!=1:raise ValueError('Any extra saved ACINTINC coordinate, even Unused or zero, requires native row inventory')
        if b.source_field_index!=source[b.field_id.rstrip(b' ').decode('ascii')]:raise ValueError('Source/current array coordinate collision')
        examined.append(dict(source_ordinal=b.source_field_index,current_ordinal=b.current_field_index,element_index=b.element_index,FV_attributes=b.fv_attributes))
    fid=b'AIAMT'.ljust(32,b' ');bs=[b for b in bindings if b.field_id==fid];node=find_value(form.hash_state,source['AIAMT'],1);record=None
    if node is not None:
        if len(bs)!=1 or(bs[0].source_field_index,bs[0].current_field_index,bs[0].element_index,bs[0].source_kind,bs[0].source_format,bs[0].fv_attributes)!=(source['AIAMT'],37,1,11,0,node.specific_attributes)or(node.kind_byte,node.flag10)!=(11,0):raise ValueError('Exact source/current AIAMT cents binding required')
        if bs[0].native_action not in('preserve','requires_additional_scalar_codec','drop_empty_storage'):raise ValueError('Unclosed AIAMT current conversion')
        record=StoredCents(node.kind_byte,node.raw,node.specific_attributes,node.header,node.flag10,node.flag11,node.exponent_byte)
    elif bs:raise ValueError('Current binding without source amount node')
    value=current_numeric_input(record);label='owned-STKBASIS-ACINTINC-row:1';engine=K1InterestFamilies(program,expected_sha256=expected_program_sha256,inputs={3541:{label:value}},prior_values={});roots=engine.run()
    return dict(source_sha256=digest,roots=roots,current_amount_trace=dict(document_path=list(path),document_file_copy=form.header.file_copy,runtime_copy_number=form.header.word7c,
        source_ordinal=source['AIAMT'],current_ordinal=37,element_index=1,source_node_exists=node is not None,present=record is not None and bool(record.attributes&1),
        raw64=None if node is None else str(node.raw),FV_attributes=0 if node is None else node.specific_attributes,packed_exponent=None if node is None else node.exponent_byte,rendered_current_text=render_current_cents(record)),
        evaluated_references=engine.trace,actual_array_proof=array_proof,strict_saved_array_coordinates=examined,hash_structure_validation=hash_receipt,
        source_STKBASIS14581_recomputed=True,source_complete14725=False,other_source_families_assumed_empty=False,
        caller_declared_ValueForm_factory=True,native_GetTable_Build_executed=False,native_qualified_UUID_mapping_executed=False,native_record_inventory_verified=False,
        saved_absence_is_not_native_runtime_absence=True,owned_labels_are_native_UUIDs=False,comparison_only=True,writeback_allowed=False,
        original_native_runtime=0,original_taxpayer_fixture=0,physical_writes=0)
