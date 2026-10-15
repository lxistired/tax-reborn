"""Independent complete source-cell example; no original input or payload."""
from pathlib import Path
from dataclasses import replace
import argparse,base64,hashlib,json,struct,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import binary_tax,create_entity_instance_map_fixture as previous
from create_binary_fixture import owned_xprf
from interop.derived_form.source_bound_value_document_reference import store_document_bytes
from interop.derived_form.value_form_tail_reference import load_value_form_tail
OLD='OWNED2025MERGED';FS='OWNEDCELL2025';FIELD='SYNTHETIC_AMOUNT';ARRAY='SYNTHETIC_ROWS'

def fixture():
    req=previous.fixture(2);doc,buffers,bound,*_=binary_tax._context(req);digests={};carriers=[]
    for item in req['carriers']:
        resources=binary_tax.wire.read_xprf_resources(base64.b64decode(item['base64']),item['sha256'])
        owned_first=False
        for key,payload in list(resources.items()):
            if key[0]in range(18000,19000):
                count=struct.unpack_from('<H',payload)[0];pos=2;strings=[]
                for _ in range(count):size=payload[pos];pos+=1;strings.append(payload[pos:pos+size]);pos+=size
                assert pos==len(payload)
                if len(strings)>1 and strings[1]==OLD.encode():
                    owned_first=owned_first or key[0]==18000;strings[1]=FS.encode();resources[key]=struct.pack('<H',len(strings))+b''.join(bytes([len(s)])+s for s in strings)
        if owned_first:
            for key,payload in list(resources.items()):
                if key[0]in(1900,1901):
                    old=b'OWNED_AMOUNT'.ljust(32,b' ');new=FIELD.encode().ljust(32,b' ')
                    resources[key]=payload.replace(old,new)
                elif key[0]==2000:
                    payload=payload.replace(b'OWNED_ROWS'.ljust(32,b' '),ARRAY.encode().ljust(32,b' '));assert struct.unpack_from('<H',payload)[0]==1
                    resources[key]=payload[:-2]+bytes([49,0])
                elif key[0]==2001:resources[key]=b'\0\0'
        raw=owned_xprf(resources);digest=hashlib.sha256(raw).hexdigest();digests[item['sha256']]=digest;carriers.append(dict(base64=base64.b64encode(raw).decode(),sha256=digest))
    def rename(value):
        if isinstance(value,dict):return{FS if k==OLD else k:rename(v)for k,v in value.items()}
        if isinstance(value,list):return[rename(v)for v in value]
        if isinstance(value,str):return FS if value==OLD else digests.get(value,value)
        return value
    req['profile']=rename(req['profile']);req['carriers']=carriers
    old_bytes=OLD.encode();fs_bytes=FS.encode()
    def key(k):return tuple(fs_bytes if x==old_bytes else x for x in k)if isinstance(k,tuple)else fs_bytes if k==old_bytes else k
    ctx=bound.context
    ids={key(k):{index:FIELD.encode()if k[0]==old_bytes and value==b'OWNED_AMOUNT'else value for index,value in rows.items()}for k,rows in ctx.field_ids.items()}
    ctx=replace(ctx,template_versions={key(k):v for k,v in ctx.template_versions.items()},field_ids=ids,current_table_ids={key(k):v for k,v in ctx.current_table_ids.items()},form_factories={key(k):v for k,v in ctx.form_factories.items()},table_factories={key(k):v for k,v in ctx.table_factories.items()},formset_factories={key(k):v for k,v in ctx.formset_factories.items()})
    def own_form(form,first):
        meta={k:v for k,v in form.metadata.items()if k!='source_value_form_scope'};children=tuple(own_form(c,first)for c in form.children)
        if first and form.header.identifier==b'FW2':
            old=b'OWNED_AMOUNT'.ljust(32,b' ');wire=form.derived_tail.source_wire;assert wire.count(old)==1
            tail=load_value_form_tail(wire.replace(old,FIELD.encode().ljust(32,b' ')),base_position=form.derived_tail.source_base_position)
            state=replace(form.hash_state,buffers=tuple(replace(block,nodes=tuple(replace(n,specific_attributes=3)if n.field_index==112 and n.element_index in(1,3)else n for n in block.nodes))for block in form.hash_state.buffers))
            return replace(form,hash_state=state,tables=tuple(replace(t,identifier=ARRAY.encode())if t.identifier==b'OWNED_ROWS'else t for t in form.tables),derived_tail=tail,metadata=meta,children=children)
        return replace(form,metadata=meta,children=children)
    sets=[]
    for fs in doc.formsets:
        first=fs.header.identifier==old_bytes;sets.append(replace(fs,header=replace(fs.header,identifier=fs_bytes)if first else fs.header,forms=tuple(own_form(f,first)for f in fs.forms),metadata={}))
    doc=replace(doc,formsets=tuple(sets),metadata={},source_bytes=None);raw=store_document_bytes(doc,buffers,template_context=ctx);req['base64']=base64.b64encode(raw).decode();binary_tax._context(req)
    return req

def build(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True);req=fixture();raw=base64.b64decode(req['base64'])
    (destination/'request.json').write_text(json.dumps(req,indent=2,sort_keys=True)+'\n');(destination/'profile.json').write_text(json.dumps(req['profile'],indent=2,sort_keys=True)+'\n');(destination/'owned-source-cell.taxbin').write_bytes(raw)
    for i,c in enumerate(req['carriers']):(destination/('owned-registry-'+str(i)+'.xprf')).write_bytes(base64.b64decode(c['base64']))
    # Fixed independent sample readback contracts; neither caller claims nor
    # these expected hashes grant authority to any other primary or payload.
    expected=dict(independently_generated=True,original_resource_payload=False,original_taxpayer_fixture=False,policy_kind='independent_synthetic',source_sha256=hashlib.sha256(raw).hexdigest(),outputs=[dict(element=1,value='1234.57',filename='source-stored-cell-element1-corrected.taxbin',bytes=8458,sha256='4d2abb06f88a75264de6c8ffd84ce5398e30bf773599baf6076074bbc440f2cc'),dict(element=3,value='12.34',filename='source-stored-cell-element3-corrected.taxbin',bytes=8460,sha256='13922dffeae4e0d026d7f59ebabad85ba6f7d4683f68d53e2f4ef44276e1a77d')],native_propagation=False,tax_recalculated=False)
    (destination/'expected.json').write_text(json.dumps(expected,indent=2)+'\n')
    return dict(independently_generated=True,original_resource_payload=False,original_field_ID_map=False,original_taxpayer_fixture=False,source_bytes=len(raw),source_sha256=hashlib.sha256(raw).hexdigest())
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--destination',type=Path,default=ROOT/'fixtures/source-cell');a=p.parse_args();print(json.dumps(build(a.destination),indent=2))
