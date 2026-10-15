"""Actual App loader/inspection/edit/export; independently generated own bytes."""
from pathlib import Path
from dataclasses import replace
import base64,copy,hashlib,json,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import binary_tax,binary_derived,create_typed_value_fixture as fixtures
from interop.derived_form.document_semantics_reference import document_semantic_snapshot
from interop.derived_form.source_bound_value_document_reference import walk_forms
from interop.derived_form.persistent_value_bodies_reference import VALUE_TAG,RECORD_ORDER

def request(name='typed-value-income'):
    return json.loads((ROOT/'fixtures/binary-tax'/(name+'-request.json')).read_text())

def edit(req):
    before=binary_tax.inspect_request(req)
    return binary_tax.edit_request(dict(inspection=req,expected_source_sha256=before['source_sha256'],
        changes=[dict(path=[0,0],field_id='WAGES',element=0,value='1234.57')],confirmed=True))

def malformed(req,mode):
    req=copy.deepcopy(req);wire=bytearray(base64.b64decode(req['base64']))
    name=RECORD_ORDER if mode=='reference_marker' else VALUE_TAG
    start=wire.rfind(name) if mode=='last_instance_version' else wire.find(name)
    if start<0:raise AssertionError('Own class body missing')
    body=start+len(name)+37
    if mode in ('version','last_instance_version'):wire[body:body+2]=b'\0\2'
    elif mode=='length':wire[body+2:body+4]=(int.from_bytes(wire[body+2:body+4],'big')+1).to_bytes(2,'big')
    elif mode=='embedded_nul':wire[body+4]=0
    elif mode=='field_zero':wire[start+len(name):start+len(name)+2]=b'\0\0'
    elif mode=='wrong_group':wire[start-2]=0xdd
    elif mode=='reference_marker':wire[body]=15
    else:raise AssertionError(mode)
    req['base64']=base64.b64encode(wire).decode();return req

class TypedValueAppTests(unittest.TestCase):
    def test_fixture_reproducibility(self):
        with tempfile.TemporaryDirectory() as directory:
            fixtures.build(directory)
            for p in Path(directory).iterdir():self.assertEqual(p.read_bytes(),(ROOT/'fixtures/binary-tax'/p.name).read_bytes())
    def test_every_value_body_inspected_and_income_reviewable(self):
        output=binary_tax.inspect_request(request());forms=output['binary_archive']['forms']
        self.assertFalse(output['unresolved_facts']);self.assertTrue(all(c['can_review'] for c in output['candidates']))
        self.assertEqual(len(forms),4)
        for form in forms:
            objects=form['derived']['groups'][2]['objects']
            self.assertEqual([o['typed_value_body']['kind'] for o in objects],['value_note','destination_reference'])
            self.assertTrue(all(o['typed_value_body']['exact_source_body_preserved'] and o['typed_value_body']['relocatable'] for o in objects))
            self.assertEqual(objects[1]['typed_value_body']['destination_formset_raw15_hex'],(b'OWNED'+b'\0'*10).hex())
            self.assertEqual(len(objects[1]['typed_value_body']['full_destination_id_hex']),64)
    def test_full_document_id_edit_preserves_bodies_graph_and_bits(self):
        req=request();before,doc,_,_=binary_tax._inspect(req);out=edit(req)
        self.assertEqual(hashlib.sha256(base64.b64decode(out['base64'])).hexdigest(),'5aa0b7e116870a3213a0d308c361230ff901c543aa0dac03aa9feec1ab6eab21')
        after,updated,_,_=binary_tax._inspect({**req,'base64':out['base64']})
        wage=next(v for v in before['binary_archive']['forms'][0]['fields'] if v['field_id']=='WAGES')
        self.assertEqual((wage['source_ordinal'],wage['current_ordinal']),(104,4))
        expected=doc;form=doc.formsets[0].forms[0]
        state=replace(form.hash_state,buffers=tuple(replace(b,nodes=tuple(replace(n,raw=123457) if (n.field_index,n.element_index)==(104,0) else n for n in b.nodes)) for b in form.hash_state.buffers))
        expected=binary_derived.replace_form(expected,(0,0),replace(form,hash_state=state))
        self.assertEqual(document_semantic_snapshot(expected),document_semantic_snapshot(updated))
        self.assertEqual(sum(len(f.links) for _,f in walk_forms(updated)),4)
        for (_,a),(_,b) in zip(walk_forms(doc),walk_forms(updated)):
            self.assertEqual(a.derived_tail.source_wire,b.derived_tail.source_wire)
            self.assertEqual(b.derived_tail.source_base_position-a.derived_tail.source_base_position,2)
            self.assertEqual(a.header,b.header);self.assertEqual(a.tables,b.tables);self.assertEqual(a.links,b.links)
        self.assertTrue(out['binary_roundtrip_verified']);self.assertFalse(out['full_return_recalculated'])
        self.assertEqual(after['candidates'][0]['amounts']['wages'],'1234.57')
    def test_empty_note_retains_four_byte_source_and_asymmetry(self):
        req=request('typed-value-empty');before,doc,_,_=binary_tax._inspect(req);out=edit(req)
        self.assertEqual(hashlib.sha256(base64.b64decode(out['base64'])).hexdigest(),'2111ad4d99eb6d48a06bfc02b819ca775fad1f8b45816f58787017dbb42e008d')
        after,updated,_,_=binary_tax._inspect({**req,'base64':out['base64']})
        for (_,a),(_,b) in zip(walk_forms(doc),walk_forms(updated)):
            self.assertEqual(a.derived_tail.source_wire,b.derived_tail.source_wire)
            self.assertEqual(b.derived_tail.groups[2][0].opaque_payload,b'\0\1\0\0')
        fact=after['binary_archive']['forms'][0]['derived']['groups'][2]['objects'][0]['typed_value_body']
        self.assertEqual(fact['text_bytes'],0);self.assertFalse(fact['native_store_length_written'])
    def test_v4_and_v5_keep_same_source_id_edit_contract(self):
        for version in (4,5):
            req=fixtures.fixture(format_version=version)
            self.assertEqual(binary_tax.inspect_request({**req,'base64':edit(req)['base64']})['candidates'][0]['amounts']['wages'],'1234.57')
    def test_malformed_known_class_blocked_in_shared_context(self):
        for mode in ('version','last_instance_version','length','embedded_nul','field_zero','wrong_group','reference_marker'):
            req=malformed(request(),mode)
            with self.subTest(mode=mode):
                with self.assertRaises(ValueError):binary_tax._context(req)
                with self.assertRaises(ValueError):binary_tax.inspect_request(req)
                with self.assertRaises(ValueError):edit(req)
    def test_unknown_record_still_readonly_and_blocks_movement(self):
        req=request('typed-value-opaque');before=binary_tax.inspect_request(req)
        self.assertTrue(all(not c['can_review'] for c in before['candidates']))
        self.assertIn('untyped_persistent_object',[v['code'] for v in before['unresolved_facts']])
        self.assertEqual([len(g['objects']) for g in before['binary_archive']['forms'][0]['derived']['groups']],[2,1,3])
        self.assertEqual(sum(bool(o.get('typed_value_body')) for o in before['binary_archive']['forms'][0]['derived']['groups'][2]['objects']),2)
        with self.assertRaises(ValueError):edit(req)
    def test_candidate_box_export_keeps_known_bodies(self):
        req=request();before=binary_tax.inspect_request(req);candidate=before['candidates'][0]
        amounts={k:candidate['amounts'][k] for k in binary_tax.prep.BOX_KEYS.values()};amounts['wages']='1234.57'
        out=binary_tax.export_request(dict(inspection=req,expected_candidate_sha256=candidate['receipt']['candidate_sha256'],amounts=amounts,confirmed=True))
        self.assertEqual(binary_tax.inspect_request({**req,'base64':out['base64']})['binary_archive']['forms'][0]['derived']['sha256'],before['binary_archive']['forms'][0]['derived']['sha256'])

if __name__=='__main__':unittest.main()
