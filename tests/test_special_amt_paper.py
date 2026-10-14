"""Read back serialized public IRS6251 pages and the combined paper packet."""
from pathlib import Path
import io,sys,unittest
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'tests'))
from test_special_amt import CASES,return_for
import tax_engine,forms,official_forms
from pypdf import PdfReader

def record(case):
    data=return_for(case)
    data['identity'].update(first_name='Synthetic',last_name='Taxpayer',ssn='123456789',address='100 Example Street',city='Example City',state='IL',zip='60000',phone='5550100100',occupation='Accountant')
    data['filing_details'].update(digital_asset_answer='no',main_home_us_answer='yes',balance_due_payment_method='electronic')
    return {'data':data,'result':tax_engine.calculate_return(data),
        'form_facts':{'schedule_b':{'foreign_account':False,'fbar_required':False,'foreign_trust':False,'facts_confirmed':True}}}

class SpecialAMTPaperTests(unittest.TestCase):
    def test_actual_6251_positive_AMT_all29_partIII_fields(self):
        cases=[next(c for c in CASES if c['filing_status']=='single' and c['expected']['AMT']>0 and c['dividends'][0]['unrecaptured_1250_gain']=='10000' and c['dividends'][0]['collectibles_gain']=='0'),
               next(c for c in CASES if c['filing_status']=='mfj' and c['expected']['AMT']>0 and c['dividends'][0]['collectibles_gain']=='10000')]
        for case in cases:
            with self.subTest(id=case['id']):
                original=record(case);packet=official_forms.build_official_packet(original)
                by={f['id']:f for f in packet['forms']}
                self.assertIn('f6251',by);self.assertIn('f1040s2',by)
                amt=by['f6251'];self.assertEqual(amt['unmapped_lines'],[])
                fields=PdfReader(io.BytesIO(amt['pdf_bytes'])).get_fields()
                self.assertEqual(len(PdfReader(io.BytesIO(amt['pdf_bytes'])).pages),2)
                mapping=official_forms.MAP['f6251']['line_fields']
                for line,value in case['expected_partIII'].items():
                    self.assertEqual(str(fields[mapping[line]]['/V']),str(value),'saved6251 line'+line)
                for line,value in [('9',case['expected']['tentative_minimum_tax']),('10',case['expected']['regular_tax']),('11',case['expected']['AMT'])]:
                    self.assertEqual(str(fields[mapping[line]]['/V']),str(value))
                self.assertEqual(by['f1040s2']['line_values']['2'],case['expected']['AMT'])

    def test_real_positive_AMT_packet_and_printed_workpaper(self):
        case=next(c for c in CASES if c['filing_status']=='single' and c['expected']['AMT']>0 and c['dividends'][0]['unrecaptured_1250_gain']=='10000')
        original=record(case);status=forms.packet_status(original)
        self.assertTrue(status['calculation_ready'])
        self.assertTrue(status['paper_preparation_complete'],status['missing_facts'])
        self.assertFalse(status['electronic_filing']);self.assertFalse(status['transmitted'])
        raw=forms.paper_packet_pdf(original);reader=PdfReader(io.BytesIO(raw))
        self.assertEqual(sum(p.get('/TaxRebornForm')=='f6251' for p in reader.pages),2)
        text='\n'.join(p.extract_text() for p in reader.pages)
        self.assertIn('FORM6251 PARTIII',text)
        self.assertIn('Form6251 line 40: $',text)
        self.assertIn('AMT liability: $',text)
        fields=reader.get_fields()
        self.assertEqual(str(fields['topmostSubform[0].Page2[0].f2_09[0]']['/V']),str(case['expected']['AMT']))

    def test_zero_AMT_MFS_packet_retains_actual_full6251(self):
        original=record(CASES[-2]);packet=official_forms.build_official_packet(original)
        amt=next(f for f in packet['forms'] if f['id']=='f6251')
        fields=PdfReader(io.BytesIO(amt['pdf_bytes'])).get_fields();mapping=official_forms.MAP['f6251']['line_fields']
        self.assertEqual(str(fields[mapping['9']]['/V']),'34743')
        self.assertEqual(str(fields[mapping['11']]['/V']),'0')

if __name__=='__main__':unittest.main()
