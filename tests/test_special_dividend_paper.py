"""Actual public IRS2025 PDF serialization; distinct from calculation readiness."""
from copy import deepcopy
from pathlib import Path
import io,sys,unittest
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
from tests.test_special_dividends import CASES,prepared
import tax_engine,forms,official_forms
from pypdf import PdfReader

P2='topmostSubform[0].Page2[0].'

def record(profile='mixed',taxable=100000):
    case=next(c for c in CASES if c['profile']==profile and c['filing_status']=='single' and c['expected_1040_15']==taxable)
    data=prepared(case);data['w2'][0]['federal_withholding']='30000'
    data['identity'].update(first_name='Synthetic',last_name='Taxpayer',ssn='123456789',address='100 Example Street',city='Example City',state='IL',zip='60000',phone='5550100100',occupation='Accountant')
    data['filing_details'].update(digital_asset_answer='no',main_home_us_answer='yes')
    return {'data':data,'result':tax_engine.calculate_return(data),'form_facts':{'schedule_b':{'foreign_account':False,'fbar_required':False,'foreign_trust':False,'facts_confirmed':True}}}

class SpecialDividendPaperTests(unittest.TestCase):
    def test_actual_schedule_d_components_and_partiii_choices(self):
        for profile,collectible,unrecap in [('one_collectible',10000,0),('one_1250',0,10000),('mixed',10000,10000)]:
            with self.subTest(profile=profile):
                original=record(profile);packet=official_forms.build_official_packet(original)
                by={f['id']:f for f in packet['forms']};self.assertIn('f1040sd',by)
                sd=by['f1040sd'];self.assertEqual(sd['line_values']['18'],collectible);self.assertEqual(sd['line_values']['19'],unrecap)
                saved=PdfReader(io.BytesIO(sd['pdf_bytes'])).get_fields()
                self.assertEqual(str(saved[P2+'f2_2[0]']['/V']),str(collectible))
                self.assertEqual(str(saved[P2+'f2_3[0]']['/V']),str(unrecap))
                self.assertNotEqual(str(saved[P2+'c2_1[0]']['/V']),'/Off')
                self.assertEqual(str(saved[P2+'c2_1[1]']['/V']),'/Off')
                self.assertNotEqual(str(saved[P2+'c2_2[1]']['/V']),'/Off')
                self.assertEqual(str(saved[P2+'c2_2[0]']['/V']),'/Off')
                self.assertEqual(str(saved[P2+'c2_3[0]']['/V']),'/Off')
                self.assertEqual(str(saved[P2+'c2_3[1]']['/V']),'/Off')
                self.assertEqual(sd['unmapped_lines'],[])
    def test_real_packet_includes_official_d_and_full_tax_workpaper(self):
        original=record();before=deepcopy(original);status=forms.packet_status(original)
        self.assertTrue(status['calculation_ready']);self.assertTrue(status['paper_preparation_complete'],status['missing_facts'])
        self.assertEqual(status['status'],'ready_to_print_and_review')
        self.assertFalse(status['electronic_filing']);self.assertFalse(status['transmitted']);self.assertFalse(status['filing_packet_ready'])
        raw=forms.paper_packet_pdf(original);reader=PdfReader(io.BytesIO(raw));text='\n'.join(p.extract_text() for p in reader.pages)
        self.assertIn('SCHEDULE D TAX WORKSHEET',text);self.assertIn('Worksheet line 47: $',text)
        self.assertTrue(any(p.get('/TaxRebornForm')=='f1040sd' for p in reader.pages))
        f=reader.get_fields();self.assertEqual(str(f[P2+'f2_08[0]']['/V']),str(original['result']['lines']['16']))
        self.assertEqual(str(f['f1040sd_1.'+P2+'f2_2[0]']['/V']),'10000')
        self.assertEqual(str(f['f1040sd_1.'+P2+'f2_3[0]']['/V']),'10000')
        self.assertEqual(original,before)
    def test_missing_identity_keeps_paper_packet_incomplete(self):
        original=record();original['data']['identity']['ssn']='';original['result']=tax_engine.calculate_return(original['data'])
        self.assertTrue(original['result']['can_prepare'])
        status=forms.packet_status(original);self.assertFalse(status['paper_preparation_complete'])
        self.assertTrue(any('SSN' in item for item in status['missing_facts']))

if __name__=='__main__':unittest.main()
