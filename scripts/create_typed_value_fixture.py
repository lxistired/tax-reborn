"""Owned v4/v5 sources with two source-proven native value-object body types."""
from pathlib import Path
import base64,hashlib,json,struct,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import create_derived_binary_fixture as derived
import create_auto_array_fixture as automatic
from interop.derived_form.value_form_tail_reference import load_value_form_tail
from interop.derived_form.persistent_value_bodies_reference import (
    VALUE_TAG,RECORD_ORDER,encode_nonempty_value_tag_body,encode_canonical_record_order_body)

def group_wire(group,objects):
    capacity=max(1,len(objects)*2);cursor=5+capacity*4;positions=[];payload=b''
    for obj in objects:
        positions.extend((cursor+len(payload),cursor+len(payload)+len(obj)));payload+=obj
    positions.extend([0xffffffff]*(capacity-len(positions)))
    return bytes([(0xd1,0xde,0xdf)[group]])+struct.pack('>HH',capacity,len(objects)*2)+struct.pack('<'+'I'*capacity,*positions)+payload

def typed_tail(template,copy,*,opaque=False,empty_note=False):
    tail=derived.tail(template,copy,opaque=opaque)
    target=next((f for f in template.fields if f.field_id=='WAGES'),template.fields[0])
    attachment=struct.pack('>HH',target.ordinal+100,0)+b'\xff'+target.field_id.encode().ljust(32,b' ')
    def obj(name,body):return b'\xdb'+bytes([len(name)])+name+attachment+body
    note=(b'\0\1\0\0' if empty_note else encode_nonempty_value_tag_body(b'Owned saved value note '+template.form_id.encode()))
    order=encode_canonical_record_order_body(b'OWNED',b'OWNED_DESTINATION'.ljust(32,b' '),12,4)
    groups=[[o.source_wire for o in group] for group in tail.groups]
    groups[2]+=[obj(VALUE_TAG,note),obj(RECORD_ORDER,order)]
    return load_value_form_tail(tail.field_map.source_wire+b''.join(group_wire(i,g) for i,g in enumerate(groups)))

def fixture(*,format_version=5,empty_note=False,opaque=False):
    if format_version not in (4,5):raise ValueError('Owned v4/v5 fixture only')
    make_tail=lambda template,copy,**options:typed_tail(template,copy,empty_note=empty_note,**options)
    return (automatic.fixture if format_version==5 else derived.fixture)(tail_factory=make_tail,opaque=opaque)

def build(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);entries={}
    for name,options in [('typed-value-income',{}),('typed-value-empty',{'empty_note':True}),('typed-value-opaque',{'opaque':True})]:
        request=fixture(**options);source=base64.b64decode(request['base64'])
        encoded=(json.dumps(request,sort_keys=True,indent=2)+'\n').encode()
        (destination/(name+'.taxbin')).write_bytes(source)
        (destination/(name+'-request.json')).write_bytes(encoded)
        entries[name]=dict(bytes=len(source),sha256=hashlib.sha256(source).hexdigest(),request_sha256=hashlib.sha256(encoded).hexdigest())
    manifest=dict(vendor_resources_included=False,original_runtime_executions=0,
        record_order_attachment='value/group2; not record-row data',
        empty_value_note='explicit4-byte source preserved; native2-byte empty Store not emitted',entries=entries)
    (destination/'typed-value-manifest.json').write_bytes((json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode('utf-8'))
    return manifest

if __name__=='__main__':print(json.dumps(build(ROOT/'fixtures/binary-tax'),indent=2))
