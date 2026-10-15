"""Owned complete v6 Entity14D(v1/v2/v3) archive fixtures; no vendor payloads."""
from pathlib import Path
from dataclasses import replace
import argparse,base64,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import binary_tax,create_instance_map_fixture as previous
from interop.derived_form.source_bound_value_document_reference import store_document_bytes
from interop.derived_form.entity_objects_reference import build_owned_objects
from interop.form_core import legacy_instance_map_entity_body_reference as legacy
from interop.form_core import instance_map_entity_body_reference as current


def fixture(version=2,*,body_override=None,extra_objects=()):
    req=previous.fixture();doc,buffers,bound,_,_,_=binary_tax._context(req)
    if body_override is None:
        if version==1:
            rows=(legacy.StoredPair(b'OWNED/TPS/v1/A',b'/OWNED/MEF/v1/A'),
                  legacy.StoredPair(b'OWNED/TPS/v1/B',b'/OWNED/MEF/v1/B'))
            body=legacy.encode_owned_legacy_body(rows)
        elif version==2:
            rows=tuple(current.StoredPair(('OWNED/TPS/v2/'+str(i)).encode(),('/OWNED/MEF/v2/'+str(i)).encode())for i in range(3))
            body=current.encode_owned_entity_body(rows,compressed=True)
        elif version==3:body=current.encode_owned_entity_body(())
        else:raise ValueError('Owned fixture version must be1/2/3')
    else:body=body_override
    objects=tuple((obj.class_name,obj.body)for obj in doc.persistent_objects.objects)+((current.NAME,body),)+tuple(extra_objects)
    doc=replace(doc,persistent_objects=build_owned_objects(objects,capacity=len(objects)*2+1,unused_offsets=(0x87654321,)),metadata={},source_bytes=None)
    raw=store_document_bytes(doc,buffers,template_context=bound.context)
    req['base64']=base64.b64encode(raw).decode();binary_tax.inspect_request(req)
    return req

def build(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);out=[]
    for version in(1,2,3):
        req=fixture(version);raw=base64.b64decode(req['base64']);stem='entity-instance-map-v'+str(version)+'-income'
        (destination/(stem+'.taxbin')).write_bytes(raw)
        (destination/(stem+'-request.json')).write_text(json.dumps(req,indent=2,sort_keys=True)+'\n')
        out.append(dict(version=version,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    return dict(synthetic_only=True,original_resources=False,native_Load=False,native_cleanup=False,native_14F_transfer=False,native_current_cache=False,fixtures=out)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--destination',type=Path,default=ROOT/'fixtures/binary-tax');a=p.parse_args()
    print(json.dumps(build(a.destination),indent=2))
