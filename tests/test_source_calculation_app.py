"""Source/current-return pairing, monetary basis and write isolation boundaries."""
from pathlib import Path
import copy,json,sys,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'web'))
import source_calculation_command as comparison

class SourceCalculationApp(unittest.TestCase):
    def payload(self):
        request=json.loads((ROOT/'web/samples/source-calculation-demo-request.json').read_text())
        data=json.loads((ROOT/'web/samples/current-App-demo-return.json').read_text())
        return dict(request=request,expected_source_profile_sha256=comparison.binary_tax.prep.canonical_hash(request['source']['profile']),
                    current_app_return=data,expected_current_app_return_sha256=comparison.current_app_snapshot(data)['current_return_sha256'],comparison_acknowledged=True)

    def test_exact_tax_payment_and_signed_balance_and_no_mutation(self):
        payload=self.payload();before=copy.deepcopy(payload);out=comparison.compare_source(payload);c=out['comparison']
        self.assertEqual((c['source_total_tax'],c['source_payments'],c['source_signed_balance']),('1279','100','1179'))
        self.assertEqual((c['current_app_summary']['total_tax'],c['current_app_summary']['payments'],c['current_app_signed_balance']),('0','100','-100'))
        self.assertEqual((c['total_tax_difference'],c['payments_difference'],c['signed_balance_difference']),('1279','0','1279'))
        self.assertTrue(c['source_refund_not_calculated']);self.assertFalse(out['writeback_allowed']);self.assertEqual(payload,before)

    def test_full_input_and_review_pair_are_required_for_differences(self):
        for changes in ({'comparison_acknowledged':False},{'comparison_acknowledged':1},{'expected_current_app_return_sha256':'0'*64}):
            p=self.payload();p.update(changes)
            with self.assertRaises(ValueError):comparison.compare_source(p)
        p=self.payload();p['current_app_return']['w2'][0]['wages']='20000.49'
        with self.assertRaises(ValueError):comparison.compare_source(p)
        p=self.payload();p['current_app_return']={'total_tax':0}
        with self.assertRaises(ValueError):comparison.compare_source(p)

    def test_no_full_current_return_means_source_only(self):
        p=self.payload();p.update(current_app_return=None,expected_current_app_return_sha256=None,comparison_acknowledged=False)
        c=comparison.compare_source(p)['comparison'];self.assertEqual(c['current_app_summary'],{});self.assertIsNone(c['signed_balance_difference'])

    def test_source_identity_profile_and_authority_tamper_refused(self):
        for target in ('source_sha','profile','authority','resource','intermediate'):
            p=self.payload();r=p['request']
            if target=='source_sha':r['expected_source_sha256']='0'*64
            elif target=='profile':r['source']['profile']['template_versions']['OWNEDTOY']=2
            elif target=='authority':r['source_profile_id']='uploaded-authority'
            elif target=='resource':r['calculation_carriers'][0]['sha256']='0'*64
            else:r['reviewed_context']['fields'].append({'form_id':'F1040','field_id':'L39','amount':'0','reason':'unverified intermediate'})
            with self.assertRaises(ValueError):comparison.compare_source(p)

    def test_blank_payment_is_not_a_missing_payment_confirmation(self):
        p=self.payload();p['request']['reviewed_context']['fields']=[r for r in p['request']['reviewed_context']['fields'] if r['field_id']!='L58']
        with self.assertRaises(ValueError):comparison.compare_source(p)

    def test_overpayment_balance_does_not_claim_source_refund_execution(self):
        p=self.payload();next(r for r in p['request']['reviewed_context']['fields'] if r['field_id']=='L58')['amount']='2000'
        p['current_app_return']['w2'][0]['federal_withholding']='2000'
        p['expected_current_app_return_sha256']=comparison.current_app_snapshot(p['current_app_return'])['current_return_sha256']
        c=comparison.compare_source(p)['comparison'];self.assertEqual((c['source_signed_balance'],c['current_app_signed_balance']),('-721','-2000'));self.assertTrue(c['source_refund_not_calculated'])

    def test_v5_uses_the_same_full_saved_field_identity(self):
        p=self.payload();r=p['request'];profile=r['source']['profile'];profile['format']='tax-reborn-binary-entity-profile-v5';profile.pop('compiled_arrays')
        p['expected_source_profile_sha256']=comparison.binary_tax.prep.canonical_hash(profile)
        out=comparison.compare_source(p);wage=next(v for v in out['source_calculation']['source_field_trace'] if v['field']=='WAGES')
        self.assertEqual((wage['source_ordinal'],wage['current_ordinal']),(104,2));self.assertEqual(out['comparison']['source_total_tax'],'1279')
        profile['compiled_arrays']=[];p['expected_source_profile_sha256']=comparison.binary_tax.prep.canonical_hash(profile)
        with self.assertRaises(ValueError):comparison.compare_source(p)

    def test_v6_stored_metadata_never_supplies_active_calculation_values(self):
        from dataclasses import replace
        import base64,hashlib
        from interop.derived_form.source_bound_value_document_reference import store_document_bytes
        from interop.derived_form.formset_attributes_reference import build_owned_attributes
        from interop.derived_form.entity_objects_reference import build_owned_objects
        from interop.derived_form.metadata_entity_body_reference import NAME as ENTITY_NAME,encode_owned_metadata_entity_body
        from interop.form_core.metadata_formset_body_reference import NAME as FS_NAME,Row,encode_owned_metadata_body
        p=self.payload();r=p['request'];source=r['source'];doc,buffers,bound,_,_,_=comparison.binary_tax._context(source)
        rows=(Row(b'F1040/L39',b'999999999999'),)
        sets=tuple(replace(fs,persistent_attributes=build_owned_attributes(((FS_NAME,encode_owned_metadata_body(rows)),))) for fs in doc.formsets)
        doc=replace(doc,formsets=sets,persistent_objects=build_owned_objects(((ENTITY_NAME,encode_owned_metadata_entity_body(rows)),)),metadata={},source_bytes=None)
        context=replace(bound.context,entity_factory='value_entity',default_formset_factory=None,
            formset_factories={fs.header.identifier:'value_formset' for fs in sets})
        raw=store_document_bytes(doc,buffers,template_context=context);source['base64']=base64.b64encode(raw).decode()
        profile=source['profile'];profile.pop('compiled_arrays');profile.update(format='tax-reborn-binary-entity-profile-v6',
            entity_factory='value_entity',formset_factories=[dict(formset_id=fs.header.identifier.decode(),formset_kind='value_formset') for fs in sets])
        r['expected_source_sha256']=hashlib.sha256(raw).hexdigest();r['reviewed_context']['source_sha256']=r['expected_source_sha256'];p['expected_source_profile_sha256']=comparison.binary_tax.prep.canonical_hash(profile)
        before=copy.deepcopy(p);out=comparison.compare_source(p)
        self.assertEqual(out['comparison']['source_total_tax'],'1279');self.assertFalse(out['writeback_allowed']);self.assertEqual(p,before)
        wage=next(v for v in out['source_calculation']['source_field_trace'] if v['field']=='WAGES')
        self.assertEqual((wage['source_ordinal'],wage['current_ordinal']),(104,2))

if __name__=='__main__':unittest.main()
