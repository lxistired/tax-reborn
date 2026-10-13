"""New literal TY2025 oracles, independent of the frozen264-test fixtures.

Published Form8839/2210 examples and handwritten form arithmetic. The JSON
oracles are never rewritten from engine results. These are directed scope
checks, not a claim of exhaustive IRS/Intuit certification.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import unittest

BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
import tax_engine as e
import tax_longtail as l

FIXTURE=json.loads((BASE/'fixtures/longtail_cases_2025.json').read_text())


def ready():
    data=e.default_return()
    for key in ('full_year_us_resident','filing_status_confirmed','all_income_reported','no_amt_preferences'):data['eligibility'][key]=True
    data['eligibility']['eitc_not_applicable']=True
    return data


def module_case(kind,patch=None,context=None):
    group={'foreign':'foreign_credit','penalty':'estimated_penalty'}.get(kind,kind);data=deepcopy(l.default_inputs()[group]);data['enabled']=True
    for key,default in data.items():
        if type(default) is bool and key.endswith('confirmed'):data[key]=True
    if group=='adoption':data.update(mfs_qualifying_separation=False,no_reimbursement_or_double_benefit_confirmed=True)
    if group=='energy':data.update(address='123 Synthetic Test Street, TX 75001',no_joint_occupancy_or_business_allocation=True)
    if group=='foreign_credit':data.update(no_excluded_income_or_treaty_resourcing=True,no_redeterminations_losses_or_carryovers=True)
    if group=='estimated_penalty':data.update(no_prior_year_tax_full_year_resident_confirmed=False,prior_year_tax_verified=True)
    data.update(deepcopy(patch or {}))
    for path,template in l.row_templates().items():
        prefix,key=path.split('.')
        if prefix!=group:continue
        rows=[]
        for index,submitted in enumerate(data[key]):
            row=deepcopy(template)
            if prefix=='adoption' and key=='children':row.update(name='Synthetic adoption '+str(index),tin=str(900000000+index),eligibility_timing_confirmed=True)
            if prefix=='energy':row.update(qualification_confirmed=True,fuel_cell_main_home_confirmed=True)
            row.update(submitted);rows.append(row)
        data[key]=rows
    ctx={'filing_status':'single','agi':100000,'tax_liability_limit':10000,
         'clean_tax_liability_limit':10000,'improvement_tax_liability_limit':10000,
         'interest':0,'ordinary_dividends':0,'qualified_dividends':0,'regular_tax':8000,
         'amt_tax':0,'preferred_income':0,'gross_income':80000,'standard_deduction':15750,
         'adjustments':0,'taxable_before_senior':64250,'ordinary_standard_income_only':True,
         'income_tax_after_credits':10000,'additional_tax_for_2210':0,'tax_for_2210':10000,
         'refundable_credits':0,'withholding':0,'excess_ss':0,'estimated':0,'prior_year_credit':0}
    ctx.update(context or {})
    return data,ctx


def get_path(result,path):
    for key in path.split('.'):result=result[int(key)] if isinstance(result,list) else result[key]
    return result


class LongtailAcceptance(unittest.TestCase):
    def test_frozen_original_oracles_unchanged(self):
        receipt=json.loads((BASE/'docs/final_validation_20261013.json').read_text())
        for path,digest in receipt['before'].items():
            if path.startswith(('tests/','fixtures/')):self.assertEqual(hashlib.sha256((BASE/path).read_bytes()).hexdigest(),digest,path)

    def test_integrated_adoption_with_8812_reservation(self):
        data=ready();data['filing_status']='mfj';data['w2']=[dict(e.ROW_DEFAULTS['w2'],employer='Synthetic',wages='100000',medicare_wages='100000',social_security_wages='100000')]
        data['dependents']=[dict(e.ROW_DEFAULTS['dependents'],name='Child '+str(i),eligibility_confirmed=True) for i in range(2)]
        data['adoption'],_=module_case('adoption',{'children':[{'expenses_2025':'20000'}]})
        result=e.calculate_return(data)
        for line,value in {'16':7746,'19':1000,'20':6746,'22':0,'28':3400,'30':5000,'35a':8400}.items():self.assertEqual(result['lines'][line],value,line)
        self.assertEqual(result['schedules']['schedule_8812_credit_limit_b']['14'],1000)
        self.assertFalse(result['blocking_issues'],result['blocking_issues'])

    def test_integrated_clean_improvement_child_credit_order(self):
        data=ready();data['filing_status']='mfj';data['w2']=[dict(e.ROW_DEFAULTS['w2'],employer='Synthetic',wages='100000',medicare_wages='100000',social_security_wages='100000')]
        data['dependents']=[dict(e.ROW_DEFAULTS['dependents'],name='Child '+str(i),eligibility_confirmed=True) for i in range(2)]
        data['energy'],_=module_case('energy',{'items':[{'kind':'solar_electric','cost':'20000'},{'kind':'insulation','cost':'10000'},{'kind':'heat_pump','cost':'10000','qmid':'AB12'}]})
        result=e.calculate_return(data)
        for line,value in {'16':7746,'19':1000,'20':6746,'22':0,'28':3400,'35a':3400}.items():self.assertEqual(result['lines'][line],value,line)
        self.assertEqual(result['schedules']['form_5695']['clean_credit'],3546)
        self.assertEqual(result['schedules']['form_5695']['improvement_credit'],3200)
        self.assertEqual(result['schedules']['form_5695']['clean_carryforward'],2454)
        self.assertFalse(result['blocking_issues'],result['blocking_issues'])

    def test_verified_carry_in_and_washsale_affect_capital_lines(self):
        data=ready();data['w2']=[dict(e.ROW_DEFAULTS['w2'],employer='Synthetic',wages='60000',medicare_wages='60000')]
        data['capital_records'].update(carry_in_confirmed=True,wash_sale_all_accounts_reviewed=True);data['eligibility']['capital_gains_eligible']=True
        data['carryovers'].update(capital_short='5000',capital_long='2000')
        data['capital_gains']=[dict(e.ROW_DEFAULTS['capital_gains'],description='Synthetic verified loss',term='short',proceeds='4000',cost_basis='5000',wash_sale_disallowed='600',wash_sale_confirmed=True)]
        result=e.calculate_return(data)
        self.assertEqual(result['lines']['7a'],-3000)
        self.assertEqual(result['schedules']['schedule_d']['net_short_term'],-5400)
        self.assertEqual(result['schedules']['schedule_d']['carryout_worksheet']['short_loss_carry_to_2026'],2400)
        self.assertEqual(result['schedules']['schedule_d']['carryout_worksheet']['long_loss_carry_to_2026'],2000)
        self.assertFalse(result['blocking_issues'],result['blocking_issues'])

    def test_wash_sale_invalid_double_or_excess_amount(self):
        for wash,adjustment in [('1001','0'),('600','600')]:
            data=ready();data['capital_gains']=[dict(e.ROW_DEFAULTS['capital_gains'],proceeds='4000',cost_basis='5000',wash_sale_disallowed=wash,adjustment=adjustment)]
            with self.subTest(wash=wash,adjustment=adjustment),self.assertRaises(ValueError):e.calculate_return(data)

    def test_mobile_schema_real_input_contract_and_purity(self):
        caps=e.capabilities();data=ready();before=deepcopy(data);e.calculate_return(data);self.assertEqual(data,before)
        for group in ('adoption','energy','foreign_credit','estimated_penalty','capital_records'):
            self.assertIn(group,[m['id'] for m in caps['ui_modules']])
            for key,value in data[group].items():
                if not isinstance(value,list):self.assertIn(group+'.'+key,caps['ui_fields'])
        for path,template in l.row_templates().items():
            self.assertIn(path,caps['row_templates'])
            for field in template:self.assertIn(path+'.*.'+field,caps['ui_fields'])


def literal_test(case):
    def test(self):
        if case['module']=='carryout':result=l.capital_carryout(*case['args'])
        else:
            data,ctx=module_case(case['module'],case['input'],case['context'])
            result=getattr(l,'calculate_'+case['module'])(data,ctx)
            self.assertFalse(result['blocking_issues'],case['basis']+' '+repr(result['blocking_issues']))
        for path,value in case['expected'].items():self.assertEqual(get_path(result,path),value,case['basis']+' '+path)
    return test


for case in FIXTURE['cases']:setattr(LongtailAcceptance,'test_literal_'+case['id'],literal_test(case))


GUARDS=[('adoption','employer_benefits','1000'),('adoption','eligibility_confirmed',False),('adoption','no_reimbursement_or_double_benefit_confirmed',False),
 ('energy','qualification_and_costs_confirmed',False),('energy','no_joint_occupancy_or_business_allocation',False),('energy','address',''),
 ('foreign','creditability_and_source_confirmed',False),('foreign','qualified_payee_statements_confirmed',False),('foreign','no_redeterminations_losses_or_carryovers',False),('foreign','carry_in','100'),
 ('penalty','actual_payment_records_confirmed',False),('penalty','annualized_income_requested',True),('penalty','waiver_disaster_farmer_or_special_rule',True),('penalty','early_filing_exception_requested',True)]


def guard_test(kind,key,value):
    def test(self):
        data,ctx=module_case(kind,{key:value});result=getattr(l,'calculate_'+kind)(data,ctx)
        self.assertTrue(result['blocking_issues']);self.assertFalse(result['can_compute'])
    return test


for kind,key,value in GUARDS:setattr(LongtailAcceptance,'test_guard_'+kind+'_'+key,guard_test(kind,key,value))


class LongtailInvalidCases(unittest.TestCase):
    def test_nonexistent_dates_and_floats_rejected(self):
        for day in ('2025-02-29','2025-13-01','2025-1-15','not-a-date'):
            data,ctx=module_case('penalty',{'payments':[{'date':day,'amount':'1000'}]})
            with self.subTest(day=day),self.assertRaises(ValueError):l.calculate_penalty(data,ctx)
        for value in (100,100.0,'NaN','100.001','-1'):
            data,ctx=module_case('adoption',{'children':[{'expenses_2025':value}]})
            with self.subTest(value=value),self.assertRaises(ValueError):l.calculate_adoption(data,ctx)

    def test_disabled_data_not_silently_ignored(self):
        for kind,patch in (('adoption',{'employer_benefits':'100'}),('energy',{'clean_carry_in':'100'}),('foreign',{'carry_in':'100'}),('penalty',{'balance_due_payment':'100'})):
            data,ctx=module_case(kind,dict(patch,enabled=False));result=getattr(l,'calculate_'+kind)(data,ctx)
            self.assertTrue(result['blocking_issues'],kind)

    def test_requested_foreign_unsupported_allocation_blocks(self):
        data,ctx=module_case('foreign',{'method':'ordinary_passive_1116','countries':[{'country':'Canada','ordinary_interest':'10000','tax_paid':'1000'}]},{'interest':10000,'amt_tax':100})
        self.assertTrue(l.calculate_foreign(data,ctx)['blocking_issues'])
        ctx['amt_tax']=0;ctx['preferred_income']=5000;self.assertTrue(l.calculate_foreign(data,ctx)['blocking_issues'])

    def test_qmid_battery_and_qualification_guard(self):
        for item in ({'kind':'heat_pump','cost':'5000','qmid':''},{'kind':'battery','cost':'5000'},{'kind':'energy_audit','cost':'500'}):
            data,ctx=module_case('energy',{'items':[item]});self.assertTrue(l.calculate_energy(data,ctx)['blocking_issues'])

    def test_estimated_actual_dates_reconcile_not_guessed(self):
        data,ctx=module_case('penalty',{}, {'estimated':1000});r=l.calculate_penalty(data,ctx)
        self.assertTrue(r['blocking_issues']);self.assertFalse(r['computed'])
        data,ctx=module_case('penalty',{'withholding_method':'actual_dates'}, {'withholding':1000});self.assertFalse(l.calculate_penalty(data,ctx)['computed'])


if __name__=='__main__':unittest.main()
