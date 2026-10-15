"""Read an actual system-saved complete ValueForm correction, without UI seeding."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--corrected-binary')
    parser.add_argument('--make-orphan-fixture')
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    import binary_tax
    if args.make_orphan_fixture:
        import create_derived_binary_fixture
        request=create_derived_binary_fixture.fixture(hash_mode='null')
        target=Path(args.make_orphan_fixture);target.mkdir(parents=True,exist_ok=True)
        (target/'orphan.taxbin').write_bytes(base64.b64decode(request['base64']))
        (target/'profile.json').write_text(json.dumps(request['profile'],indent=2)+'\n')
        for i,carrier in enumerate(request['carriers']):
            (target/('registry-'+str(i)+'.xprf')).write_bytes(base64.b64decode(carrier['base64']))
        try:binary_tax.inspect_request(request)
        except ValueError as error:
            assert 'Source hash' in str(error)
        else:raise AssertionError('An unreachable source must not become current income')
        Path(args.output).write_text(json.dumps({'owned_malformed_fixture_created':True,'source_hash_rejected':True,'carrier_count':len(request['carriers'])},indent=2)+'\n')
        return
    if not args.corrected_binary:parser.error('--corrected-binary is required for readback')
    request=json.loads((ROOT/'fixtures/binary-tax/derived-income-request.json').read_text())
    before=binary_tax.inspect_request(request)
    expected=binary_tax.edit_request({'inspection':request,'expected_source_sha256':before['source_sha256'],
        'changes':[{'path':[0,0],'field_id':'WAGES','element':0,'value':'1234.57'}],'confirmed':True})
    actual=Path(args.corrected_binary).read_bytes()
    assert actual==base64.b64decode(expected['base64']),'Actual selected file differs from complete source correction'
    assert len(actual)==2906
    digest=hashlib.sha256(actual).hexdigest()
    assert digest=='179560f55862259878bdb45f8efe076e25c841d4425055618a579a2befa58b25'
    after=binary_tax.inspect_request({**request,'base64':base64.b64encode(actual).decode()})
    old=before['binary_archive']['forms'];new=after['binary_archive']['forms']
    assert len(old)==len(new)==4
    assert sum(len(f['links']) for f in new)==4
    assert old[0]['children']==new[0]['children']==1
    assert new[0]['table_headers'][0]['saved_last_used_record_index']==3
    wages=next(f for f in new[0]['fields'] if f['field_id']=='WAGES')
    assert (wages['text'],wages['source_ordinal'],wages['current_ordinal'])==('1234.57',104,4)
    movement=[]
    for a,b in zip(old,new):
        assert a['path']==b['path'] and a['table_headers']==b['table_headers'] and a['links']==b['links']
        assert a['derived']['fields']==b['derived']['fields']
        assert a['derived']['groups']==b['derived']['groups']
        assert a['derived']['sha256']==b['derived']['sha256']
        assert b['derived']['source_ordinals_preserved'] and not b['derived']['native_fixup_performed']
        movement.append(b['derived']['source_position']-a['derived']['source_position'])
    assert movement==[2,2,2,2]
    assert expected['all_other_parsed_facts_preserved'] and expected['binary_roundtrip_verified']
    receipt={'system_saved_complete_ValueForm_bytes':len(actual),'system_saved_sha256':digest,
        'source_full_ID_WAGES':True,'source_ordinal':104,'current_ordinal':4,
        'saved_field_maps_and_all_three_object_groups_retained':True,
        'typed_UUID_bodies_retained':True,'all_four_tails_moved_bytes':movement,
        'nonempty_table_child_and_four_links_retained':True,
        'other_parsed_facts_preserved':True,'full_file_readback':True,
        'original_engine_executed':False,'native_field_remap_executed':False,
        'whole_original_tax_compatibility':False,'synthetic_only':True}
    Path(args.output).write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__':main()
