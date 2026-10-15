"""Complete source editing with two additional persisted-object scopes."""
from pathlib import Path
from dataclasses import replace
import base64,copy,hashlib,json,sys,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import binary_tax,binary_derived,create_persistent_document_fixture as fixture
from interop.derived_form.document_semantics_reference import document_semantic_snapshot
from interop.derived_form.source_bound_value_document_reference import walk_forms
from interop.derived_form.formset_attributes_reference import build_owned_attributes
from interop.derived_form.entity_objects_reference import build_owned_objects

def request():return json.loads((ROOT/'fixtures/binary-tax/persistent-document-income-request.json').read_text())
def edit(req):return binary_tax.edit_request(dict(inspection=req,expected_source_sha256=hashlib.sha256(base64.b64decode(req['base64'])).hexdigest(),confirmed=True,changes=[dict(path=[0,0],field_id='WAGES',element=0,value='1234.57')]))
def rename(req,name):
    out=copy.deepcopy(req);raw=base64.b64decode(out['base64']);assert raw.count(name)>=1
    out['base64']=base64.b64encode(raw.replace(name,b'X'+name[1:],1)).decode();return out

class PersistentDocumentAppTests(unittest.TestCase):
    def test_owned_fixture_reproducible_and_three_persistent_scopes(self):
        req=request();self.assertEqual(req,fixture.fixture())
        view,doc,_,_=binary_tax._inspect(req);groups=view['binary_archive']['persistent_objects']
        self.assertEqual(len(view['binary_archive']['forms']),8)
        self.assertEqual(sum(len(f.links) for _,f in walk_forms(doc)),8)
        self.assertTrue(any(f.tables for _,f in walk_forms(doc)));self.assertTrue(any(f.children for _,f in walk_forms(doc)))
        self.assertEqual([o['class_name'] for o in groups['entity']['objects']],['zccPersistentEntityUUID','zccPersisUUID','MetaDataKeyValuePersistentObject'])
        metadata=groups['formsets'][0]['persistent_attributes']['objects'][1]
        self.assertEqual(metadata['kind'],'stored_metadata');self.assertEqual(len(metadata['rows']),3)
        self.assertEqual(metadata['rows'][0]['path_hex'],metadata['rows'][1]['path_hex'])
        self.assertNotEqual(metadata['rows'][0]['text_hex'],metadata['rows'][1]['text_hex'])
        self.assertFalse(metadata['native_set_value_executed']);self.assertTrue(all(c['can_review'] for c in view['candidates']))

    def test_complete_correction_keeps_all_three_raw_persistent_layers(self):
        req=request();before,doc,buffers,bound=binary_tax._inspect(req);initial=copy.deepcopy(req)
        out=edit(req);after,updated,_,_=binary_tax._inspect({**req,'base64':out['base64']})
        self.assertEqual(req,initial);self.assertEqual(after['candidates'][0]['amounts']['wages'],'1234.57')
        self.assertTrue(out['binary_roundtrip_verified']);self.assertFalse(out['full_return_recalculated'])
        delta=len(base64.b64decode(out['base64']))-len(base64.b64decode(req['base64']));self.assertNotEqual(delta,0)
        self.assertEqual(doc.persistent_objects.source_wire,updated.persistent_objects.source_wire)
        self.assertEqual(updated.persistent_objects.source_base_position-doc.persistent_objects.source_base_position,delta)
        self.assertEqual(doc.persistent_objects.offsets[-1],0x87654321)
        for a,b in zip(doc.formsets,updated.formsets):
            self.assertEqual(a.persistent_attributes.source_wire,b.persistent_attributes.source_wire)
            self.assertEqual(b.persistent_attributes.source_base_position-a.persistent_attributes.source_base_position,delta)
            self.assertEqual(a.persistent_attributes.offsets[-1],0x12345678)
        for (_,a),(_,b) in zip(walk_forms(doc),walk_forms(updated)):
            self.assertEqual(a.derived_tail.source_wire,b.derived_tail.source_wire)
            self.assertEqual(a.tables,b.tables);self.assertEqual(a.links,b.links);self.assertEqual(a.header,b.header)
        self.assertEqual(before['binary_archive']['persistent_objects']['entity']['sha256'],after['binary_archive']['persistent_objects']['entity']['sha256'])

    def test_explicit_factory_inventory_required(self):
        mutations=[lambda p:p.pop('entity_factory'),lambda p:p.pop('formset_factories'),
            lambda p:p.update(entity_factory='base_entity'),lambda p:p.update(formset_factories=[]),
            lambda p:p['formset_factories'].append(copy.deepcopy(p['formset_factories'][0])),
            lambda p:p['formset_factories'][0].update(formset_kind='guess'),
            lambda p:p['formset_factories'][0].update(formset_id='NOT_PRESENT'),
            lambda p:p['formset_factories'][0].update(formset_kind='base_formset')]
        for mutate in mutations:
            req=request();mutate(req['profile'])
            with self.subTest(profile=req['profile']):
                with self.assertRaises(ValueError):binary_tax.inspect_request(req)

    def test_prior_profile_cannot_guess_new_envelopes(self):
        req=request();req['profile']['format']='tax-reborn-binary-entity-profile-v5'
        req['profile'].pop('entity_factory');req['profile'].pop('formset_factories')
        with self.assertRaises(ValueError):binary_tax.inspect_request(req)

    def test_unknown_each_scope_inspectable_but_relocation_refused(self):
        for name in (b'zccPersistentEntityUUID',b'zccPersistentFormSetUUID'):
            req=rename(request(),name);view,doc,buffers,bound=binary_tax._inspect(req)
            self.assertIn('untyped_persistent_object',[f['code'] for f in view['unresolved_facts']])
            self.assertTrue(all(not c['can_review'] for c in view['candidates']))
            with self.assertRaises(ValueError):edit(req)
            unchanged,_=binary_derived.store_and_read(doc,buffers,bound)
            self.assertEqual(unchanged,base64.b64decode(req['base64']))

    def test_known_legacy_length_and_metadata_version_cannot_be_malformed(self):
        for name,change in [(b'zccPersisUUID',lambda body:bytes([(body[0]+1)%256])+body[1:]),
                            (b'MetaDataKeyValueFormSetPO',lambda body:b'\0\3'+body[2:])]:
            req=request();raw=base64.b64decode(req['base64']);_,doc,_,_=binary_tax._inspect(req)
            records=doc.persistent_objects.objects if name==b'zccPersisUUID' else doc.formsets[0].persistent_attributes.objects
            obj=next(o for o in records if o.class_name==name)
            altered=obj.source_wire[:-len(obj.body)]+change(obj.body)
            req['base64']=base64.b64encode(raw.replace(obj.source_wire,altered,1)).decode()
            with self.subTest(name=name):
                with self.assertRaises(ValueError):binary_tax.inspect_request(req)

    def test_both_inventory_and_raw_body_changes_are_in_semantic_snapshot(self):
        _,doc,_,_=binary_tax._inspect(request());expected=document_semantic_snapshot(doc)
        objects=tuple((o.class_name,o.body) for o in doc.persistent_objects.objects)
        changed=replace(doc,persistent_objects=build_owned_objects(objects[::-1],base_position=doc.persistent_objects.source_base_position))
        self.assertNotEqual(expected,document_semantic_snapshot(changed))
        fs=doc.formsets[0];attrs=tuple((o.class_name,o.body) for o in fs.persistent_attributes.objects)
        changed=replace(doc,formsets=(replace(fs,persistent_attributes=build_owned_attributes(attrs[::-1],base_position=fs.persistent_attributes.source_base_position)),*doc.formsets[1:]))
        self.assertNotEqual(expected,document_semantic_snapshot(changed))

    def test_source_scope_prevents_object_reordering_or_edit(self):
        _,doc,buffers,bound=binary_tax._inspect(request())
        changed=replace(doc,persistent_objects=replace(doc.persistent_objects,objects=doc.persistent_objects.objects[::-1]))
        with self.assertRaises(ValueError):binary_derived.store_and_read(changed,buffers,bound)
        fs=doc.formsets[0];changed=replace(doc,formsets=(replace(fs,persistent_attributes=replace(fs.persistent_attributes,objects=fs.persistent_attributes.objects[::-1])),*doc.formsets[1:]))
        with self.assertRaises(ValueError):binary_derived.store_and_read(changed,buffers,bound)

    def test_complete_entity_end_is_required(self):
        for end in (b'',b'\xc1',b'\xc1\xc1\0'):
            req=request();raw=base64.b64decode(req['base64']);req['base64']=base64.b64encode(raw[:-2]+end).decode()
            with self.subTest(end=end):
                with self.assertRaises(ValueError):binary_tax.inspect_request(req)

if __name__=='__main__':unittest.main()
