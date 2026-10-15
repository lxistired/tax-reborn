"""Complete owned archives: Entity14D stored bytes, never a current native map."""
import base64,copy,json,struct,sys,unittest
from dataclasses import replace
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import binary_tax,create_entity_instance_map_fixture as fixture
from interop.form_core import entity_stored_instance_map_reference as unified
from interop.form_core import legacy_instance_map_entity_body_reference as legacy
from interop.form_core import instance_map_entity_body_reference as compressed
from interop.derived_form.entity_objects_reference import build_owned_objects,preserve_objects,load_objects,typed_body
from interop.derived_form.formset_attributes_reference import typed_body as formset_typed

def request(version):return json.loads((ROOT/f'fixtures/binary-tax/entity-instance-map-v{version}-income-request.json').read_text())
def entity_map(view):return next(o for o in view['binary_archive']['persistent_objects']['entity']['objects'] if o['class_name']==unified.NAME.decode())
def change(req):
    view=binary_tax.inspect_request(req)
    return binary_tax.edit_request(dict(inspection=req,expected_source_sha256=view['source_sha256'],changes=[dict(path=[0,0],field_id='WAGES',element=0,value='1234.57')],confirmed=True))
def mutate_body(req,fn):
    doc,*_=binary_tax._context(req);body=next(o.body for o in doc.persistent_objects.objects if o.class_name==unified.NAME)
    raw=base64.b64decode(req['base64']);assert raw.count(body)==1
    altered=fn(body);assert len(altered)==len(body)
    return {**req,'base64':base64.b64encode(raw.replace(body,altered,1)).decode()}

class EntityInstanceMapTests(unittest.TestCase):
    def test_three_owned_versions_complete_and_reproducible(self):
        for version,rows in ((1,2),(2,3),(3,0)):
            req=request(version);self.assertEqual(req,fixture.fixture(version));view=binary_tax.inspect_request(req)
            self.assertFalse(view['unresolved_facts']);self.assertTrue(all(c['can_review'] for c in view['candidates']))
            self.assertEqual(len(view['binary_archive']['forms']),8)
            obj=entity_map(view);self.assertEqual(obj['class_id'],0x14d);self.assertEqual(obj['version'],version);self.assertEqual(len(obj['rows']),rows)
            self.assertTrue(obj['relocatable']);self.assertEqual(obj['stored_no_payload'],version==3)
            for flag in ('native_Load_executed','native_SetValue_executed','native_cleanup_executed','native_14F_transfer_executed','native_current_cache_verified','native_inventory_verified','active_native_cache_empty_verified','row_editing_supported','active_native_value'):self.assertFalse(obj[flag])
            if version==3:self.assertEqual(obj['source_format'],'version3-stored-no-payload')

    def test_each_version_whole_edit_retains_all_layers_and_owner(self):
        for version in (1,2,3):
            req=request(version);kept=copy.deepcopy(req);old,*_=binary_tax._context(req);before=binary_tax.inspect_request(req);out=change(req)
            self.assertEqual(req,kept);self.assertTrue(out['binary_roundtrip_verified']);self.assertTrue(out['all_other_parsed_facts_preserved'])
            self.assertFalse(out['original_program_acceptance_verified']);self.assertFalse(out['full_return_recalculated'])
            after_req={**req,'base64':out['base64']};new,*_=binary_tax._context(after_req);after=binary_tax.inspect_request(after_req)
            self.assertEqual(old.persistent_objects.source_wire,new.persistent_objects.source_wire)
            self.assertEqual(old.header,new.header)
            for a,b in zip(old.formsets,new.formsets):
                self.assertEqual(a.header,b.header);self.assertEqual(a.persistent_attributes.source_wire,b.persistent_attributes.source_wire)
            self.assertEqual(len(after['binary_archive']['forms']),8);self.assertEqual(sum(len(f['links'])for f in after['binary_archive']['forms']),8)
            self.assertEqual(entity_map(before)['rows'],entity_map(after)['rows'])
            self.assertEqual(next(f for f in after['binary_archive']['forms'][0]['fields'] if f['field_id']=='WAGES')['text'],'1234.57')
            for a,b in zip(before['binary_archive']['forms'][1:],after['binary_archive']['forms'][1:]):self.assertEqual(a['fields'],b['fields'])

    def test_public_correction_and_source_document_scope_reject_owner_or_body_replacement(self):
        from interop.derived_form.source_bound_value_document_reference import store_document_bytes
        req=request(2);doc,buffers,bound,*_=binary_tax._context(req);view=binary_tax.inspect_request(req)
        cases=[replace(doc,entity_header=replace(doc.entity_header,serial=doc.entity_header.serial+1)),
               replace(doc,persistent_objects=build_owned_objects(((unified.NAME,b"\x00\x03"),),base_position=doc.persistent_objects.source_base_position)),
               replace(doc,formsets=tuple(reversed(doc.formsets)))]
        for altered in cases:
            with self.assertRaisesRegex(ValueError,'Source-derived document permits scalar correction only'):
                store_document_bytes(altered,buffers,template_context=bound.context)
        for extra in ({'owner':'different Entity'},{'body_hex':'0003'},{'class_name':'TpsInstanceToMefInstanceMapPO'}):
            with self.assertRaises(ValueError):binary_tax.edit_request(dict(inspection=req,expected_source_sha256=view['source_sha256'],changes=[dict(path=[0,0],field_id='WAGES',element=0,value='1234.57',**extra)],confirmed=True))
        # A different valid source body is a new source, never accepted under
        # the original source receipt even when its total length is unchanged.
        legacy_req=request(1);legacy_view=binary_tax.inspect_request(legacy_req)
        changed=mutate_body(legacy_req,lambda body:body.replace(b'OWNED/TPS/v1/A',b'OWNED/TPS/v1/Z'))
        binary_tax.inspect_request(changed)
        with self.assertRaises(ValueError):binary_tax.edit_request(dict(inspection=changed,expected_source_sha256=legacy_view['source_sha256'],changes=[dict(path=[0,0],field_id='WAGES',element=0,value='1234.57')],confirmed=True))

    def test_complete_source_wrong_formset_scope_blocks_correction(self):
        from interop.derived_form.source_bound_value_document_reference import store_document_bytes
        from interop.derived_form.formset_attributes_reference import build_owned_attributes
        req=request(2);doc,buffers,bound,*_=binary_tax._context(req)
        body=next(o.body for o in doc.persistent_objects.objects if o.class_name==unified.NAME)
        fs=doc.formsets[0];old=fs.persistent_attributes
        records=tuple((o.class_name,o.body)for o in old.objects)+((unified.NAME,body),)
        attrs=build_owned_attributes(records,base_position=old.source_base_position)
        own=replace(doc,formsets=(replace(fs,persistent_attributes=attrs),)+doc.formsets[1:],metadata={},source_bytes=None)
        raw=store_document_bytes(own,buffers,template_context=bound.context)
        wrong={**req,'base64':base64.b64encode(raw).decode()};view=binary_tax.inspect_request(wrong)
        obj=next(o for o in view['binary_archive']['persistent_objects']['formsets'][0]['persistent_attributes']['objects']if o['class_name']==unified.NAME.decode())
        self.assertEqual(obj['kind'],'opaque');self.assertFalse(obj['relocatable']);self.assertTrue(view['unresolved_facts'])
        with self.assertRaises(ValueError):change(wrong)

    def test_reviewed_income_export_equals_exact_whole_correction(self):
        for version in (1,2,3):
            req=request(version);before=binary_tax.inspect_request(req);candidate=before['candidates'][0]
            amounts={key:candidate['amounts'][key]for key in binary_tax.prep.BOX_KEYS.values()};amounts['wages']='1234.57'
            output=binary_tax.export_request(dict(inspection=req,expected_candidate_sha256=candidate['receipt']['candidate_sha256'],amounts=amounts,confirmed=True))
            self.assertEqual(output['base64'],change(req)['base64'])

    def test_source_body_only_and_exact_same_entity_owner(self):
        for version in (1,2,3):
            doc,*_=binary_tax._context(request(version));body=next(o.body for o in doc.persistent_objects.objects if o.class_name==unified.NAME)
            parsed=unified.load_entity_body(body);self.assertEqual(unified.preserve_entity_body(parsed),body)
            evidence=unified.relocation_evidence(unified.NAME,body,owner_level='entity',source_owner_key=b'owned/source/entity/1',target_owner_key=b'owned/source/entity/1')
            self.assertFalse(evidence['owner_reassignment_allowed']);self.assertFalse(evidence['native_current_cache_verified'])
            with self.assertRaises(ValueError):unified.relocation_evidence(unified.NAME,body,owner_level='entity',source_owner_key=b'owned/source/entity/1',target_owner_key=b'owned/source/entity/2')
            with self.assertRaises(ValueError):unified.preserve_entity_body(replace(parsed,source_format='forged'))

    def test_wrong_formset_record_value_scope_never_grants_type(self):
        # The public classifiers are deliberately scope-specific; no global
        # class-name allowlist grants permission to another persistent layer.
        for version in (1,2,3):
            doc,*_=binary_tax._context(request(version));body=next(o.body for o in doc.persistent_objects.objects if o.class_name==unified.NAME)
            self.assertIsNone(formset_typed(unified.NAME,body))
            for owner in ('formset','record','value'):
                with self.assertRaises(ValueError):unified.load_named_entity_body(unified.NAME,body,owner_level=owner)
            self.assertIsNone(typed_body(unified.NAME.lower(),body))

    def test_unknown_version_and_compressed_count_zero_opaque(self):
        req=request(2)
        for mutation in (lambda b:b'\0\4'+b[2:],lambda b:b[:2]+b'\0\0\0\0'+b[6:]):
            bad=mutate_body(req,mutation);view=binary_tax.inspect_request(bad);obj=entity_map(view)
            self.assertEqual(obj['kind'],'opaque');self.assertFalse(obj['relocatable']);self.assertTrue(view['unresolved_facts'])
            self.assertTrue(all(not c['can_review'] for c in view['candidates']))
            with self.assertRaises(ValueError):change(bad)

    def test_known_last_instance_malformed_refused_not_opaque(self):
        for version in (1,2):
            req=request(version)
            with self.assertRaises(ValueError):binary_tax.inspect_request(mutate_body(req,lambda b:b[:-1]+bytes([b[-1]^0x7f])))
            doc,*_=binary_tax._context(req);body=next(o.body for o in doc.persistent_objects.objects if o.class_name==unified.NAME)
            with self.assertRaises(ValueError):build_owned_objects(((unified.NAME,body),(unified.NAME,body+b'x')))
        for bad in (b'\0\3x',b'\0\3\0\0\0\0'):
            with self.assertRaises(ValueError):typed_body(unified.NAME,bad)

    def test_each_object_must_validate_before_relocation(self):
        body=legacy.encode_owned_legacy_body((legacy.StoredPair(b'A',b'B'),))
        for opaque in (b'\x00\x09anything',struct.pack('>HI',2,0)):
            objs=build_owned_objects(((unified.NAME,body),(unified.NAME,opaque)),base_position=100)
            self.assertEqual(preserve_objects(objs,base_position=100),objs.source_wire)
            with self.assertRaises(ValueError):preserve_objects(objs,base_position=101)
        objs=build_owned_objects(((unified.NAME,body),),base_position=100)
        moved=load_objects(preserve_objects(objs,base_position=333),base_position=333)
        self.assertEqual(moved.objects[0].body,body)
        with self.assertRaises(ValueError):preserve_objects(replace(objs,capacity=objs.capacity+1),base_position=333)

    def test_legacy_empty_and_raw_non_unicode_are_preserved(self):
        for rows in ((),(legacy.StoredPair(b'',b''),),(legacy.StoredPair(b'\xff\t\nA',b'\xfeB\n\t'),)):
            wire=legacy.encode_owned_legacy_body(rows);parsed=unified.load_entity_body(wire)
            self.assertEqual(unified.preserve_entity_body(parsed),wire);self.assertEqual(len(parsed.rows),len(rows))
        self.assertEqual(unified.load_entity_body(struct.pack('>HI',1,0)).source_format,'version1-length-framed')
        self.assertEqual(unified.load_entity_body(b'\0\3').rows,())
        self.assertIsNone(unified.typed_entity_body_or_none(struct.pack('>HI',2,0)))

if __name__=='__main__':unittest.main()
