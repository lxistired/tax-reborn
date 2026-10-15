"""Read and preserve complete stored instance maps, not an active native cache."""
import base64,copy,json,struct,sys,unittest
from pathlib import Path
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import binary_tax,binary_derived,create_instance_map_fixture as fixture
from interop.form_core.instance_map_formset_body_reference import (NAME,StoredPair,encode_owned_body,load_stored_body,typed_raw_body_or_none,preserve_stored_body)
from interop.derived_form.formset_attributes_reference import load_attributes,preserve_attributes,build_owned_attributes,typed_body
from interop.derived_form.entity_objects_reference import typed_body as entity_body
from interop.derived_form.document_semantics_reference import document_semantic_snapshot
from interop.derived_form.source_bound_value_document_reference import walk_forms,store_document_bytes

def request():return json.loads((ROOT/'fixtures/binary-tax/instance-map-income-request.json').read_text())

class InstanceMapTests(unittest.TestCase):
    def test_fixture_complete_and_reproducible(self):
        req=request();self.assertEqual(req,fixture.fixture());view=binary_tax.inspect_request(req)
        self.assertFalse(view['unresolved_facts']);self.assertTrue(all(c['can_review'] for c in view['candidates']))
        self.assertEqual(len(view['binary_archive']['forms']),8)
        for fs in view['binary_archive']['persistent_objects']['formsets']:
            maps=[obj for obj in fs['persistent_attributes']['objects'] if obj['kind']=='stored_instance_map']
            self.assertEqual(len(maps),1);self.assertEqual(len(maps[0]['rows']),3)
            self.assertTrue(maps[0]['relocatable']);self.assertFalse(maps[0]['native_current_cache_verified'])
            self.assertFalse(maps[0]['native_cleanup_executed']);self.assertFalse(maps[0]['native_14D_transfer_executed'])

    def test_full_document_correction_all_stored_bodies_values_children_and_links(self):
        req=request();kept=copy.deepcopy(req);before=binary_tax.inspect_request(req)
        old,_,_,_,_,_=binary_tax._context(req);snapshot=document_semantic_snapshot(old)
        fact=next(f for f in before['binary_archive']['forms'][0]['fields'] if f['field_id']=='WAGES')
        output=binary_tax.edit_request({'inspection':req,'expected_source_sha256':before['source_sha256'],
            'changes':[{'path':[0,0],'field_id':'WAGES','element':0,'value':'1234.57'}],'confirmed':True})
        self.assertEqual(req,kept);self.assertTrue(output['binary_roundtrip_verified']);self.assertTrue(output['all_other_parsed_facts_preserved'])
        self.assertFalse(output['original_program_acceptance_verified']);self.assertFalse(output['full_return_recalculated'])
        new,_,_,_,_,_=binary_tax._context({**req,'base64':output['base64']})
        for a,b in zip(old.formsets,new.formsets):
            self.assertEqual(a.header,b.header)
            self.assertEqual([(o.class_name,o.body,o.source_wire)for o in a.persistent_attributes.objects],[(o.class_name,o.body,o.source_wire)for o in b.persistent_attributes.objects])
        self.assertEqual(old.persistent_objects.source_wire,new.persistent_objects.source_wire)
        after=binary_tax.inspect_request({**req,'base64':output['base64']})
        forms=after['binary_archive']['forms'];self.assertEqual(len(forms),8)
        self.assertEqual(sum(len(f['links'])for f in forms),8)
        self.assertTrue(all(f['links']and f['tables']and f['children'] for f in forms if f['path'][-1]==0 and len(f['path'])==2))
        self.assertEqual(next(f for f in forms[0]['fields'] if f['field_id']=='WAGES')['text'],'1234.57')
        self.assertEqual(forms[4]['fields'],before['binary_archive']['forms'][4]['fields'])
        # Public correction already checks the complete expected semantic
        # snapshot; independent per-object comparison above verifies every body.
        self.assertNotEqual(document_semantic_snapshot(new),snapshot)

    def test_exact_body_moves_only_as_raw_bytes_and_every_instance_validates(self):
        for compressed in (False,True):
            wire=encode_owned_body((StoredPair(b'OWNED/TPS/A',b'OWNED/MEF/A'),),compressed=compressed)
            attrs=build_owned_attributes(((NAME,wire),),base_position=100)
            output=preserve_attributes(attrs,base_position=999)
            moved=load_attributes(output,base_position=999)
            self.assertEqual(moved.objects[0].body,wire);self.assertEqual(moved.objects[0].source_wire,attrs.objects[0].source_wire)
            self.assertEqual(preserve_stored_body(typed_body(NAME,wire)),wire)
            self.assertIsNone(entity_body(NAME,wire))
            with self.assertRaises(ValueError):build_owned_attributes(((NAME,wire),(NAME,wire+b'x')))

    def test_unknown_version_and_empty_count_stay_opaque_and_movement_blocked(self):
        good=encode_owned_body((StoredPair(b'OWNED/A',b'OWNED/B'),))
        for wire in (b'\0\2'+good[2:],struct.pack('>HI',1,0),struct.pack('>HI',1,0)+b'unknown-empty-tail'):
            self.assertIsNone(typed_raw_body_or_none(wire));attrs=build_owned_attributes(((NAME,wire),),base_position=101)
            self.assertEqual(preserve_attributes(attrs,base_position=101),attrs.source_wire)
            with self.assertRaises(ValueError):preserve_attributes(attrs,base_position=102)

    def test_complete_source_with_unsupported_map_stays_inspectable_and_income_blocked(self):
        req=request();doc,_,_,_,_,_=binary_tax._context(req)
        obj=next(o for o in doc.formsets[0].persistent_attributes.objects if o.class_name==NAME)
        source=base64.b64decode(req['base64']);self.assertEqual(source.count(obj.body),1)
        for body in (b'\0\2'+obj.body[2:],obj.body[:2]+b'\0\0\0\0'+obj.body[6:]):
            view=binary_tax.inspect_request({**req,'base64':base64.b64encode(source.replace(obj.body,body,1)).decode()})
            maps=[o for o in view['binary_archive']['persistent_objects']['formsets'][0]['persistent_attributes']['objects'] if o['class_name']==NAME.decode()]
            self.assertEqual(maps[0]['kind'],'opaque');self.assertFalse(maps[0]['relocatable'])
            self.assertTrue(view['unresolved_facts']);self.assertTrue(all(not c['can_review'] for c in view['candidates']))

    def test_nonempty_bad_CRC_truncation_tail_count_and_duplicate_keys_refused(self):
        wire=encode_owned_body((StoredPair(b'A',b'X'),StoredPair(b'B',b'Y')),compressed=True)
        for bad in (wire[:-1],wire+b'x',wire[:2]+struct.pack('>I',3)+wire[6:],wire[:-2]+bytes([wire[-2]^1])+wire[-1:]):
            with self.assertRaises(ValueError):typed_body(NAME,bad)
        for rows in ((StoredPair(b'A',b'X'),StoredPair(b'A',b'Y')),(StoredPair(b'A',b'X'),StoredPair(b'B',b'X'))):
            with self.assertRaises(ValueError):encode_owned_body(rows)
        parsed=load_stored_body(wire)
        with self.assertRaises(ValueError):preserve_stored_body(replace(parsed,rows=tuple(reversed(parsed.rows))))

if __name__=='__main__':unittest.main()
