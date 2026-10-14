from copy import deepcopy
import io,unittest
from pypdf import PdfReader
import tax_engine as engine
import tax_filing,forms,official_forms
from payment_voucher_qa import cases,return_for
from foreign_address_qa import CASES,apply_address,verify_packet

class ForeignMailingAddress(unittest.TestCase):
    def test_foreign_packet_separate_printed_rows_and_unmodified_tax(self):
        for case in CASES:
            with self.subTest(country=case['country']):
                domestic=return_for(engine,cases()[0]);before=engine.calculate_return(domestic)
                d=apply_address(deepcopy(domestic),case);result=engine.calculate_return(d)
                self.assertEqual(result['lines'],before['lines']);self.assertEqual(result['summary'],before['summary'])
                self.assertEqual(result['form_readiness']['missing_identity'],[])
                self.assertTrue(forms.packet_status({'data':d,'result':result})['paper_preparation_complete'])
                self.assertEqual((d['identity']['state'],d['identity']['zip']),('IL','60000'))
                verify_packet(forms.paper_packet_pdf({'data':d,'result':result}),case,official_forms)
                d['identity'].update(state='',zip='');result=engine.calculate_return(d)
                self.assertEqual(result['form_readiness']['missing_identity'],[])

    def test_explicit_format_switch_retains_inputs_and_excludes_inactive_rows(self):
        d=apply_address(return_for(engine,cases()[0]),CASES[0]);saved=deepcopy(d['identity'])
        d['filing_details']['mailing_address_type']='domestic';result=engine.calculate_return(d)
        self.assertEqual(d['identity'],saved);self.assertEqual(result['lines']['37'],2435)
        fields=PdfReader(io.BytesIO(forms.form1040_pdf({'data':d,'result':result}))).get_fields()
        p='topmostSubform[0].Page1[0].Address_ReadOrder[0].'
        self.assertEqual(fields[p+'f1_23[0]']['/V'],'IL');self.assertEqual(fields[p+'f1_24[0]']['/V'],'60000')
        for n in (25,26,27):self.assertEqual(fields[p+f'f1_{n}[0]'].get('/V',''),'')

    def test_foreign_country_missing_or_abbreviated_blocks_only_paper_readiness(self):
        for country in ('','DE'):
            d=apply_address(return_for(engine,cases()[0]),CASES[0]);d['identity']['foreign_country']=country
            result=engine.calculate_return(d);self.assertTrue(result['can_prepare']);self.assertEqual(result['lines']['37'],2435)
            self.assertFalse(forms.packet_status({'data':d,'result':result})['paper_preparation_complete'])
            self.assertTrue(result['form_readiness']['missing_identity'])

    def test_foreign_postal_and_province_are_optional_when_not_applicable(self):
        d=apply_address(return_for(engine,cases()[0]),CASES[0]);d['identity'].update(foreign_province='',foreign_postal_code='')
        r=engine.calculate_return(d);self.assertEqual(r['form_readiness']['missing_identity'],[])
        self.assertTrue(forms.packet_status({'data':d,'result':r})['paper_preparation_complete'])

    def test_legacy_addresses_migrate_and_invalid_mode_is_rejected(self):
        d=apply_address(return_for(engine,cases()[0]),CASES[1]);del d['filing_details']['mailing_address_type']
        self.assertEqual(engine.normalized(d)['filing_details']['mailing_address_type'],'foreign')
        d['identity']['foreign_country']='';self.assertEqual(engine.normalized(d)['filing_details']['mailing_address_type'],'domestic')
        d['filing_details']['mailing_address_type']='unknown'
        with self.assertRaises(ValueError):engine.normalized(d)

    def test_mailing_country_does_not_override_tax_eligibility(self):
        d=apply_address(return_for(engine,cases()[0]),CASES[0]);d['eligibility']['full_year_us_resident']=False
        self.assertFalse(engine.calculate_return(d)['can_prepare'])

    def test_legacy_cached_US_readiness_cannot_block_current_foreign_packet(self):
        d=apply_address(return_for(engine,cases()[0]),CASES[1]);del d['filing_details']['mailing_address_type']
        d['identity'].update(state='',zip='');r=engine.calculate_return(d)
        r['form_readiness']['missing_identity']=['State','ZIP code']
        self.assertTrue(forms.packet_status({'data':d,'result':r})['paper_preparation_complete'])
        verify_packet(forms.paper_packet_pdf({'data':d,'result':r}),CASES[1],official_forms)

if __name__=='__main__':unittest.main()
