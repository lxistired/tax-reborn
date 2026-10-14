"""IRS2025 printed-line/field oracles and real interactive supporting packets.

Golden amounts/field suffixes below were authored from the public IRS2025 forms
before importing official_forms. No output from the packet builder is an oracle.
All identities and underlying documents in these tests are synthetic.
"""
from copy import deepcopy
import hashlib, io, json, re, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
# Public2025 printed lines cross-checked with widget coordinates/row identities.
GOLDEN_FIELDS={
 'f1040s1':{'3':(1,7),'5':(1,9),'8f':(1,18),'10':(1,38),'13':(2,3),'15':(2,5),'20':(2,12),'26':(2,30)},
 'f1040s2':{'1a':(1,3),'2':(1,12),'3':(1,13),'4':(1,15),'11':(1,22),'12':(1,23),'17c':(2,4),'21':(2,24)},
 'f1040s3':{'2':(1,4),'3':(1,5),'4':(1,6),'6d':(1,12),'8':(1,25),'9':(1,26),'11':(1,28),'15':(1,37)},
 'f1040sse':{'2':(1,5),'4a':(1,7),'10':(1,19),'11':(1,20),'12':(1,21),'13':(1,22)},
 'f8889':{'13':(1,14),'14c':(1,17),'16':(1,19),'17b':(1,20)},
 'f2441':{'3':(1,27),'11':(1,37),'25':(2,14),'26':(2,15)},
 'f8880':{'7':(1,15),'8':(1,16),'10':(1,18),'11':(1,19),'12':(1,20)},
 'f1040sr':{'10':(2,1),'13c':(2,6),'22':(2,15)},
 'f8995':{'2':(1,18),'11':(1,27),'14':(1,30),'15':(1,31)},
 'f8959':{'1':(1,3),'7':(1,9),'13':(1,15),'18':(1,20),'24':(1,26)},
 'f8962':{'1':(1,3),'24':(1,91),'25':(1,92),'26':(1,93),'29':(1,96)},
 'f8863':{'1':(1,5),'8':(1,13),'19':(1,25)},
 'f1040s1a':{'13':(1,21),'21':(1,31),'30':(2,14),'37':(2,22),'38':(2,23)},
}
BUSINESS_EXPECTED={'gross':100000,'expenses':10000,'profit':90000,'se_earnings':83115,'ss_tax':10306,'medicare_tax':2410,'se_tax':12716,'half_se':6358,'qbi_deduction':13598}
import tax_engine as engine
import tax_credits
import tax_additional
import official_forms as forms
from pypdf import PdfReader

def sample_base():
 d=engine.default_return();d['name']='Synthetic official form validation'
 d['eligibility'].update(full_year_us_resident=True,filing_status_confirmed=True,all_income_reported=True,eitc_not_applicable=True,no_amt_preferences=True)
 d['identity'].update(first_name='Example',last_name='Taxpayer',ssn='123456789',address='100 Example Street',city='Example City',state='IL',zip='60000')
 return d

def business_sample():
 d=sample_base();d['businesses']=[dict(engine.ROW_DEFAULTS['businesses'],name='Example Consulting',revenue='100000',expenses='10000',active_business=True,expenses_eligible=True,at_risk_confirmed=True,qbi_eligible=True)]
 d['interest']=[dict(engine.ROW_DEFAULTS['interest'],payer='Example Bank',taxable='100')]
 return {'data':d,'result':engine.calculate_return(d),'form_facts':{'schedule_b':{'foreign_account':False,'fbar_required':False,'foreign_trust':False},'businesses':[{'profession':'Business consulting','business_code':'541611','address':'100 Example Street','city_state_zip':'Example City IL60000','requires_1099':False,'expense_lines':{'18':'10000'}}]}}

def credits_sample():
 d=sample_base();w=dict(engine.ROW_DEFAULTS['w2'],employer='Example Employer',wages='60000',federal_withholding='6500',social_security_wages='60000',social_security_withholding='3720',medicare_wages='60000',medicare_withholding='870');d['w2']=[w]
 d['dependents']=[dict(engine.ROW_DEFAULTS['dependents'],name='Example Child',age=8,eligibility_confirmed=True)]
 care=tax_additional.default_inputs()['care'];care.update(enabled=True,work_related_expenses_confirmed=True,provider_information_confirmed=True,no_double_benefit_confirmed=True)
 care['beneficiaries']=[dict(tax_additional.row_templates()['care.beneficiaries'],beneficiary_id='child1',name='Example Child',qualified_expenses='5000',qualification_residency_confirmed=True)]
 care['providers']=[dict(tax_additional.row_templates()['care.providers'],name='Example Daycare',address='200 Example Road',tin='123456780',amount_paid='5000',eligible_provider_confirmed=True)]
 d['care']=care
 d['education'].update(enabled=True,claim_eligibility_confirmed=True,no_foreign_magi_or_prior_credit_recapture=True)
 student=dict(tax_credits.row_templates()['education.students'],student_id='taxpayer',name='Example Taxpayer',credit='aotc',institution_ein='12-3456789',tuition_and_required_fees='4000',half_time_degree_program=True,first_four_years_not_completed=True,no_felony_drug_conviction=True,eligible_institution_and_payment_period_confirmed=True,qualified_expenses_and_no_double_benefit_confirmed=True,dependency_claim_and_tin_confirmed=True,form_1098t_received_or_exception_confirmed=True)
 d['education']['students']=[student]
 return {'data':d,'result':engine.calculate_return(d),'form_facts':{'care':{'beneficiaries':[{'first_name':'Example','last_name':'Child','ssn':'123456788'}]}}}

class OfficialFormsAcceptance(unittest.TestCase):
 def test_all_templates_are_original_irs2025(self):
  self.assertEqual(len(forms.SOURCES),32)
  for id,source in forms.SOURCES.items():
   with self.subTest(form=id):
    raw=(forms.FORMS/source['path']).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),source['sha256'])
    self.assertIn('2025',PdfReader(io.BytesIO(raw)).pages[0].extract_text());self.assertTrue(source['url'].startswith('https://www.irs.gov/pub/irs-prior/'))
 def test_literal_printed_line_field_map(self):
  for id,lines in GOLDEN_FIELDS.items():
   for line,(page,num) in lines.items():
    with self.subTest(form=id,line=line):self.assertEqual(forms.MAP[id]['line_fields'][line],forms._short(id,page,num))
 def test_business_packet_literal_amounts(self):
  record=business_sample();result=forms.build_official_packet(record);by={f['id']:f for f in result['forms']}
  self.assertEqual(by['f1040sc']['line_values']['1'],100000);self.assertEqual(by['f1040sc']['line_values']['28'],10000);self.assertEqual(by['f1040sc']['line_values']['31'],90000)
  for line,key in (('4a','se_earnings'),('10','ss_tax'),('11','medicare_tax'),('12','se_tax'),('13','half_se')):self.assertEqual(by['f1040sse']['line_values'][line],BUSINESS_EXPECTED[key])
  self.assertEqual(by['f8995']['line_values']['15'],13598)
  self.assertGreater(result['verification']['verified_fields'],95)
  self.assertFalse(result['filing_packet_ready']);self.assertFalse(result['electronic_filing'])
  for f in result['forms']:self.assertEqual(f['unmapped_lines'],[])
 def test_credits_packet_literal_amounts(self):
  record=credits_sample();p=forms.build_official_packet(record);by={f['id']:f for f in p['forms']}
  self.assertEqual(by['f2441']['line_values']['3'],3000);self.assertEqual(by['f2441']['line_values']['11'],600)
  self.assertEqual(by['f8863']['line_values']['1'],2500);self.assertEqual(by['f8863']['line_values']['8'],1000);self.assertEqual(by['f8863']['line_values']['19'],1500)
  self.assertEqual(by['f1040s8']['line_values']['14'],2200)
  self.assertEqual(by['f1040s3']['line_values']['2'],600);self.assertEqual(by['f1040s3']['line_values']['3'],1500)
  self.assertEqual(by['f2441']['values'][forms._short('f2441',1,32)],'20')
  self.assertEqual(by['f2441']['values'][forms._short('f2441',1,17)],'123456788')
  for f in p['forms']:self.assertEqual(f['unmapped_lines'],[])
 def test_missing_facts_are_explicit_and_not_invented(self):
  record=business_sample();record['form_facts']={};record['data']['identity']['ssn']=''
  p=forms.build_official_packet(record);self.assertEqual(p['status'],'draft_incomplete');self.assertIn('taxpayer SSN/ITIN',p['missing_facts'])
  self.assertTrue(any('expense category' in v for v in p['missing_facts']))
  self.assertTrue(any('PartIII' in v for v in p['missing_facts']))
  self.assertTrue(all(not value.endswith('999999999') for form in p['forms'] for value in form['values'].values()))
 def test_separate_business_forms_preserve_distinct_interactive_names(self):
  r=business_sample();r['data']['businesses'].append(dict(r['data']['businesses'][0],name='Second Example',revenue='20000',expenses='1000'));r['result']=engine.calculate_return(r['data']);p=forms.build_official_packet(r)
  fields=PdfReader(io.BytesIO(p['pdf_bytes'])).get_fields();forms_c=[f for f in p['forms'] if f['id']=='f1040sc'];self.assertEqual(len(forms_c),2)
  saved=[str(v.get('/V','')) for k,v in fields.items() if k.endswith(forms.MAP['f1040sc']['line_fields']['31']) and k.startswith('f1040sc_')]
  self.assertEqual(sorted(saved),['19000','90000'])
  self.assertGreater(p['verification']['verified_fields'],100)
  self.assertTrue(any(k.startswith('f1040sc_') for k in fields));self.assertTrue(p['verification']['widget_values_and_appearances_verified'])
 def test_no_forms_when_no_supporting_schedule_applies(self):
  d=sample_base();p=forms.build_official_packet({'data':d,'result':engine.calculate_return(d)});self.assertEqual(p['forms'],[]);self.assertEqual(p['pdf_bytes'],b'')
 def test_malformed_identity_fails_closed(self):
  r=business_sample();r['data']['identity']['ssn']='1234';self.assertRaises(ValueError,forms.build_official_packet,r)
 def test_unknown_computed_line_is_not_silently_dropped(self):
  f=forms.render_official_form('f1040s1',{'999':123});self.assertEqual(f['unmapped_lines'],['999']);self.assertEqual(f['status'],'draft_incomplete')
 def test_inputs_are_not_mutated(self):
  r=credits_sample();before=deepcopy(r);forms.build_official_packet(r);self.assertEqual(r,before)
 def test_real_hsa_and_marketplace_lines(self):
  from tests.test_credits import CASES,adapted_data
  d=sample_base();d['w2']=[dict(engine.ROW_DEFAULTS['w2'],employer='ExampleEmployer',wages='40000',social_security_wages='40000',medicare_wages='40000',medicare_withholding='580')]
  d['hsa']=adapted_data(CASES['hsa_self_limit_employer']);d['marketplace']=adapted_data(CASES['ptc_250percent_annual_net_credit'])
  r=engine.calculate_return(d);p=forms.build_official_packet({'data':d,'result':r});by={f['id']:f for f in p['forms']}
  self.assertEqual(by['f8889']['line_values']['13'],r['schedules']['form_8889']['deduction']);self.assertEqual(by['f8962']['line_values']['24'],r['schedules']['form_8962']['form_lines']['line24'])
  for f in p['forms']:self.assertEqual(f['unmapped_lines'],[])

if __name__=='__main__':unittest.main()
