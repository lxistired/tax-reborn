"""Preserving real derived table metadata without guessing a native factory."""
import base64
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import binary_tax
import create_binary_fixture as fixtures
import test_binary_tax_app as old
from interop.form_core.native_document_reference import load_document_bytes
from interop.form_core.value_table_header_reference import (
    TableHeader,load_table_header,store_table_header,
)

def request():
    return json.loads((ROOT/'fixtures/binary-tax/value-table-request.json').read_text())

class ValueTableBinary(unittest.TestCase):
    def test_factory_bound_derived_header_and_indexed_presence(self):
        result=binary_tax.inspect_request(request());forms=result['binary_archive']['forms']
        self.assertEqual((len(forms),forms[0]['children'],sum(len(f['links']) for f in forms)),(4,1,4))
        self.assertEqual(forms[0]['table_headers'],[dict(identifier='OWNED_ROWS',table_kind='value_table',first_field_ordinal=12,last_field_ordinal=12,saved_last_used_record_index=3)])
        rows=[f for f in forms[0]['fields'] if f['declared_array']]
        self.assertEqual([(f['element'],f['raw64'],f['specific_attributes']) for f in rows],[(1,'2500',3),(3,'0',3),(4,'99999',2)])
        self.assertTrue(all(not f['editable'] for f in rows))
        self.assertEqual(len(result['unresolved_facts']),2)
        self.assertTrue(all(not c['can_review'] for c in result['candidates']))

    def test_scalar_correction_retains_array_zero_unused_boundary_children_and_links(self):
        req=request();result=binary_tax.inspect_request(req)
        fsid,_,context,*_=fixtures.value_table_inputs()
        context=replace(context,current_table_ids={(fsid.encode(),copy):copy+10 for copy in range(1,5)})
        before=load_document_bytes(base64.b64decode(req['base64']),fixtures.buffers(),template_context=context)
        field=next(f for f in result['binary_archive']['forms'][0]['fields'] if f['field_id']=='WAGES')
        edited=binary_tax.edit_request(dict(inspection=req,expected_source_sha256=result['source_sha256'],confirmed=True,
            changes=[dict(path=[0,0],ordinal=field['ordinal'],element=0,value='1234.57')]))
        after=load_document_bytes(base64.b64decode(edited['base64']),fixtures.buffers(),template_context=context)
        old.BinaryTaxAppAcceptance().assert_retained_except(before,after,path=(0,0),ordinal=field['ordinal'],raw=123457)
        self.assertEqual(after.formsets[0].forms[0].tables[0].last_used_record_index,3)
        reread=binary_tax.inspect_request({**req,'base64':edited['base64']})
        self.assertEqual(reread['candidates'][0]['amounts']['wages'],'1234.57')
        self.assertFalse(edited['full_return_recalculated'])
        self.assertFalse(edited['original_program_acceptance_verified'])

    def test_factory_never_inferred_from_schema_or_trailing_length(self):
        for mode in ('missing','wrong','old_profile'):
            with self.subTest(mode=mode):
                req=request()
                if mode=='missing':req['profile']['table_factories']=[]
                elif mode=='wrong':req['profile']['table_factories'][0]['table_kind']='base_e1'
                else:
                    req['profile']['format']=binary_tax.EFFECTIVE_PROFILE
                    del req['profile']['table_factories']
                with self.assertRaises(ValueError):binary_tax.inspect_request(req)

    def test_array_elements_cannot_change_presence_through_scalar_editor(self):
        for element in (0,1,3,4,5):
            req=request();result=binary_tax.inspect_request(req)
            with self.subTest(element=element),self.assertRaisesRegex(ValueError,'duplicate, unused or unsupported'):
                binary_tax.edit_request(dict(inspection=req,expected_source_sha256=result['source_sha256'],confirmed=True,
                    changes=[dict(path=[0,0],ordinal=12,element=element,value='99.00')]))

    def test_factory_declarations_are_exact_unique_selected_templates(self):
        req=request();entry=req['profile']['table_factories'][0]
        for declarations in ([entry,entry],[{**entry,'form_id':'UNKNOWN'}],[{**entry,'table_kind':'auto'}],[{**entry,'extra':True}]):
            bad=deepcopy(req);bad['profile']['table_factories']=declarations
            with self.subTest(declarations=declarations),self.assertRaises(ValueError):binary_tax.inspect_request(bad)

    def test_helper_boundaries_and_legacy_store_are_explicit(self):
        record=TableHeader(b'OWNED_ARRAY',11,12,4)
        wire=store_table_header(record,entity_schema=18,table_kind='value_table')
        self.assertEqual(load_table_header(wire,entity_schema=18,table_kind='value_table'),record)
        for candidate in (wire[:-1],wire+b'\0'):
            with self.assertRaises(ValueError):load_table_header(candidate,entity_schema=18,table_kind='value_table')
        with self.assertRaises(ValueError):load_table_header(wire,entity_schema=18,table_kind='base_e1')
        legacy=load_table_header(wire[:-2],entity_schema=12,table_kind='value_table')
        self.assertEqual(legacy.last_used_record_index,0)
        with self.assertRaises(ValueError):store_table_header(legacy,entity_schema=12,table_kind='value_table')

if __name__=='__main__':unittest.main()
