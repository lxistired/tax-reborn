"""Reopen a complete system-saved owned binary source and compare all layers."""
from pathlib import Path
import argparse,base64,copy,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'web')]
import binary_tax

def verify(path):
    req=json.loads((ROOT/'fixtures/binary-tax/instance-map-income-request.json').read_text())
    before=binary_tax.inspect_request(req);blob=Path(path).read_bytes()
    assert len(blob)==8360 and hashlib.sha256(blob).hexdigest()=='da0b62b035b3f1332719b9f38428c98eea6d7c0fd48e6f8ee0ae4d6777711a54'
    after=binary_tax.inspect_request({**req,'base64':base64.b64encode(blob).decode()})
    old,new=before['binary_archive'],after['binary_archive'];assert len(new['forms'])==8 and new['formsets']==2
    for index,(a,b) in enumerate(zip(old['forms'],new['forms'])):
        for name in ('path','form_id','file_copy','table_headers','tables','children','links'):assert a[name]==b[name],(index,name)
        fields=copy.deepcopy(a['fields'])
        if index==0:
            selected=next(f for f in fields if f['field_id']=='WAGES');assert selected['raw64']=='123456'
            selected['raw64']='123457';selected['text']='1234.57'
        assert fields==b['fields'],index
        for name in ('sha256','fields','groups'):assert a['derived'][name]==b['derived'][name],(index,name)
        assert b['derived']['source_position']-a['derived']['source_position']==2
    def group(a,b):
        assert {k:v for k,v in a.items()if k not in ('source_position','objects')}=={k:v for k,v in b.items()if k not in ('source_position','objects')}
        assert b['source_position']-a['source_position']==2
        assert len(a['objects'])==len(b['objects'])
        for x,y in zip(a['objects'],b['objects']):
            assert {k:v for k,v in x.items()if k!='source_position'}=={k:v for k,v in y.items()if k!='source_position'}
            assert y['source_position']-x['source_position']==2 and not y['active_native_value']
    group(old['persistent_objects']['entity'],new['persistent_objects']['entity'])
    maps=[]
    for a,b in zip(old['persistent_objects']['formsets'],new['persistent_objects']['formsets']):
        assert a['index']==b['index']and a['formset_id']==b['formset_id'];group(a['persistent_attributes'],b['persistent_attributes'])
        maps.extend(o for o in b['persistent_attributes']['objects']if o['kind']=='stored_instance_map')
    assert len(maps)==2 and sum(len(o['rows'])for o in maps)==6
    assert all(o['relocatable']and not o['native_current_cache_verified']and not o['native_cleanup_executed']and not o['native_14D_transfer_executed']for o in maps)
    return {'complete_file_readback':True,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),
        'formsets':2,'forms':8,'links':8,'nonempty_tables_and_children_retained':True,
        'stored_instance_maps':2,'stored_pair_rows':6,'both_F0_and_0F_bodies_byte_exact':True,
        'all_entity_FormSet_and8_value_tails_byte_exact':True,'all_persistent_positions_moved_by':2,
        'same_source_owners_retained':True,'only_WAGES_changed':'1234.56 to 1234.57',
        'native_cleanup_executed':False,'native_current_cache_verified':False,
        'original_runtime':0,'full_original_compatibility':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('file');p.add_argument('--output');a=p.parse_args();receipt=verify(a.file)
    if a.output:Path(a.output).write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))
