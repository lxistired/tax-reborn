"""Owned complete source with an existing whole-number field and2160 bounds."""
from pathlib import Path
from dataclasses import replace
import base64,hashlib,json,struct,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import create_binary_fixture as original
import create_typed_value_fixture as typed
from taxml_wire import Registry,read_xprf_resources
from interop.form_core.value_hash_wire_reference import Node,hash_for_nodes


def fixture(*,value=7,attrs=1,header=0,exponent=0,flag11=0,limits='cross_home'):
    old_inputs=original.value_table_inputs;old_document=original.value_table_document
    def inputs():
        fsid,templates,context,profile,carriers,report=old_inputs();replacements={};updated=[]
        for i,carrier in enumerate(carriers):
            resources=read_xprf_resources(base64.b64decode(carrier['base64']),carrier['sha256'])
            if i==1:
                body=resources[1901,1];count=int.from_bytes(body[:2],'little')
                resources[1901,1]=struct.pack('<H',count+1)+body[2:]+b'\xff'+b'OWNED_UNITS'.ljust(32,b' ')+struct.pack('<BBI',13,0,0)
                if limits=='primary_empty':resources[2160,1]=b'\0\0'
                if limits=='primary_miss':resources[2160,1]=struct.pack('<HHiiHH',1,12,0,100,0,3)
            elif limits!='absent':
                resources[2160,1]=struct.pack('<HHiiHH',1,13,-10000 if limits=='wide' else 1,10000 if limits=='wide' else 12,0,3)
                if limits=='malformed':resources[2160,1]+=b'X'
            wire=original.owned_xprf(resources);digest=hashlib.sha256(wire).hexdigest();replacements[carrier['sha256']]=digest;updated.append(dict(base64=base64.b64encode(wire).decode(),sha256=digest))
        profile['registry_order']=[c['sha256']for c in updated]
        for row in profile['templates']:row['carrier_sha256']=replacements[row['carrier_sha256']]
        selected={(r['formset_id'],r['form_id']):(r['carrier_sha256'],r['resource_id'])for r in profile['templates']}
        registry=Registry.from_effective_xprf([(base64.b64decode(c['base64']),c['sha256'])for c in updated],selected)
        templates={name:registry.resolve(fs,name,identity)for(fs,name),identity in selected.items()}
        return fsid,templates,context,profile,updated,registry.binding_report
    def document(templates,fsid):
        doc=old_document(templates,fsid);root=doc.formsets[0].forms[0]
        nodes=tuple(n for block in root.hash_state.buffers for n in block.nodes)
        nodes+=(Node(kind_byte=13,raw=value&((1<<64)-1),field_index=13,specific_attributes=attrs,header=header,exponent_byte=exponent,flag11=flag11),)
        root=replace(root,hash_state=hash_for_nodes(nodes));return replace(doc,formsets=(replace(doc.formsets[0],forms=(root,)+doc.formsets[0].forms[1:]),))
    original.value_table_inputs=inputs;original.value_table_document=document
    try:return typed.fixture()
    finally:original.value_table_inputs=old_inputs;original.value_table_document=old_document


def build(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);request=fixture();wire=base64.b64decode(request['base64']);encoded=(json.dumps(request,sort_keys=True,indent=2)+'\n').encode()
    for name,data in [('whole-number-income.taxbin',wire),('whole-number-income-request.json',encoded)]:
        (destination/name).write_bytes(data)
    return dict(bytes=len(wire),sha256=hashlib.sha256(wire).hexdigest(),request_sha256=hashlib.sha256(encoded).hexdigest(),vendor_resources=False)

if __name__=='__main__':print(json.dumps(build(ROOT/'fixtures/binary-tax')))
