"""Independent printed2025 Form1040 choices and actual paper-preparation paths."""
from copy import deepcopy
import io
import unittest
import forms
import tax_engine
from pypdf import PdfReader

P1='topmostSubform[0].Page1[0].'
P2='topmostSubform[0].Page2[0].'
# Literal IRS2025 field identities, retained separately from implementation maps.
STATUS_FIELDS={'single':(P1+'Checkbox_ReadOrder[0].c1_8[0]','/1'),
 'mfj':(P1+'Checkbox_ReadOrder[0].c1_8[1]','/2'),
 'mfs':(P1+'Checkbox_ReadOrder[0].c1_8[2]','/3'),
 'hoh':(P1+'c1_8[0]','/4'),'qss':(P1+'c1_8[1]','/5')}

def example(status='single'):
 d=tax_engine.default_return();d['name']='Synthetic paper acceptance';d['filing_status']=status
 d['eligibility'].update(full_year_us_resident=True,filing_status_confirmed=True,all_income_reported=True,no_amt_preferences=True,eitc_not_applicable=True,hoh_eligible=status=='hoh',qss_eligible=status=='qss')
 d['identity'].update(first_name='Example',last_name='Taxpayer',ssn='123456789',address='100 Example Street',city='Example City',state='IL',zip='60000',spouse_first_name='Example',spouse_last_name='Spouse',spouse_ssn='123456788',phone='5550100100',occupation='Consultant')
 d['filing_details'].update(digital_asset_answer='no',main_home_us_answer='yes')
 d['w2']=[dict(tax_engine.ROW_DEFAULTS['w2'],employer='Synthetic Employer',wages='60000',social_security_wages='60000',medicare_wages='60000',federal_withholding='7000')]
 return {'data':d,'result':tax_engine.calculate_return(d),'updated_at':'2026-10-13T00:00:00Z'}

def fields(raw):return PdfReader(io.BytesIO(raw)).get_fields()

class PaperPacketAcceptance(unittest.TestCase):
 def test_all_five_statuses_have_one_correct_visible_selection(self):
  for status,(selected,state) in STATUS_FIELDS.items():
   with self.subTest(status=status):
    r=example(status);raw=forms.paper_packet_pdf(r);saved=fields(raw)
    self.assertEqual(str(saved[selected]['/V']),state)
    for key,_ in STATUS_FIELDS.values():
     if key!=selected:self.assertEqual(str(saved[key]['/V']),'/Off')
    self.assertTrue(forms.verify_fields(raw,forms.filing_values(r))['interactive'])
 def test_mfs_name_is_written_to_the_mfs_name_cell(self):
  f=fields(forms.paper_packet_pdf(example('mfs')))
  self.assertEqual(f[P1+'Checkbox_ReadOrder[0].f1_28[0]']['/V'],'Example Spouse')
  self.assertEqual(f[P1+'f1_19[0]']['/V'],'123456788')
  self.assertNotIn('/V',f[P1+'f1_17[0]'])
 def test_bank_and_designee_preserve_leading_digits_and_appearances(self):
  r=example();r['data']['filing_details'].update(refund_delivery='direct_deposit',bank_type='savings',bank_routing='021000021',bank_account='001234567',designee_yes=True,designee_name='Example Helper',designee_phone='5550100101',designee_pin='00012')
  raw=forms.paper_packet_pdf(r);f=fields(raw)
  for key,value in [(P2+'RoutingNo[0].f2_32[0]','021000021'),(P2+'AccountNo[0].f2_33[0]','001234567'),(P2+'f2_39[0]','00012'),(P2+'c2_16[1]','/2'),(P2+'c2_17[0]','/1')]:self.assertEqual(str(f[key]['/V']),value)
  forms.verify_fields(raw,forms.filing_values(r))
 def test_invalid_routing_does_not_produce_a_deposit_instruction(self):
  r=example();r['data']['filing_details'].update(refund_delivery='direct_deposit',bank_type='checking',bank_routing='021000022',bank_account='1234')
  self.assertIn('Valid nine-digit refund routing number',forms.packet_status(r)['missing_facts'])
  self.assertRaises(ValueError,forms.paper_packet_pdf,r)
 def test_unanswered_paper_question_blocks_preparation_without_changing_tax(self):
  r=example();before=deepcopy(r);r['data']['filing_details']['digital_asset_answer']='unanswered'
  s=forms.packet_status(r)
  self.assertFalse(s['paper_preparation_complete']);self.assertIn('Form1040 digital asset yes/no answer',s['missing_facts'])
  self.assertEqual(r['result'],before['result'])
 def test_complete_simple_preparation_has_real1040_and_no_filing_claim(self):
  r=example();s=forms.packet_status(r);raw=forms.paper_packet_pdf(r)
  self.assertTrue(s['paper_preparation_complete']);self.assertEqual(s['status'],'ready_to_print_and_review')
  self.assertTrue(s['requires_taxpayer_signature']);self.assertFalse(s['transmitted']);self.assertFalse(s['electronic_filing'])
  self.assertEqual(len(PdfReader(io.BytesIO(raw)).pages),3)
  # IRS TY2025 tax-table row44,250 <= income <44,300: Single tax5075.
  self.assertEqual(fields(raw)[P2+'f2_31[0]']['/V'],'1925')
 def test_child_fields_and_credit_boxes_survive_pdf_serialization(self):
  r=example('mfj');r['data']['dependents']=[dict(tax_engine.ROW_DEFAULTS['dependents'],name='Example Child',form_first_name='Example',form_last_name='Child',form_ssn='123456787',relationship='Daughter',age=8,eligibility_confirmed=True,lived_with_taxpayer_more_than_half_year=True,us_home_more_than_half_year=True)]
  r['result']=tax_engine.calculate_return(r['data']);raw=forms.paper_packet_pdf(r);f=fields(raw)
  self.assertEqual(f[P1+'Table_Dependents[0].Row1[0].f1_31[0]']['/V'],'Example')
  self.assertEqual(f[P1+'Table_Dependents[0].Row2[0].f1_35[0]']['/V'],'Child')
  self.assertEqual(f[P1+'Table_Dependents[0].Row3[0].f1_39[0]']['/V'],'123456787')
  self.assertEqual(f[P1+'Table_Dependents[0].Row4[0].f1_43[0]']['/V'],'Daughter')
  self.assertEqual(str(f[P1+'Table_Dependents[0].Row7[0].Dependent1[0].c1_28[0]']['/V']),'/1')
  self.assertEqual(str(f[P1+'Table_Dependents[0].Row7[0].Dependent1[0].c1_28[1]']['/V']),'/Off')
  self.assertTrue(any(k.startswith('f1040s8_') for k in f))
 def test_pdf_does_not_mutate_saved_return(self):
  r=example();before=deepcopy(r);forms.paper_packet_pdf(r);self.assertEqual(r,before)
 def test_age_and_blindness_choices_are_visible(self):
  r=example('mfj');r['data']['taxpayer'].update(age=70,blind=True);r['data']['spouse'].update(age=66);r['result']=tax_engine.calculate_return(r['data'])
  f=fields(forms.paper_packet_pdf(r))
  for short in ('c2_5[0]','c2_6[0]','c2_7[0]'):self.assertEqual(str(f[P2+short]['/V']),'/1')
  self.assertEqual(str(f[P2+'c2_8[0]']['/V']),'/Off')

if __name__=='__main__':unittest.main()
