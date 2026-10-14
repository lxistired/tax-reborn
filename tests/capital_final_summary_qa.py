"""Independently authored App regression using fixed IRS2025 synthetic facts.

The adjacent fixture contains IRS literal rows and independently calculated
expected dollars. It contains no vendor compiled programs or binary assets.
"""
from pathlib import Path
import argparse,json,sys

def check_app(engine):
 fixture=json.loads((Path(__file__).resolve().parents[1]/'fixtures/capital_fifteen_final_summary_2025.json').read_text())
 rows=[]
 for case in fixture['cases']:
  data=engine.default_return();data['name']=case['name']
  data['taxpayer'].update(age=40,birth_date='1985-06-01',valid_ssn=True,valid_tin=True)
  data['eligibility'].update(full_year_us_resident=True,filing_status_confirmed=True,all_income_reported=True,no_amt_preferences=True,capital_gains_eligible=True)
  data['eitc'].update(claim=True,eligibility_confirmed=True,main_home_us_half_year=True,not_qualifying_child_of_another=True,no_disallowed_claim_history=True)
  data['w2']=[{'employer':'Synthetic employer','wages':str(case['wages']),'medicare_wages':str(case['wages']),'federal_withholding':str(case['W2_withholding'])}]
  data['interest']=[{'payer':'Synthetic bank','taxable':str(case['taxable_interest']),'tax_exempt':'0'}]
  data['dividends']=[{'payer':'Synthetic fund '+str(i+1),'ordinary':str(case['ordinary_dividends'])if i==0 else'0','qualified':'0','capital_gain_distributions':amount}for i,amount in enumerate(case['capital_distributions'])]
  if case['prior_zero_tax_exception_if_owed']:
   data['estimated_penalty'].update(enabled=True,prior_year_tax='0',prior_year_agi='0',prior_year_full_12_months=True,prior_year_tax_verified=True,no_prior_year_tax_full_year_resident_confirmed=True,actual_payment_records_confirmed=True)
  result=engine.calculate_return(data);actual={key:result['lines'][key]for key in case['expected']}
  assert actual==case['expected'],(case['name'],actual,case['expected'])
  assert result['can_prepare'],(case['name'],result['blocking_issues'])
  rows.append({'name':case['name'],'expected':case['expected'],'actual':actual,'passed':True})
 return {'cases':len(rows),'passed':len(rows),'rows':rows,'tax_year':2025,'primary_IRS_sources':fixture['primary_IRS_sources'],'scope':fixture['scope']+' Appcalculation only; officialpacket/nativeoriginal/efile acceptance is separate.'}

