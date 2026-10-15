"""Independently authored complete v6 source; no vendor files or runtime."""
from pathlib import Path
from dataclasses import replace
import base64,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import binary_tax,create_typed_value_fixture as typed
from interop.derived_form.source_bound_value_document_reference import store_document_bytes,walk_forms,is_string_kind
from taxml_wire import read_xprf_resources
from create_binary_fixture import owned_xprf
from interop.derived_form.formset_attributes_reference import build_owned_attributes,UUID_NAME as FS_UUID
from interop.derived_form.entity_objects_reference import build_owned_objects,UUID_NAME as ENTITY_UUID
from interop.derived_form.legacy_entity_uuid_body_reference import NAME as LEGACY_UUID,encode_owned_legacy_uuid_body
from interop.derived_form.metadata_entity_body_reference import NAME as ENTITY_METADATA,encode_owned_metadata_entity_body
from interop.form_core.metadata_formset_body_reference import NAME as METADATA,Row,encode_owned_metadata_body

def second_owned_formset(request,doc,context):
    """Create a second explicitly bound own registry and a separate copy set."""
    original=doc.formsets[0];old=original.header.identifier;new=b'OWNED2025SECOND'
    if len(old)!=len(new):raise AssertionError('Own length-preserving registry owner edit')
    carriers=[];digests={}
    for carrier in request['carriers']:
        resources=read_xprf_resources(base64.b64decode(carrier['base64']),carrier['sha256'])
        resources={key:(value.replace(old,new) if key[0]==18000 else value) for key,value in resources.items()}
        raw=owned_xprf(resources);sha=hashlib.sha256(raw).hexdigest();digests[carrier['sha256']]=sha
        carriers.append(dict(base64=base64.b64encode(raw).decode(),sha256=sha))
    profile=request['profile'];templates=list(profile['templates']);factories=list(profile['form_factories'])
    request['carriers']+=carriers;profile['registry_order'] += [c['sha256'] for c in carriers]
    profile['templates'] += [dict(t,formset_id=new.decode(),carrier_sha256=digests[t['carrier_sha256']]) for t in templates]
    profile['form_factories'] += [dict(f,formset_id=new.decode()) for f in factories]
    profile['template_versions'][new.decode()]=profile['template_versions'][old.decode()]
    offset=max(f.table_id for _,f in walk_forms(doc));table_ids=dict(context.current_table_ids)
    def clone(form):
        table_id=form.table_id+offset;table_ids[new,form.header.file_copy]=table_id
        blocks=tuple(replace(block,nodes=tuple(replace(node,raw=(node.raw&~65535)|table_id) if is_string_kind(node.kind_byte) else node for node in block.nodes)) for block in form.hash_state.buffers)
        return replace(form,hash_state=replace(form.hash_state,buffers=blocks),table_id=table_id,source_table_id=None,
            children=tuple(clone(child) for child in form.children),metadata={})
    extra=replace(original,header=replace(original.header,identifier=new),forms=tuple(clone(f) for f in original.forms))
    def extend(mapping):return dict(mapping)|{(new,key[1]):value for key,value in mapping.items() if key[0]==old}
    context=replace(context,template_versions=dict(context.template_versions)|{new:context.template_versions[old]},
        field_ids=extend(context.field_ids),form_factories=extend(context.form_factories),table_factories=extend(context.table_factories),current_table_ids=table_ids)
    return replace(doc,formsets=(*doc.formsets,extra)),context

def fixture():
    request=typed.fixture();doc,buffers,bound,_,_,_=binary_tax._context(request)
    doc,base_context=second_owned_formset(request,doc,bound.context)
    uid=b'\x24'+b'11111111-2222-4333-8444-555555555555'
    rows=(Row(b'OWNED/ROW_A',b'alpha'),Row(b'OWNED/ROW_A',b'beta'),Row(b'OWNED/ROW_B',b'owned stored value'))
    sets=[]
    for fs in doc.formsets:
        objects=((FS_UUID,uid),(METADATA,encode_owned_metadata_body(rows)))
        sets.append(replace(fs,persistent_attributes=build_owned_attributes(objects,capacity=len(objects)*2+1,unused_offsets=(0x12345678,))))
    objects=((ENTITY_UUID,uid),(LEGACY_UUID,encode_owned_legacy_uuid_body(b'owned\0preserved\xfflegacy')),
        (ENTITY_METADATA,encode_owned_metadata_entity_body(rows)))
    doc=replace(doc,formsets=tuple(sets),persistent_objects=build_owned_objects(objects,capacity=len(objects)*2+1,unused_offsets=(0x87654321,)),metadata={},source_bytes=None)
    context=replace(base_context,entity_factory='value_entity',default_formset_factory=None,
        formset_factories={fs.header.identifier:'value_formset' for fs in doc.formsets})
    source=store_document_bytes(doc,buffers,template_context=context)
    profile=request['profile'];profile.update(format='tax-reborn-binary-entity-profile-v6',entity_factory='value_entity',
        formset_factories=[dict(formset_id=fs.header.identifier.decode(),formset_kind='value_formset') for fs in doc.formsets])
    request['base64']=base64.b64encode(source).decode()
    binary_tax.inspect_request(request)
    return request

def build(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    request=fixture();source=base64.b64decode(request['base64']);data=(json.dumps(request,sort_keys=True,indent=2)+'\n').encode()
    (destination/'persistent-document-income.taxbin').write_bytes(source)
    (destination/'persistent-document-income-request.json').write_bytes(data)
    result=dict(synthetic_only=True,vendor_resources_included=False,native_executions=0,
        bytes=len(source),sha256=hashlib.sha256(source).hexdigest(),request_sha256=hashlib.sha256(data).hexdigest())
    (destination/'persistent-document-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(build(ROOT/'fixtures/binary-tax'),indent=2))
