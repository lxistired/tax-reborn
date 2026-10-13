"""Held-out 2025 disability1099-R classification, credits and payroll exclusion."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'fixtures/disability_independent_2025.json'
FROZEN_SHA256='d493ad75a46af2ccf4ea489b6226896f90212bea8498b48f0a722a340e41188c'
raw=FIXTURE.read_bytes()
if hashlib.sha256(raw).hexdigest()!=FROZEN_SHA256:raise RuntimeError('Disability oracle changed after freeze.')
ORACLE=json.loads(raw)


class DisabilityAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0,str(ROOT));import tax_engine
        cls.engine=tax_engine

    def data(self,case):
        f=case['facts'];x=self.engine.default_return();x['name']='Independent '+case['id'];x['filing_status']=f['filing_status'];x['taxpayer']['age']=f['age']
        for key in ('full_year_us_resident','filing_status_confirmed','all_income_reported','no_amt_preferences'):x['eligibility'][key]=True
        x['retirement'].update(disability_taxpayer_gross=f['taxable_disability'],disability_taxpayer_taxable=f['taxable_disability'],
            disability_before_minimum_retirement_age_confirmed=True,disability_amounts_confirmed=True,early_distribution_exception_confirmed=True,qualified_plan_confirmed=True)
        if f['wages']!='0':
            wage=Decimal(f['wages']);row=deepcopy(self.engine.ROW_DEFAULTS['w2']);row.update(employer='Synthetic Payroll',wages=f['wages'],federal_withholding=f.get('federal_withholding','0'),
                social_security_wages=str(min(wage,Decimal('176100'))),medicare_wages=str(wage),
                social_security_withholding=format((min(wage,Decimal('176100'))*Decimal('.062')).quantize(Decimal('.01')),'f'),
                medicare_withholding=f.get('medicare_withholding',format((wage*Decimal('.0145')).quantize(Decimal('.01')),'f')))
            x['w2']=[row]
        x['eitc'].update(claim=True,eligibility_confirmed=True,main_home_us_half_year=True,not_qualifying_child_of_another=True,no_disallowed_claim_history=True)
        if case['id']=='disability15000_before_minimum_retirement':
            x['elderly_credit'].update(enabled=True,eligibility_confirmed=True,nontaxable_benefits_confirmed=True,taxpayer_permanently_disabled=True,
                taxpayer_taxable_disability_income='15000',disability_income_in_return_confirmed=True,physician_statement_confirmed=True)
        return x

    def run_case(self,case):
        x=self.data(case);before=deepcopy(x);r=self.engine.calculate_return(x)
        self.assertIs(r['can_prepare'],True,r['blocking_issues']);self.assertEqual(x,before)
        for key,expected in case['expected'].items():
            with self.subTest(key=key):
                value=r['additional_lines'][key.split('.')[1]] if key.startswith('additional_lines.') else r['lines'][key]
                self.assertEqual(value,expected)

    def test_fixture_integrity(self):self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),FROZEN_SHA256)

    def test_old_pension_classification_must_block(self):
        x=self.data(ORACLE['cases'][0]);x['retirement'].update(disability_taxpayer_gross='0',disability_taxpayer_taxable='0',
            pension_gross='15000',pension_taxable='15000',qualified_plan_confirmed=True,taxable_amounts_confirmed=True,early_distribution_exception_confirmed=True)
        r=self.engine.calculate_return(x);self.assertIs(r['can_prepare'],False)
        self.assertTrue(any('disability' in m.lower() and ('line1h' in m or 'classification' in m) for m in r['blocking_issues']))

    def test_missing_minimum_retirement_confirmation_blocks(self):
        x=self.data(ORACLE['cases'][0]);x['retirement']['disability_before_minimum_retirement_age_confirmed']=False
        self.assertIs(self.engine.calculate_return(x)['can_prepare'],False)

    def test_missing_payer_amount_confirmation_blocks(self):
        x=self.data(ORACLE['cases'][0]);x['retirement']['disability_amounts_confirmed']=False
        self.assertIs(self.engine.calculate_return(x)['can_prepare'],False)

    def test_missing_early_distribution_exception_blocks(self):
        x=self.data(ORACLE['cases'][0]);x['retirement']['early_distribution_exception_confirmed']=False
        self.assertIs(self.engine.calculate_return(x)['can_prepare'],False)

    def test_after_minimum_before_mandatory_is_pension_not_earned(self):
        x=self.data(ORACLE['cases'][0]);x['retirement'].update(disability_taxpayer_gross='0',disability_taxpayer_taxable='0',
            pension_gross='15000',pension_taxable='15000',qualified_plan_confirmed=True,taxable_amounts_confirmed=True)
        x['elderly_credit']['taxpayer_after_minimum_retirement_age_confirmed']=True
        r=self.engine.calculate_return(x)
        self.assertIs(r['can_prepare'],True,r['blocking_issues'])
        #Minimumage and mandatoryage are different. Verifiedpastminimum is5b;
        #same15000pensionisnot EICearned;Rtaxcapacityiszero.
        self.assertEqual(r['additional_lines']['1h'],0)
        self.assertEqual(r['lines']['5b'],15000)
        self.assertEqual(r['lines']['27a'],0)

    def test_missing_qualified_us_plan_confirmation_blocks(self):
        x=self.data(ORACLE['cases'][0]);x['retirement']['qualified_plan_confirmed']=False
        self.assertIs(self.engine.calculate_return(x)['can_prepare'],False)

    def test_disability_plan_distributions_reduce_saver_and_earned_limit_controls_eic_review(self):
        x=self.data(ORACLE['cases'][0])
        row=deepcopy(self.engine.ROW_DEFAULTS['w2']);row.update(employer='Synthetic Before Disability Payroll',wages='5000',
            social_security_wages='5000',medicare_wages='5000',social_security_withholding='310',medicare_withholding='72.50')
        x['w2']=[row]
        x['ira'].update(enabled=True,traditional_taxpayer='2000',contributions_and_coverage_confirmed=True,
            compensation_and_magi_confirmed=True,no_rollovers_recharacterizations_or_prior_excess=True)
        x['saver'].update(enabled=True,contributions_eligibility_confirmed=True,distribution_window_and_exclusions_confirmed=True)
        x['eitc']['claim']=False;x['eligibility']['eitc_not_applicable']=False
        r=self.engine.calculate_return(x)
        self.assertIs(r['can_prepare'],False)
        self.assertTrue(any('saver' in issue.lower() and 'distribution' in issue.lower() for issue in r['blocking_issues']))
        x['saver']['taxpayer_distributions']='15000'
        r=self.engine.calculate_return(x)
        self.assertIs(r['can_prepare'],True,r['blocking_issues'])
        #Qualified-plan disability is a8880distribution:IRA2000-15000=>0.
        #EICearned5000+15000=20000>SingleNoChild19104,even thoughAGI18000.
        self.assertEqual(r['schedules']['form_8880']['nonrefundable_credit'],0)
        self.assertEqual(r['lines']['27a'],0)
        self.assertEqual(r['lines']['11b'],18000)

    def test_disability_taxable_exceeds_gross_rejected(self):
        x=self.data(ORACLE['cases'][0]);x['retirement']['disability_taxpayer_gross']='10000'
        with self.assertRaises(ValueError):self.engine.calculate_return(x)


def literal(case):
    def test(self):self.run_case(case)
    return test
for c in ORACLE['cases']:setattr(DisabilityAcceptance,'test_literal_'+c['id'],literal(c))

if __name__=='__main__':unittest.main()
