"""Complete independently authored v6 source with stored FormSet instance maps."""
from pathlib import Path
from dataclasses import replace
import base64,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import binary_tax,create_persistent_document_fixture as old
from interop.derived_form.source_bound_value_document_reference import store_document_bytes
from interop.derived_form.formset_attributes_reference import build_owned_attributes
from interop.form_core.instance_map_formset_body_reference import NAME,StoredPair,encode_owned_body

def fixture():
    req=old.fixture();doc,buffers,bound,_,_,_=binary_tax._context(req);sets=[]
    for index,fs in enumerate(doc.formsets):
        rows=tuple(StoredPair(('OWNED/TPS/'+str(index)+'/'+str(i)).encode(),
                             ('OWNED/MEF/'+str(index)+'/'+str(i)).encode()) for i in range(3))
        body=encode_owned_body(rows,compressed=index==0)
        records=tuple((obj.class_name,obj.body) for obj in fs.persistent_attributes.objects)+((NAME,body),)
        attrs=build_owned_attributes(records,capacity=2*len(records)+1,unused_offsets=(0x12345678,))
        sets.append(replace(fs,persistent_attributes=attrs))
    doc=replace(doc,formsets=tuple(sets),metadata={},source_bytes=None)
    blob=store_document_bytes(doc,buffers,template_context=bound.context)
    req['base64']=base64.b64encode(blob).decode();binary_tax.inspect_request(req)
    return req

def build(destination=ROOT/'fixtures/binary-tax'):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    req=fixture();blob=base64.b64decode(req['base64']);payload=(json.dumps(req,indent=2,sort_keys=True)+'\n').encode()
    (destination/'instance-map-income.taxbin').write_bytes(blob)
    (destination/'instance-map-income-request.json').write_bytes(payload)
    (destination/'instance-map-profile.json').write_text(json.dumps(req['profile'],indent=2,sort_keys=True)+'\n')
    for index,carrier in enumerate(req['carriers']):
        (destination/('instance-map-registry-'+str(index)+'.xprf')).write_bytes(base64.b64decode(carrier['base64']))
    receipt={'synthetic_only':True,'vendor_resources_included':False,'original_runtime':0,
        'formsets':2,'forms':8,'stored_instance_map_objects':2,'stored_pairs':6,
        'body_compression':['F0-mode4','0F-stored'],'native_cleanup_executed':False,
        'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),
        'request_sha256':hashlib.sha256(payload).hexdigest()}
    (destination/'instance-map-manifest.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':print(json.dumps(build()))
