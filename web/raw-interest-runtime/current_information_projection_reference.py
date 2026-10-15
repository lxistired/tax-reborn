"""Actual saved current information fields -> caller-owned CS -> owned proposals.

The caller explicitly orders this section before the interest graph. No claim
is made that the native scheduler ran it, that proposed keys already existed,
or that source/export state changed.
"""
import base64,hashlib
from information_section_reference import IntegerStorage,execute_section
from strict_actual_array_interest_reference import _raw_header_ids
from interop.derived_form.value_hash_wire_reference import find_value


def project_information(request,*,binary_loader,approved_identity,approved_fields,approved_section):
    if type(request)is not dict or request.get('source',{}).get('profile',{}).get('format')!='tax-reborn-binary-entity-profile-v5':
        raise ValueError('Explicit actual-v5 source request required')
    doc,buffers,bound,registry,selected,wire=binary_loader(request['source']);digest=hashlib.sha256(wire).hexdigest()
    if digest!=request.get('expected_source_sha256')or getattr(bound,'document',None)is not doc:raise ValueError('One exact source/current binding snapshot required')
    path=request.get('summary_path')
    if type(path)is not list or len(path)!=2 or any(type(i)is not int or i<0 for i in path):raise ValueError('Exact existing summary owner path required')
    try:fs=doc.formsets[path[0]];summary=fs.forms[path[1]]
    except IndexError as error:raise ValueError('Existing summary owner required')from error
    sid,parent=_raw_header_ids(summary)
    if sid.ljust(32,b' ')!=b'FSCHB'.ljust(32,b' ')or parent is not None:raise ValueError('Exact existing FSCHB root owner required')
    found=[(i,f)for i,f in enumerate(fs.forms)if f.header.identifier.ljust(32,b' ')==b'FINFOWKS'.ljust(32,b' ')]
    if len(found)!=1:raise ValueError('One existing same-owner FINFOWKS root required; no native form creation')
    index,form=found[0];formpath=(path[0],index);fid,parent=_raw_header_ids(form)
    if fid.ljust(32,b' ')!=b'FINFOWKS'.ljust(32,b' ')or parent is not None or form.header.word7c!=0:raise ValueError('Exact FINFOWKS copy0 root required')
    fsid=fs.header.identifier.decode().rstrip(' ');identity=selected.get((fsid,'FINFOWKS'))
    if identity is None or tuple(identity)!=tuple(approved_identity)or identity[0]!=approved_section['carrier_sha256']or identity[1]!=approved_section['resource_id']:
        raise ValueError('Current metadata and source program must use one approved carrier/form resource identity')
    key=(fs.header.identifier,form.header.identifier)
    if bound.context.form_factories.get(key)!='value_form'or bound.context.table_factories.get(key)!='value_table':raise ValueError('Explicit caller ValueForm/ValueTable factory boundary required')
    template=registry.resolve(fsid,'FINFOWKS',identity);stored={};trace=[]
    for plan in approved_fields:
        fields=[f for f in template.fields if f.field_id==plan['field_id']]
        if len(fields)!=1 or tuple(getattr(fields[0],k)for k in('ordinal','kind','format','attributes'))!=tuple(plan[k]for k in('ordinal','kind','format','template_attributes')):
            raise ValueError('Current complete target metadata differs from exact reviewed source')
        identifier=plan['field_id'].encode().ljust(32,b' ');entries=[e for e in form.derived_tail.field_map.entries if e.identifier==identifier]
        if len(entries)>1:raise ValueError('Ambiguous complete source D2 field ID')
        source=entries[0].source_field_index if entries else None;node=find_value(form.hash_state,source,0)if source is not None else None
        bs=[b for b in bound.bindings.get(formpath,())if b.field_id==identifier]
        if node is None:
            if bs:raise ValueError('Current scalar binding without source node')
            old=None
        else:
            if len(bs)!=1 or(bs[0].source_field_index,bs[0].current_field_index,bs[0].element_index,bs[0].source_kind,bs[0].source_format,bs[0].fv_attributes)!=(source,plan['ordinal'],0,10,0,node.specific_attributes):
                raise ValueError('Exact scalar kind10 full-ID source binding required')
            if(node.kind_byte,node.flag10,node.header,node.flag11)!=(10,0,0,0):raise ValueError('Finite ordinary current integer storage protocol required')
            old=IntegerStorage(node.raw,node.specific_attributes,node.header)
        stored[plan['ordinal']]=old
        trace.append(dict(field_id=plan['field_id'],source_ordinal=source,current_ordinal=plan['ordinal'],document_path=list(formpath),
            source_node_exists=node is not None,source_used=node is not None and bool(node.specific_attributes&1),
            raw64=None if node is None else str(node.raw),FV_attributes=None if node is None else node.specific_attributes))
    carriers=[x for x in request['source']['carriers']if x.get('sha256')==approved_section['carrier_sha256']]
    if len(carriers)!=1:raise ValueError('Exact one caller-owned local resource carrier required')
    raw=base64.b64decode(carriers[0]['base64'],validate=True)
    result=execute_section(raw,approved_section=approved_section,current_storage=stored,approved_fields=approved_fields)
    nr=next((p for p in approved_fields if p['field_id']=='PR1040NR'),None)
    if nr is None:raise ValueError('Exact PR1040NR producer target required')
    value=result['proposed_storage'][nr['ordinal']]
    if value is None or not value.attributes&1:raise ValueError('Proposed NR remains absent under exterior override; no false default')
    if value.raw64 not in(0,1):raise ValueError('Canonical integer0/1 normal case10 Boolean transform only')
    return dict(result,source_sha256=digest,current_target_trace=trace,projected_input_9801=bool(value.raw64),
        projected_input_origin='owned_CS113_proposed_kind10_state_then_case10_Boolean',
        stored_source_state_replaced=False,native_generic_mapping_constraints_executed=False,original_taxpayer_fixture=0,
        source_complete_calculation=False,information_document_file_copy=form.header.file_copy,information_runtime_copy_number=form.header.word7c)
