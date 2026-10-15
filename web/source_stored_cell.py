"""Finite stored-cell correction; independent code, no original payload.

Authority is exact validated caller-resource bytes. This is an archive edit,
not native setter permission, active inventory, propagation or calculation.
"""
import base64,hashlib,re
from dataclasses import replace
from decimal import Decimal

PRIMARY='b100d55f8db5cf46d399082561e5f229f481981082241444c6a175213f5beca3'
BLOCKS=('53ec3cc1b55755f5ccc87f0bee5d24eee2e40e98c4b924f65d4ccd36a0c40028','a49e2f1045d9884348072a1d87cba032691818814d20f6bac1657a4cfa41bf58')
FS='S2025US1040PER'
class UnsupportedProfile(ValueError):pass
UnsupportedStoredCell=UnsupportedProfile
def _sha(data):return hashlib.sha256(data).hexdigest()
def _id(value):
    if type(value)is not bytes or not 0<len(value)<=32 or b'\0'in value:raise UnsupportedStoredCell('Exact stored field identity required.')
    return value.ljust(32,b' ')

# Separate byte-pinned policies. Neither request nor profile may supply authority.
POLICIES=(
 dict(policy_kind='sha_verified_original_caller_resources',fs=FS,form='FSCHB',primary=PRIMARY,rid=42,blocks=BLOCKS,field='AMT',ordinal=24,array='INT',array_index=3,first=23,last=24,limit=65520,fields=(('PAY',23,7,0,1092,True),('AMT',24,11,0,3652,True))),
 dict(policy_kind='independent_synthetic',fs='OWNEDCELL2025',form='FW2',primary='9d6a99e04548a3cfdc97462c5005dd25dee669de520c63ec32fc1c82790f837e',rid=1,blocks=('9716ee82d139e6c8d2091dcec07e6831145c2a2d279ed92c65688f967d01184e','96a296d224f285c67bee93c30f8a309157f0daa35dc5b87e410b78630a09cfc7'),field='SYNTHETIC_AMOUNT',ordinal=12,array='SYNTHETIC_ROWS',array_index=1,first=12,last=12,limit=10,fields=(('SYNTHETIC_AMOUNT',12,11,0,64,True),)),
)

def _domain(inspection,context,api,owner=None):
    if type(inspection)is not dict or type(inspection.get('profile'))is not dict or inspection['profile'].get('format')not in(api.derived.AUTOMATIC_PROFILES):return None
    doc,_,bound,registry,selected,_=context
    if not isinstance(bound,api.derived.BoundDocument):return None
    for policy in POLICIES:
        fs,form,primary,rid=(policy[k]for k in('fs','form','primary','rid'))
        if owner is not None and owner!=(fs.encode(),form.encode()):continue
        if selected.get((fs,form))!=(primary,rid):continue
        template=registry.resolve(fs,form,(primary,rid));fields={f.field_id:f for f in template.fields}
        if any(name not in fields for name,*_ in policy['fields']):continue
        if tuple((name,fields[name].ordinal,fields[name].kind,fields[name].format,fields[name].attributes,fields[name].is_array)for name,*_ in policy['fields'])!=policy['fields']:continue
        payloads=getattr(registry,'array_payloads',{}).get((fs,form))
        if payloads is None or len(payloads.blocks)!=2:continue
        if tuple(_sha(b.source_payload)if b.source_payload is not None else None for b in payloads.blocks)!=policy['blocks']:continue
        if len(payloads.records)<policy['array_index']:continue
        row=payloads.records[policy['array_index']-1]
        if (_id(row.identifier),row.global_index,row.first_field,row.last_field,row.element_limit,row.flags,row.byte27)!=(_id(policy['array'].encode()),policy['array_index'],policy['first'],policy['last'],policy['limit'],49,0):continue
        return policy
    return None

def _select(inspection,context,path,field_id,element,api):
    if type(path)is not list or len(path)<2 or any(type(x)is not int or not 0<=x<=65535 for x in path):raise UnsupportedStoredCell('Choose an exact existing stored form path.')
    doc,buffers,bound,registry,selected,source=context;key=tuple(path);forms=dict(api.walk_forms(doc))
    if key not in forms:raise UnsupportedStoredCell('The selected stored form is absent.')
    form=forms[key];owner=(doc.formsets[key[0]].header.identifier,form.header.identifier)
    policy=_domain(inspection,context,api,owner)
    if policy is None:raise UnsupportedStoredCell('This stored owner does not bind a supported byte-pinned cell policy.')
    fs,form_id,target,ordinal,array_id,array_index,limit=(policy[k]for k in('fs','form','field','ordinal','array','array_index','limit'))
    if field_id!=target or type(field_id)is not str or type(element)is not int or not 1<=element<=limit:raise UnsupportedStoredCell('Choose an existing positive stored amount element.')
    template=registry.resolve(fs,form_id,(policy['primary'],policy['rid']));values=[v for v in bound.bindings[key]if v.field_id==_id(target.encode())and v.element_index==element]
    if len(values)!=1:raise UnsupportedStoredCell('One existing source/current field binding is required.')
    binding=values[0]
    if(binding.current_field_index,binding.array_index,binding.element_limit,binding.native_action)!=(ordinal,array_index,limit,'requires_additional_scalar_codec'):raise UnsupportedStoredCell('Field shape or source/current identity is unresolved.')
    node=api.derived.find_value(form.hash_state,binding.source_field_index,element)
    physical=[n for block in form.hash_state.buffers for n in block.nodes if(n.field_index,n.element_index)==(binding.source_field_index,element)]
    if len(physical)!=1 or physical[0]is not node:raise UnsupportedStoredCell('One unique reachable existing source cell is required.')
    if(node.kind_byte,node.flag10,node.header)!=(11,0,0)or node.specific_attributes not in(1,3):raise UnsupportedStoredCell('Only existing Used, non-Override normal amount cells are supported.')
    keys=[k for k in bound.arrays if(_id(k[0]),_id(k[1]))==(_id(fs.encode()),_id(form_id.encode()))]
    if len(keys)!=1:raise UnsupportedStoredCell('Complete same-registry array context is required.')
    arrays=bound.arrays[keys[0]][0]+bound.arrays[keys[0]][1];matches=[(i,a)for i,a in enumerate(arrays,1)if a.first_field<=ordinal<=a.last_field]
    if len(matches)!=1 or matches[0][0]!=array_index:raise UnsupportedStoredCell('Current array membership is ambiguous.')
    array=matches[0][1]
    if(_id(array.identifier),array.first_field,array.last_field,array.element_limit,array.flags)!=(_id(array_id.encode()),policy['first'],policy['last'],limit,49):raise UnsupportedStoredCell('Stored array identity differs from the approved source metadata.')
    tables=[t for t in form.tables if _id(t.identifier)==_id(array_id.encode())]
    if len(tables)!=1 or type(tables[0].last_used_record_index)is not int or not element<=tables[0].last_used_record_index:raise UnsupportedStoredCell('An existing exact stored table and saved record boundary are required.')
    table=tables[0];entries=form.derived_tail.field_map.entries;by_id={_id(e.identifier):e.source_field_index for e in entries}
    columns=[f for f in template.fields if policy['first']<=f.ordinal<=policy['last']]
    if len(columns)!=policy['last']-policy['first']+1 or any(not f.is_array for f in columns)or any(_id(f.field_id.encode())not in by_id for f in columns):raise UnsupportedStoredCell('The complete saved/current table-column set is missing.')
    saved={by_id[_id(f.field_id.encode())]for f in columns}
    if saved!=set(range(table.word28,table.word2a+1))or binding.source_field_index not in saved:raise UnsupportedStoredCell('Saved table bounds and current full field identities disagree.')
    value=api.decode_amount(kind_byte=node.kind_byte,raw64=node.raw,exponent_byte=node.exponent_byte,fv_attributes=node.specific_attributes,value_header=node.header)
    if value.status!='value':raise UnsupportedStoredCell('The existing stored amount is not a supported numeric value.')
    owner=dict(formset_id=fs,form_id=form_id,fileCopyNum=str(form.header.file_copy),copyNum=form.header.word7c,binary_path=path)
    authority=dict(source_sha256=_sha(source),wire_profile_sha256=api.prep.canonical_hash(inspection['profile']),registry_order=[c['sha256']for c in inspection['carriers']],source_owner=owner,field_id=target,full_id_hex=_id(target.encode()).hex(),source_ordinal=binding.source_field_index,current_ordinal=ordinal,element=element,array_id_hex=_id(array_id.encode()).hex(),array_index=array_index,table_bounds=[table.word28,table.word2a],saved_last_used=table.last_used_record_index,raw64=str(node.raw),kind=11,format=0,header=node.header,exponent_byte=node.exponent_byte,flag11=node.flag11,FV_attributes=node.specific_attributes,primary=[policy['primary'],policy['rid']],array_payload_sha256=list(policy['blocks']),policy_kind=policy['policy_kind'])
    cell=dict(path=path,field_id=target,element=element,source_ordinal=binding.source_field_index,current_ordinal=ordinal,text=format(value.value,'f'),source_owner=owner,array_id=array_id,policy_kind=policy['policy_kind'],independent_synthetic_example=policy['policy_kind']=='independent_synthetic',can_review=False,can_correct_source=True,native_write_permission_verified=False,native_propagation=False,receipt=dict(source_sha256=authority['source_sha256'],wire_profile_sha256=authority['wire_profile_sha256'],cell_sha256=api.prep.canonical_hash(authority)))
    return form,binding,node,value,cell

def inspect_cells(inspection,context,*,binary_api):
    doc,_,bound,*_=context;result=[]
    if not isinstance(bound,binary_api.derived.BoundDocument):return result
    for path,form in binary_api.walk_forms(doc):
        policy=_domain(inspection,context,binary_api,(doc.formsets[path[0]].header.identifier,form.header.identifier))
        if policy is None:continue
        for binding in bound.bindings[path]:
            if binding.field_id!=_id(policy['field'].encode())or not binding.element_index:continue
            try:result.append(_select(inspection,context,list(path),policy['field'],binding.element_index,binary_api)[4])
            except UnsupportedStoredCell:pass
    return result

def correct_request(request):
    import binary_tax as api
    keys={'inspection','expected_source_sha256','expected_cell_sha256','path','field_id','element','value','confirmed'}
    if type(request)is not dict or set(request)!=keys or request['confirmed']is not True:raise UnsupportedStoredCell('Review and confirm one stored-cell correction.')
    context=api._context(request['inspection']);source=context[5]
    if request['expected_source_sha256']!=_sha(source):raise UnsupportedStoredCell('The source changed. Inspect it again.')
    form,binding,node,before,cell=_select(request['inspection'],context,request['path'],request['field_id'],request['element'],api)
    if request['expected_cell_sha256']!=cell['receipt']['cell_sha256']:raise UnsupportedStoredCell('The source profile or selected cell changed. Inspect it again.')
    text=request['value']
    if type(text)is not str or not re.fullmatch(r'-?[0-9]{1,13}(?:\.[0-9]{1,2})?',text):raise UnsupportedStoredCell('Enter a stored amount with at most two decimal places.')
    raw=Decimal(text).scaleb(2)
    if raw!=raw.to_integral_value()or not-(1<<63)<raw<(1<<63)-1:raise UnsupportedStoredCell('The corrected stored amount is out of range.')
    bits=int(raw)&((1<<64)-1)
    if bits==node.raw:raise UnsupportedStoredCell('Change the selected stored amount first.')
    decoded=api.decode_amount(kind_byte=11,raw64=bits,exponent_byte=node.exponent_byte,fv_attributes=node.specific_attributes,value_header=node.header)
    if decoded.status!='value':raise UnsupportedStoredCell('The corrected amount is reserved or unsupported.')
    changed_form=replace(form,hash_state=replace(form.hash_state,buffers=tuple(replace(block,nodes=tuple(replace(n,raw=bits)if n is node else n for n in block.nodes))for block in form.hash_state.buffers)))
    doc,buffers,bound,*_=context;changed=api.replace_form(doc,tuple(request['path']),changed_form);expected=api.derived_snapshot(changed);wire,reopened=api.derived.store_and_read(changed,buffers,bound)
    if api.derived_snapshot(reopened)!=expected:raise UnsupportedStoredCell('Complete source readback differed. No corrected file is supplied.')
    return dict(format='tax-reborn-source-stored-cell-correction-v1',mime='application/octet-stream',base64=base64.b64encode(wire).decode(),source_sha256=_sha(source),output_sha256=_sha(wire),source_profile_sha256=cell['receipt']['wire_profile_sha256'],source_address={k:cell[k]for k in('path','field_id','element','source_ordinal','current_ordinal')},previous_value=cell['text'],corrected_value=format(decoded.value,'f'),changed_fields=1,source_stored_cell_corrected=True,policy_kind=cell['policy_kind'],independent_synthetic_example=cell['independent_synthetic_example'],row_presence_changed=False,source_owners_changed=False,table_metadata_changed=False,all_other_parsed_facts_preserved=True,binary_roundtrip_verified=True,native_write_permission_verified=False,native_SetValue_executed=False,native_StoreEvent_or_Trim_executed=False,native_Build_or_UUID_executed=False,native_current_inventory_verified=False,native_propagation=False,tax_recalculated=False,original_program_acceptance_verified=False)
