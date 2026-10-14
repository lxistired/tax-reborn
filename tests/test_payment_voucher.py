"""Real official Form1040-V fields, explicit payment facts and no tax mutation."""
from copy import deepcopy
import io,unittest
from pypdf import PdfReader
import tax_engine as engine
import tax_filing,forms,official_forms
from payment_voucher_qa import cases,return_for,verify_packet,P


class PaymentVoucher(unittest.TestCase):
    def test_three_independent_owed_cases_and_complete_official_voucher(self):
        for case in cases():
            with self.subTest(case=case['name']):
                d=return_for(engine,case);r=engine.calculate_return(d)
                self.assertTrue(r['can_prepare'],r['blocking_issues'])
                self.assertEqual({k:r['lines'][k]for k in ('16','17','23','24','37')},
                    {'16':case['regular_tax'],'17':case['AMT'],'23':case['NIIT'],'24':case['total_tax'],'37':case['owed']})
                record={'data':d,'result':r};status=forms.packet_status(record)
                self.assertTrue(status['paper_preparation_complete'],status['missing_facts'])
                self.assertEqual(status['payment_voucher']['amount'],str(case['owed'])+'.00')
                self.assertFalse(status['payment_voucher']['payment_initiated'])
                proof=verify_packet(forms.paper_packet_pdf(record),str(case['owed'])+'.00',official_forms)
                self.assertEqual(proof['canonical_and_widget_fields'],9)

    def test_custom_cents_are_not_added_to_tax_payments_or_rounded(self):
        d=return_for(engine,cases()[0]);before=engine.calculate_return(d)
        d['filing_details'].update(paper_payment_amount_source='custom',paper_payment_amount='999.99')
        r=engine.calculate_return(d);self.assertEqual(r['lines'],before['lines']);self.assertEqual(r['summary'],before['summary'])
        verify_packet(forms.paper_packet_pdf({'data':d,'result':r}),'999.99',official_forms)
        self.assertEqual(r['lines']['37'],2435);self.assertEqual(r['lines']['25d'],1000)

    def test_method_and_confirmation_are_separate_from_computation(self):
        d=return_for(engine,cases()[0]);d['filing_details']['paper_payment_confirmed']=False
        r=engine.calculate_return(d);self.assertTrue(r['can_prepare'])
        self.assertIn('Confirm the paper payment amount and method',forms.packet_status({'data':d,'result':r})['missing_facts'])
        d['filing_details']['balance_due_payment_method']='unanswered';r=engine.calculate_return(d)
        self.assertFalse(any(f['id']=='f1040v'for f in official_forms.build_official_packet({'data':d,'result':r})['forms']))
        self.assertFalse(forms.packet_status({'data':d,'result':r})['paper_preparation_complete'])

    def test_electronic_choice_has_no_paper_voucher_or_payment_effect(self):
        d=return_for(engine,cases()[0]);before=engine.calculate_return(d)
        d['filing_details'].update(balance_due_payment_method='electronic',paper_payment_amount_source='custom',paper_payment_amount='999.99')
        r=engine.calculate_return(d);self.assertEqual(r['lines'],before['lines'])
        self.assertFalse(any(f['id']=='f1040v'for f in official_forms.build_official_packet({'data':d,'result':r})['forms']))
        status=forms.packet_status({'data':d,'result':r});self.assertFalse(status['payment_voucher']['requested']);self.assertFalse(status['payment_voucher']['payment_initiated'])

    def test_refund_after_income_edit_requires_paper_selection_review(self):
        d=return_for(engine,cases()[0]);d['w2'][0]['federal_withholding']='5000';r=engine.calculate_return(d)
        self.assertGreater(r['lines']['35a'],0);self.assertEqual(r['lines']['37'],0)
        status=forms.packet_status({'data':d,'result':r});self.assertFalse(status['payment_voucher']['requested'])
        self.assertTrue(any('no longer has a balance' in x for x in status['missing_facts']))

    def test_invalid_payment_strings_refused_and_blank_zero_reviewed(self):
        d=return_for(engine,cases()[0])
        for value in ('-1','1.001','100000000','NaN',1.2,True):
            d['filing_details']['paper_payment_amount']=value
            with self.subTest(value=value),self.assertRaises(ValueError):engine.calculate_return(d)
        for value in ('','0'):
            d['filing_details'].update(paper_payment_amount_source='custom',paper_payment_amount=value)
            r=engine.calculate_return(d);self.assertTrue(r['can_prepare']);self.assertTrue(forms.packet_status({'data':d,'result':r})['missing_facts'])

    def test_joint_voucher_has_both_ssns_but_mfs_does_not_fill_second_ssn(self):
        d=return_for(engine,cases()[0]);d['filing_status']='mfj';d['identity'].update(spouse_first_name='Synthetic',spouse_middle_initial='B',spouse_last_name='Spouse',spouse_ssn='987654321')
        d['spouse'].update(age=40,valid_ssn=True,valid_tin=True);d['w2'][0]['wages']='150000';d['w2'][0]['medicare_wages']='150000'
        r=engine.calculate_return(d);voucher=next(f for f in official_forms.build_official_packet({'data':d,'result':r})['forms']if f['id']=='f1040v')
        fields=PdfReader(io.BytesIO(voucher['pdf_bytes'])).get_fields();self.assertEqual(fields[P+'f1_2[0]']['/V'],'987654321');self.assertEqual(fields[P+'f1_7[0]']['/V'],'Synthetic B');self.assertEqual(fields[P+'f1_8[0]']['/V'],'Spouse')
        d['filing_status']='mfs';r=engine.calculate_return(d);voucher=next(f for f in official_forms.build_official_packet({'data':d,'result':r})['forms']if f['id']=='f1040v');fields=PdfReader(io.BytesIO(voucher['pdf_bytes'])).get_fields();self.assertNotIn('/V',fields[P+'f1_2[0]'])


if __name__=='__main__':unittest.main()
