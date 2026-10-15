"""Actual App stream migration with independently authored ordered registries."""
import base64
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'web'),str(ROOT/'scripts')]
import binary_tax
import create_binary_fixture as fixtures
import taxml_wire as wire
import tax_engine
import test_binary_tax_app as old_acceptance
from interop.form_core.native_document_reference import load_document_bytes

def request(name='merged'):
    return json.loads((ROOT/'fixtures/binary-tax'/f'{name}-request.json').read_text())

def change_carrier(req,index,change):
    item=req['carriers'][index];previous=item['sha256']
    records=wire.read_xprf_resources(base64.b64decode(item['base64']),previous)
    change(records);blob=fixtures.owned_xprf(records);sha=wire.digest(blob)
    req['carriers'][index]={'base64':base64.b64encode(blob).decode(),'sha256':sha}
    req['profile']['registry_order'][index]=sha
    for selected in req['profile']['templates']:
        if selected['carrier_sha256']==previous:selected['carrier_sha256']=sha

class EffectiveBinaryRegistry(unittest.TestCase):
    def test_actual_income_boxes_and_split_source_ordinals(self):
        req=request();before=deepcopy(req);result=binary_tax.inspect_request(req)
        self.assertEqual(req,before)
        self.assertFalse(result['unresolved_facts'])
        self.assertTrue(all(c['can_review'] for c in result['candidates']))
        self.assertEqual([c['record_type'] for c in result['candidates']],['w2','interest','dividends'])
        w2=result['candidates'][0]
        self.assertEqual(w2['amounts']['wages'],'1234.56')
        self.assertEqual(w2['amounts']['federal_withholding'],'123.00')
        report=result['registry_binding'];self.assertEqual(report['registry_order'],req['profile']['registry_order'])
        selected=next(x for x in report['selected_templates'] if x['form_id']=='FW2')
        fields={f['field_id']:f for f in selected['fields']}
        self.assertEqual((fields['WAGES']['ordinal'],fields['WAGES']['source_resource_type'],fields['WAGES']['source_carrier_sha256']),(4,1900,req['carriers'][0]['sha256']))
        self.assertEqual((fields['FEDTAX']['ordinal'],fields['FEDTAX']['source_dictionary_ordinal'],fields['FEDTAX']['source_resource_type'],fields['FEDTAX']['source_carrier_sha256']),(5,1,1901,req['carriers'][1]['sha256']))
        self.assertEqual(selected['primary']['carrier_sha256'],req['carriers'][1]['sha256'])
        self.assertFalse(report['native_current_registry_verified'])
        self.assertFalse(report['checksum_inferred_from_wire'])

    def test_version_replacement_and_repeated_home_membership_are_retained(self):
        req=request();report=binary_tax.inspect_request(req)['registry_binding']
        fs,=report['membership'];forms={f['form_id']:f for f in fs['forms']}
        self.assertEqual(forms['OWNED_UNUSED']['selection_version'],2)
        homes=forms['FW2']['homes'];alpha,beta=req['profile']['registry_order']
        self.assertEqual([(h['carrier_sha256'],h['resource_id'],h['metadata_type']) for h in homes],[(beta,1,18000),(alpha,1,18000),(beta,1,18001)])

    def test_order_duplicate_and_false_primary_are_refused(self):
        req=request();bad=deepcopy(req);bad['carriers'].reverse()
        with self.assertRaisesRegex(ValueError,'ordered registry'):binary_tax.inspect_request(bad)
        bad=deepcopy(req);bad['carriers'][1]=bad['carriers'][0]
        with self.assertRaisesRegex(ValueError,'Duplicate registry'):binary_tax.inspect_request(bad)
        bad=deepcopy(req);bad['profile']['templates'][0]['carrier_sha256']=req['carriers'][0]['sha256']
        with self.assertRaisesRegex(ValueError,'primary SHA/RID'):binary_tax.inspect_request(bad)

    def test_missing_and_changed_carrier_bytes_are_refused(self):
        req=request();bad=deepcopy(req);bad['carriers'].pop()
        with self.assertRaises(ValueError):binary_tax.inspect_request(bad)
        bad=deepcopy(req);blob=bytearray(base64.b64decode(bad['carriers'][0]['base64']));blob[-1]^=1;bad['carriers'][0]['base64']=base64.b64encode(blob).decode()
        with self.assertRaisesRegex(ValueError,'carrier_identity_mismatch'):binary_tax.inspect_request(bad)

    def test_present_empty_attribute_cannot_fall_through(self):
        req=request();change_carrier(req,1,lambda resources:resources.update({(1900,1):b''}))
        with self.assertRaisesRegex(ValueError,'zero-length present'):binary_tax.inspect_request(req)

    def test_duplicate_field_ids_between_selected_blocks_are_refused(self):
        req=request()
        def duplicate(resources):
            payload=bytearray(resources[1901,1]);payload[3:35]=b'WAGES'.ljust(32,b' ');resources[1901,1]=bytes(payload)
        change_carrier(req,1,duplicate)
        with self.assertRaisesRegex(ValueError,'ambiguous or unsupported context ID'):binary_tax.inspect_request(req)

    def test_merged_nested_edit_retains_every_other_parsed_fact(self):
        req=request('merged-nested');result=binary_tax.inspect_request(req)
        fsid,_,context,*_=fixtures.merged_registry_inputs()
        # Runtime StringTableIDs are independently allocated. Decode both
        # files against one explicit current registry before comparing facts.
        context=replace(context,current_table_ids={(fsid.encode(),copy):copy+10 for copy in range(1,5)})
        before=load_document_bytes(base64.b64decode(req['base64']),fixtures.buffers(),template_context=context)
        field=next(f for f in result['binary_archive']['forms'][0]['fields'] if f['field_id']=='WAGES')
        edited=binary_tax.edit_request(dict(inspection=req,expected_source_sha256=result['source_sha256'],confirmed=True,
            changes=[dict(path=[0,0],ordinal=field['ordinal'],element=0,value='1234.57')]))
        after=load_document_bytes(base64.b64decode(edited['base64']),fixtures.buffers(),template_context=context)
        old_acceptance.BinaryTaxAppAcceptance().assert_retained_except(before,after,path=(0,0),ordinal=field['ordinal'],raw=123457)
        reread=binary_tax.inspect_request({**req,'base64':edited['base64']})
        self.assertEqual(reread['candidates'][0]['amounts']['wages'],'1234.57')
        forms=reread['binary_archive']['forms']
        self.assertEqual((len(forms),forms[0]['tables'],forms[0]['children'],sum(len(f['links']) for f in forms)),(4,1,1,4))
        self.assertTrue(all(link['resolved'] for form in forms for link in form['links']))
        self.assertFalse(edited['full_return_recalculated'])
        self.assertFalse(edited['original_program_acceptance_verified'])

    def test_reviewed_owned_amounts_reach_existing_IRS_calculation(self):
        result=binary_tax.inspect_request(request());data=tax_engine.default_return()
        for c in result['candidates']:
            values=c['amounts'];kind=c['record_type']
            if kind=='w2':row=dict(tax_engine.ROW_DEFAULTS[kind],**values,employer='Synthetic employer',owner='taxpayer')
            elif kind=='interest':row=dict(tax_engine.ROW_DEFAULTS[kind],payer='Synthetic bank',taxable=str(Decimal(values['interest_income'])+Decimal(values['treasury_interest'])),tax_exempt=values['tax_exempt_interest'],federal_withholding=values['federal_withholding'])
            else:row=dict(tax_engine.ROW_DEFAULTS[kind],**values,payer='Synthetic fund',special_distribution_confirmed=True)
            data[kind].append(row)
        output=tax_engine.calculate_return(data)
        self.assertEqual(output['summary']['refund'],344)
        self.assertFalse(output['can_prepare'])
        self.assertFalse(result['full_return_imported'])

if __name__=='__main__':unittest.main()
