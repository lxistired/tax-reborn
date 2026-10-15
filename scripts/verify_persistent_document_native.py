"""Independently read an actual system-saved owned complete source copy."""
from pathlib import Path
import argparse,base64,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'web')]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--corrected-binary',required=True);parser.add_argument('--output',required=True);a=parser.parse_args()
    import binary_tax
    req=json.loads((ROOT/'fixtures/binary-tax/persistent-document-income-request.json').read_text())
    before=binary_tax.inspect_request(req);actual=Path(a.corrected_binary).read_bytes()
    assert len(actual)==8110 and hashlib.sha256(actual).hexdigest()=='c5bdc13fb5bdd8cb435e4e2eaad2fdb21077b5024a28e89e8b1bbcbc0e30ba26'
    expected=binary_tax.edit_request(dict(inspection=req,expected_source_sha256=before['source_sha256'],confirmed=True,
        changes=[dict(path=[0,0],field_id='WAGES',element=0,value='1234.57')]))
    assert actual==base64.b64decode(expected['base64'])
    after=binary_tax.inspect_request({**req,'base64':base64.b64encode(actual).decode()})
    old=before['binary_archive'];new=after['binary_archive'];assert old['formsets']==new['formsets']==2
    assert len(old['forms'])==len(new['forms'])==8 and sum(len(f['links']) for f in new['forms'])==8
    moves=[]
    for x,y in zip(old['forms'],new['forms']):
        for key in ('path','table_headers','links','children'):assert x[key]==y[key]
        for key in ('sha256','fields','groups'):assert x['derived'][key]==y['derived'][key]
        moves.append(y['derived']['source_position']-x['derived']['source_position'])
    assert moves==[2]*8
    def same_group(x,y):
        for key in ('capacity','used','relative_offsets','bytes','sha256'):assert x[key]==y[key]
        assert y['source_position']-x['source_position']==2
        for p,q in zip(x['objects'],y['objects']):
            assert {k:v for k,v in p.items() if k!='source_position'}=={k:v for k,v in q.items() if k!='source_position'}
            assert q['source_position']-p['source_position']==2 and not q['active_native_value']
    p=old['persistent_objects'];q=new['persistent_objects'];same_group(p['entity'],q['entity'])
    assert len(q['entity']['objects'])==3
    for x,y in zip(p['formsets'],q['formsets']):
        assert x['index']==y['index'] and x['formset_id']==y['formset_id']
        same_group(x['persistent_attributes'],y['persistent_attributes'])
        assert len(y['persistent_attributes']['objects'])==2
    wage=next(f for f in new['forms'][0]['fields'] if f['field_id']=='WAGES')
    assert (wage['text'],wage['source_ordinal'],wage['current_ordinal'])==('1234.57',104,4)
    receipt=dict(actual_system_file_readback=True,bytes=len(actual),sha256=hashlib.sha256(actual).hexdigest(),formsets=2,forms=8,
        links=8,nonempty_tables_and_children_preserved=True,all_eight_form_tails_preserved=True,
        Entity_14B_146_147_and_both_FormSet_148_151_original_wire_retained=True,all_three_persistent_layers_moved_by=2,
        ordered_duplicate_metadata_rows_preserved=True,
        source_current_ordinals=[104,4],original_engine_executed=False,active_native_metadata=False,
        whole_original_tax_compatibility=False,synthetic_only=True)
    Path(a.output).write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))

if __name__=='__main__':main()
