"""Source-grounded synthetic checks, independent directed expected amounts.

The public fixture expected values were hand calculated from the cited IRS
2025 worksheets/table, not copied from calculate_return. Independent acceptance
is owned separately and tests complete Form1040 maps.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import unittest

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import tax_engine as engine

FIXTURE=json.loads((BASE/'fixtures'/'tax_cases.json').read_text())


def ready():
    data=engine.default_return()
    for key in ('full_year_us_resident','filing_status_confirmed','all_income_reported','no_amt_preferences'):
        data['eligibility'][key]=True
    return data


def wages(amount,med='0'):
    return dict(engine.ROW_DEFAULTS['w2'],employer='Synthetic Employer',wages=amount,
                social_security_wages=str(min(Decimal(amount),Decimal(176100))),medicare_wages=amount,medicare_withholding=med)


class TaxEngineTests(unittest.TestCase):
    def test_source_grounded_directed_returns(self):
        for case in FIXTURE['cases']:
            with self.subTest(case=case['id']):
                result=engine.calculate_return(case['input'])
                self.assertEqual(result['can_prepare'],case['can_prepare'],result['blocking_issues'])
                for line,expected in case['expected_lines'].items():
                    self.assertEqual(result['lines'][line],expected,line)
                for path,expected in case['expected_schedule'].items():
                    value=result['schedules']
                    for field in path.split('.'):value=value[field]
                    self.assertEqual(value,expected,path)

    def test_official_irs_table_example_and_boundaries(self):
        self.assertEqual(engine.ordinary_tax(25300,'mfj'),2562)
        self.assertEqual(engine.ordinary_tax(0,'single'),0)
        self.assertEqual(engine.ordinary_tax(5,'single'),1)
        self.assertEqual(engine.ordinary_tax(25,'single'),4)
        self.assertEqual(engine.ordinary_tax(99999,'single'),16909)
        self.assertEqual(engine.ordinary_tax(100000,'single'),16914)
        self.assertEqual(engine.ordinary_tax(100000,'qss'),engine.ordinary_tax(100000,'mfj'))

    def test_tax_table_continuous_and_primary_provenance(self):
        last=0
        for row in engine.RULES['tax_table']:
            self.assertEqual(row[0],last);self.assertGreater(row[1],row[0]);last=row[1]
            self.assertTrue(all(type(value) is int for value in row))
        self.assertEqual(last,100000)
        self.assertEqual(len(engine.RULES['tax_table']),2062)
        for source in engine.RULES['sources'].values():
            self.assertTrue(source['url'].startswith('https://www.irs.gov/pub/irs-pdf/'))
            self.assertEqual(source['tax_year'],2025)
            self.assertRegex(source['sha256'],r'^[0-9a-f]{64}$')

    def test_no_float_and_invalid_inputs_fail_without_mutation(self):
        for value in (50000,50000.0,'NaN','Infinity','-1','100.001','1e6'):
            data=ready();data['w2']=[wages('50000')];data['w2'][0]['wages']=value
            before=deepcopy(data)
            with self.subTest(value=repr(value)),self.assertRaises(ValueError):engine.calculate_return(data)
            self.assertEqual(data,before)
        data=ready();data['unsupported_foreign_field']='1000'
        with self.assertRaises(ValueError):engine.calculate_return(data)
        data=ready();data['tax_year']=2024
        with self.assertRaises(ValueError):engine.calculate_return(data)
        data=ready();data['dividends']=[{'ordinary':'100','qualified':'101'}]
        with self.assertRaises(ValueError):engine.calculate_return(data)

    def test_same_income_line_add_cents_before_dollar_rounding(self):
        data=ready();data['w2']=[wages('30000.49'),dict(wages('30000.49'),employer='Second synthetic employer')]
        result=engine.calculate_return(data)
        self.assertEqual(result['lines']['1a'],60001)
        self.assertEqual(result['lines']['15'],44251)
        self.assertEqual(result['lines']['16'],5075)

    def test_dependency_deduction_and_missing_checks(self):
        blank=engine.calculate_return(engine.default_return())
        self.assertFalse(blank['can_prepare']);self.assertGreaterEqual(len(blank['blocking_issues']),4)
        data=ready();data['businesses']=[{'name':'Undocumented business','revenue':'50000','expenses':'0'}]
        result=engine.calculate_return(data)
        self.assertFalse(result['can_prepare']);self.assertTrue(any('expenses_eligible' in value for value in result['blocking_issues']))
        data=ready();data['itemized']['mortgage_interest']='30000'
        result=engine.calculate_return(data)
        self.assertFalse(result['can_prepare']);self.assertTrue(any('Mortgage' in value for value in result['blocking_issues']))

    def test_unsupported_deductions_are_not_silently_applied(self):
        for key in ('ira_deduction','hsa_deduction'):
            data=ready();data['w2']=[wages('60000')];data['adjustments'][key]='5000'
            result=engine.calculate_return(data)
            self.assertFalse(result['can_prepare']);self.assertEqual(result['lines']['10'],0)
        data=ready();data['itemized']['investment_interest']='30000'
        result=engine.calculate_return(data)
        self.assertFalse(result['can_prepare']);self.assertEqual(result['schedules']['schedule_a']['itemized_total'],0)

    def test_automatic_unsupported_tax_screens(self):
        data=ready();data['w2']=[wages('10000')]
        result=engine.calculate_return(data)
        self.assertFalse(result['can_prepare']);self.assertTrue(any('EITC' in value for value in result['blocking_issues']))
        data=ready();data['interest']=[{'taxable':'300000'}]
        result=engine.calculate_return(data)
        self.assertFalse(result['can_prepare']);self.assertTrue(any('8960' in value for value in result['blocking_issues']))
        data=ready();data['interest']=[{'taxable':'50000'}];data['carryovers']['capital_short']='1000'
        self.assertFalse(engine.calculate_return(data)['can_prepare'])
        data=ready();data['businesses']=[dict(engine.ROW_DEFAULTS['businesses'],revenue='300000',active_business=True,expenses_eligible=True,at_risk_confirmed=True,qbi_eligible=True)]
        result=engine.calculate_return(data)
        self.assertFalse(result['can_prepare']);self.assertTrue(any('8995' in value for value in result['blocking_issues']))
        data=ready();data['unsupported']=['ISO/AMT','state return','Marketplace1095A']
        self.assertEqual(len(engine.calculate_return(data)['blocking_issues']),3)

    def test_capital_losses_do_not_become_zero_taxed_gains(self):
        data=ready();data['w2']=[wages('60000')];data['eligibility']['capital_gains_eligible']=True
        data['capital_gains']=[{'term':'short','proceeds':'1000','cost_basis':'7000'},{'term':'long','proceeds':'5000','cost_basis':'1000'}]
        result=engine.calculate_return(data)
        self.assertEqual(result['lines']['7a'],-2000)
        self.assertEqual(result['schedules']['qualified_dividends_capital_gain_worksheet']['zero_rate_income'],0)
        self.assertEqual(result['lines']['16'],4835)

    def test_per_owner_se_social_security_cap(self):
        data=ready();data['filing_status']='mfj';data['w2']=[wages('176100',med='2553.45')]
        data['businesses']=[dict(engine.ROW_DEFAULTS['businesses'],name='Spouse services',owner='spouse',revenue='50000',active_business=True,expenses_eligible=True,at_risk_confirmed=True,qbi_eligible=True)]
        result=engine.calculate_return(data)
        self.assertEqual(result['schedules']['schedule_se']['spouse']['line_10_ss_tax'],5726)
        self.assertEqual(result['schedules']['schedule_se']['taxpayer']['line_10_ss_tax'],0)
        data['businesses'][0]['owner']='taxpayer';result=engine.calculate_return(data)
        self.assertEqual(result['schedules']['schedule_se']['taxpayer']['line_10_ss_tax'],0)
        self.assertEqual(result['schedules']['schedule_se']['taxpayer']['line_11_medicare_tax'],1339)

    def test_three_children_actc_payroll_alternative(self):
        data=ready();data['w2']=[dict(wages('3000',med='43.50'),social_security_withholding='186')]
        data['interest']=[{'taxable':'12000'}]
        data['dependents']=[dict(engine.ROW_DEFAULTS['dependents'],name='Synthetic child'+str(i),eligibility_confirmed=True) for i in range(3)]
        result=engine.calculate_return(data)
        # 15%*(3000-2500)=75; W2Boxes4+6 aggregate round=230.
        self.assertEqual(result['lines']['28'],230)
        self.assertEqual(result['lines']['19'],0)
        self.assertTrue(result['can_prepare'],result['blocking_issues'])

    def test_qualified_dividend_and_retirement_scope_require_confirmation(self):
        data=ready();data['w2']=[wages('60000')]
        data['dividends']=[{'ordinary':'1000','qualified':'1000'}]
        result=engine.calculate_return(data)
        self.assertFalse(result['can_prepare'])
        self.assertTrue(any('Qualified dividends' in issue for issue in result['blocking_issues']))
        data['eligibility']['qualified_dividends_eligible']=True
        self.assertTrue(engine.calculate_return(data)['can_prepare'])
        data=ready();data['taxpayer']['age']=70
        data['retirement'].update(pension_gross='260000',pension_taxable='260000',taxable_amounts_confirmed=True)
        data['schedule_1a']['eligibility_confirmed']=True
        result=engine.calculate_return(data)
        self.assertFalse(result['can_prepare'])
        self.assertTrue(any('Nonqualified commercial annuities' in issue for issue in result['blocking_issues']))
        data['retirement']['qualified_plan_confirmed']=True
        self.assertTrue(engine.calculate_return(data)['can_prepare'])
        data['filing_status']='mfj';data['spouse']['age']=35
        self.assertFalse(engine.calculate_return(data)['can_prepare'])

    def test_state_roundtrip_is_pure_and_all_lines_are_ints(self):
        for demo in engine.demo_returns():
            original=deepcopy(demo['data']);first=engine.calculate_return(original)
            second=engine.calculate_return(json.loads(json.dumps(original)))
            self.assertEqual(first,second);self.assertEqual(original,demo['data'])
            self.assertTrue(first['can_prepare'],first['blocking_issues'])
            self.assertEqual(set(first['lines']),set(engine.LINE_KEYS))
            self.assertTrue(all(type(value) is int for value in first['lines'].values()))
            self.assertEqual(first['not_computed_lines'],['38'])


if __name__=='__main__':unittest.main()
