"""Actual owned carriers -> current arrays -> full source-ID edit/readback."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import binary_tax
from create_auto_array_fixture import fixture
import create_derived_binary_fixture as manual
from create_binary_fixture import owned_xprf
from taxml_wire import read_xprf_resources

def replace_resource(request,index,key,value):
    result=deepcopy(request);carrier=result['carriers'][index]
    resources=read_xprf_resources(base64.b64decode(carrier['base64']),carrier['sha256'])
    if value is None:resources.pop(key,None)
    else:resources[key]=value
    blob=owned_xprf(resources);digest=hashlib.sha256(blob).hexdigest();old=carrier['sha256']
    carrier.update(base64=base64.b64encode(blob).decode(),sha256=digest)
    result['profile']['registry_order'][index]=digest
    for target in result['profile']['templates']:
        if target['carrier_sha256']==old:target['carrier_sha256']=digest
    return result

class AutoArrayBinaryTests(unittest.TestCase):
    def test_no_manual_arrays_and_cross_carrier_source_report(self):
        request=fixture();before=deepcopy(request);result=binary_tax.inspect_request(request)
        self.assertEqual(request,before);self.assertNotIn('compiled_arrays',request['profile'])
        self.assertTrue(all(c['can_review'] for c in result['candidates']))
        selected=next(t for t in result['registry_binding']['selected_array_templates'] if t['form_id']=='FW2')
        a,b=selected['blocks'];self.assertEqual((a['attribute_type'],b['attribute_type']),(2000,2001))
        self.assertEqual((a['resource_id'],b['resource_id']),(1,3))
        self.assertEqual((a['carrier_sha256'],b['carrier_sha256']),tuple(c['sha256'] for c in request['carriers']))
        self.assertEqual((a['records'][0]['byte27'],b['records'][0]['byte27']),(2,1))
        self.assertEqual((a['records'][0]['global_index'],b['records'][0]['global_index']),(1,2))
        self.assertEqual(a['records'][0]['source_metadata_hex'],'0c000c000a003102')
    def test_full_ID_edit_preserves_complete_document_and_array_report(self):
        request=fixture();before=binary_tax.inspect_request(request)
        result=binary_tax.edit_request(dict(inspection=request,expected_source_sha256=hashlib.sha256(base64.b64decode(request['base64'])).hexdigest(),changes=[dict(path=[0,0],field_id='WAGES',element=0,value='1234.57')],confirmed=True))
        after=binary_tax.inspect_request({**request,'base64':result['base64']})
        self.assertEqual(after['candidates'][0]['amounts']['wages'],'1234.57')
        self.assertEqual(hashlib.sha256(base64.b64decode(result['base64'])).hexdigest(),'179560f55862259878bdb45f8efe076e25c841d4425055618a579a2befa58b25')
        self.assertEqual(before['registry_binding'],after['registry_binding'])
        for old,new in zip(before['binary_archive']['forms'],after['binary_archive']['forms']):
            self.assertEqual(old['derived']['sha256'],new['derived']['sha256'])
            self.assertEqual(new['derived']['source_position'],old['derived']['source_position']+2)
            self.assertEqual(old['table_headers'],new['table_headers']);self.assertEqual(old['links'],new['links'])
    def test_reviewed_box_export_uses_full_source_ID(self):
        request=fixture();candidate=binary_tax.inspect_request(request)['candidates'][0]
        amounts={name:candidate['amounts'][name] for name in binary_tax.prep.BOX_KEYS.values()}
        amounts['wages']='1234.57'
        output=binary_tax.export_request(dict(inspection=request,expected_candidate_sha256=candidate['receipt']['candidate_sha256'],amounts=amounts,confirmed=True))
        self.assertEqual(hashlib.sha256(base64.b64decode(output['base64'])).hexdigest(),'179560f55862259878bdb45f8efe076e25c841d4425055618a579a2befa58b25')
    def test_actual_prepared_fields_use_current_not_source_ordinal(self):
        doc,buffers,bound,registry,selected,source=binary_tax._context(fixture())
        arrays=bound.arrays[next(key for key in bound.arrays if key[1]==b'FW2')]
        self.assertEqual((arrays[0][0].first_field,arrays[1][0].first_field),(12,12))
        mapping=next(v for v in bound.bindings[(0,0)] if v.field_id==b'OWNED_AMOUNT'.ljust(32,b' '))
        self.assertEqual((mapping.source_field_index,mapping.current_field_index,mapping.array_index),(112,12,1))
    def test_used_array_blocks_income_but_scalar_edit_preserves_rows(self):
        request=fixture(used_array=True);result=binary_tax.inspect_request(request)
        self.assertTrue(all(not c['can_review'] for c in result['candidates']))
        corrected=binary_tax.edit_request(dict(inspection=request,expected_source_sha256=hashlib.sha256(base64.b64decode(request['base64'])).hexdigest(),changes=[dict(path=[0,0],field_id='WAGES',element=0,value='1234.57')],confirmed=True))
        reread=binary_tax.inspect_request({**request,'base64':corrected['base64']})
        old=[f for f in result['binary_archive']['forms'][0]['fields'] if f['element']]
        new=[f for f in reread['binary_archive']['forms'][0]['fields'] if f['element']]
        self.assertEqual(old,new)
    def test_opaque_objects_still_cannot_move(self):
        request=fixture(opaque=True)
        with self.assertRaises(ValueError):binary_tax.edit_request(dict(inspection=request,expected_source_sha256=hashlib.sha256(base64.b64decode(request['base64'])).hexdigest(),changes=[dict(path=[0,0],field_id='WAGES',element=0,value='1234.57')],confirmed=True))
    def test_present_empty_and_truncated_and_trailing_payload_refused(self):
        request=fixture()
        for payload in (b'',b'\x01\0',b'\0\0TRAIL'):
            with self.subTest(payload=payload),self.assertRaises(ValueError):binary_tax.inspect_request(replace_resource(request,0,(2000,1),payload))
    def test_missing_array_for_retained_indexed_source_is_refused(self):
        request=replace_resource(fixture(),0,(2000,1),None)
        request=replace_resource(request,1,(2001,3),None)
        with self.assertRaises(ValueError):binary_tax.inspect_request(request)
    def test_manual_array_override_not_accepted_in_v5(self):
        request=fixture();request['profile']['compiled_arrays']=[]
        with self.assertRaises(ValueError):binary_tax.inspect_request(request)
    def test_selected_form_and_primary_and_carrier_order_mismatches_refused(self):
        for mutation in ('form','primary','order'):
            request=fixture()
            if mutation=='form':request['profile']['templates'][0]['form_id']='F1099D'
            elif mutation=='primary':request['profile']['templates'][0]['resource_id']=3
            else:request['profile']['registry_order'].reverse()
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):binary_tax.inspect_request(request)
    def test_v4_manual_contract_remains_and_missing_manual_lists_refused(self):
        request=manual.fixture();self.assertTrue(binary_tax.inspect_request(request)['candidates'][0]['can_review'])
        request['profile'].pop('compiled_arrays')
        with self.assertRaises(ValueError):binary_tax.inspect_request(request)
    def test_full_hash_integrity_still_required(self):
        for mode in ('null','wrong_bucket','out_of_range'):
            with self.subTest(mode=mode),self.assertRaisesRegex(ValueError,'Source hash'):
                binary_tax.inspect_request(fixture(hash_mode=mode))
    def test_source_tail_mismatch_not_relaxed(self):
        request=fixture();doc,*_=binary_tax._context(request)
        source=bytearray(base64.b64decode(request['base64']))
        source[doc.formsets[0].forms[0].derived_tail.source_base_position]^=1
        request['base64']=base64.b64encode(source).decode()
        with self.assertRaises(ValueError):binary_tax.inspect_request(request)

if __name__=='__main__':unittest.main()
