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
    profile=parser.add_mutually_exclusive_group()
    profile.add_argument('--auto-arrays',action='store_true')
    profile.add_argument('--typed-values',action='store_true')
    profile.add_argument('--whole-numbers',action='store_true')
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
    fixture_name='whole-number-income' if args.whole_numbers else 'typed-value-income' if args.typed_values else 'auto-array-income' if args.auto_arrays else 'derived-income'
    request=json.loads((ROOT/'fixtures/binary-tax'/(fixture_name+'-request.json')).read_text())
    before=binary_tax.inspect_request(request)
    expected=binary_tax.edit_request({'inspection':request,'expected_source_sha256':before['source_sha256'],
        'changes':[{'path':[0,0],'field_id':'OWNED_UNITS' if args.whole_numbers else 'WAGES','element':0,'value':'8' if args.whole_numbers else '1234.57'}],'confirmed':True})
    actual=Path(args.corrected_binary).read_bytes()
    assert actual==base64.b64decode(expected['base64']),'Actual selected file differs from complete source correction'
    assert len(actual)==(3831 if args.whole_numbers else 3787 if args.typed_values else 2906)
    digest=hashlib.sha256(actual).hexdigest()
    assert digest==('3772cb75235635e81d47d61ff526db44b40c8a1f4a372956a0307b979428cd7f' if args.whole_numbers else '5aa0b7e116870a3213a0d308c361230ff901c543aa0dac03aa9feec1ab6eab21' if args.typed_values else '179560f55862259878bdb45f8efe076e25c841d4425055618a579a2befa58b25')
    after=binary_tax.inspect_request({**request,'base64':base64.b64encode(actual).decode()})
    old=before['binary_archive']['forms'];new=after['binary_archive']['forms']
    assert len(old)==len(new)==4
    assert sum(len(f['links']) for f in new)==4
    assert old[0]['children']==new[0]['children']==1
    assert new[0]['table_headers'][0]['saved_last_used_record_index']==3
    wages=next(f for f in new[0]['fields'] if f['field_id']==('OWNED_UNITS' if args.whole_numbers else 'WAGES'))
    assert (wages['text'],wages['source_ordinal'],wages['current_ordinal'])==(('8',113,13) if args.whole_numbers else ('1234.57',104,4))
    movement=[]
    for a,b in zip(old,new):
        assert a['path']==b['path'] and a['table_headers']==b['table_headers'] and a['links']==b['links']
        assert a['derived']['fields']==b['derived']['fields']
        assert a['derived']['groups']==b['derived']['groups']
        assert a['derived']['sha256']==b['derived']['sha256']
        assert b['derived']['source_ordinals_preserved'] and not b['derived']['native_fixup_performed']
        movement.append(b['derived']['source_position']-a['derived']['source_position'])
    assert movement==([1,1,1,1] if args.whole_numbers else [2,2,2,2])
    assert expected['all_other_parsed_facts_preserved'] and expected['binary_roundtrip_verified']
    receipt={'system_saved_complete_ValueForm_bytes':len(actual),'system_saved_sha256':digest,
        'source_full_ID': 'OWNED_UNITS' if args.whole_numbers else 'WAGES','source_ordinal':113 if args.whole_numbers else 104,'current_ordinal':13 if args.whole_numbers else 4,
        'saved_field_maps_and_all_three_object_groups_retained':True,
        'typed_UUID_bodies_retained':True,'all_four_tails_moved_bytes':movement,
        'nonempty_table_child_and_four_links_retained':True,
        'other_parsed_facts_preserved':True,'full_file_readback':True,
        'original_engine_executed':False,'native_field_remap_executed':False,
        'whole_original_tax_compatibility':False,'synthetic_only':True}
    if args.auto_arrays or args.typed_values or args.whole_numbers:
        assert 'compiled_arrays' not in request['profile']
        assert before['registry_binding']==after['registry_binding']
        arrays=next(t for t in before['registry_binding']['selected_array_templates'] if t['form_id']=='FW2')
        assert [b['resource_id'] for b in arrays['blocks']]==[1,3]
        assert [b['records'][0]['byte27'] for b in arrays['blocks']]==[2,1]
        assert len({b['carrier_sha256'] for b in arrays['blocks']})==2
        receipt.update(automatic_arrays_from_same_registry=True,manual_array_lists=False,
            original_array_source_report_preserved=True,selected_array_sources=arrays,
            selected_source_profile_sha256=before['wire_profile_sha256'])
    if args.typed_values or args.whole_numbers:
        for a,b in zip(old,new):
            assert [len(g['objects']) for g in b['derived']['groups']]==[1,0,2]
            objects=b['derived']['groups'][2]['objects']
            assert [o['typed_value_body']['kind'] for o in objects]==['value_note','destination_reference']
            assert all(o['typed_value_body']['exact_source_body_preserved'] and o['typed_value_body']['relocatable'] for o in objects)
            assert a['derived']['groups']==b['derived']['groups']
        receipt.update(known_value_bodies_per_form=2,typed_value_note_and_destination_preserved=True,
            all_four_form_entire_derived_tails_preserved=True,source_record_class_6AB_not_admitted=True,
            native_row_lifecycle_executed=False)
    if args.whole_numbers:
        field=next(f for f in new[0]['fields'] if f['field_id']=='OWNED_UNITS')
        assert field['number_kind']=='whole_number' and field['template_bounds']['minimum']==1 and field['template_bounds']['maximum']==12
        assert not any(c['can_review'] for c in after['candidates'])
        receipt.update(whole_number7_to8=True,saved_template_minimum=1,saved_template_maximum=12,source_only=True,tax_values_imported=False,complete_native_validation=False)
    Path(args.output).write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__':main()
