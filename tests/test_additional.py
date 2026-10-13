"""TY2025 IRS2441/8880/ScheduleR directed boundary and integration checks."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
import tax_engine as engine
import tax_additional as a


def care():
    data=a.default_inputs()['care'];data.update(enabled=True,work_related_expenses_confirmed=True,
      provider_information_confirmed=True,no_double_benefit_confirmed=True,benefits_qualification_confirmed=True)
    data['beneficiaries']=[dict(a.row_templates()['care.beneficiaries'],beneficiary_id='synthetic',name='Synthetic child',qualified_expenses='6000',qualification_residency_confirmed=True)]
    data['providers']=[dict(a.row_templates()['care.providers'],name='Synthetic Care',address='100 Test Road',tin='Tax-Exempt',eligible_provider_confirmed=True)]
    return data


class AdditionalTests(unittest.TestCase):
    def test_care_statutory_rates_and_earned_limits(self):
        data=care();ctx=dict(filing_status='single',agi=15000,earned_taxpayer=6000,earned_spouse=0,benefits_received=0,tax_liability_limit=5000)
        self.assertEqual(a.calculate_care(data,ctx)['nonrefundable_credit'],1050)
        ctx['agi']=15001;self.assertEqual(a.calculate_care(data,ctx)['nonrefundable_credit'],1020)
        ctx['agi']=43001;self.assertEqual(a.calculate_care(data,ctx)['nonrefundable_credit'],600)
        ctx.update(filing_status='mfj',earned_spouse=1000)
        self.assertEqual(a.calculate_care(data,ctx)['nonrefundable_credit'],200)

    def test_care_fsa_extra_wages_are_reported_as_1e(self):
        data=engine.default_return();data['filing_status']='mfj'
        for key in ('full_year_us_resident','filing_status_confirmed','all_income_reported','no_amt_preferences'):data['eligibility'][key]=True
        data['w2']=[dict(engine.ROW_DEFAULTS['w2'],employer='Synthetic',wages='60000',dependent_care_benefits='5000',medicare_wages='60000',social_security_wages='60000'),
                    dict(engine.ROW_DEFAULTS['w2'],employer='Synthetic spouse',owner='spouse',wages='2000',medicare_wages='2000',social_security_wages='2000')]
        data['care']=care();data['care']['benefits_expenses_incurred']='6000'
        result=engine.calculate_return(data)
        #Exclusion min(benefits5000,expenses6000,spouseearnings2000)=2000;taxable3000.
        self.assertTrue(result['can_prepare'],result['blocking_issues'])
        self.assertEqual(result['lines']['1a'],62000);self.assertEqual(result['additional_lines']['1e'],3000)
        self.assertEqual(result['additional_lines']['1z'],65000);self.assertEqual(result['lines']['11b'],65000)
        self.assertEqual(result['schedules']['form_2441']['form_lines']['25'],2000)
        self.assertEqual(result['schedules']['form_2441']['nonrefundable_credit'],200)

    def test_provider_identity_type_and_absence_gates(self):
        ctx=dict(filing_status='single',agi=50000,earned_taxpayer=50000,benefits_received=0,tax_liability_limit=5000)
        data=care();data['providers']=[]
        self.assertFalse(a.calculate_care(data,ctx)['can_compute'])
        for field in ('name','address','tin'):
            data=care();data['providers'][0][field]=''
            self.assertFalse(a.calculate_care(data,ctx)['can_compute'])
            data['providers'][0][field]=123
            with self.assertRaises(ValueError):a.calculate_care(data,ctx)

    def test_saver_same_line_raw_ira_able_and_joint_distribution_rounding(self):
        data=a.default_inputs()['saver'];data.update(enabled=True,contributions_eligibility_confirmed=True,distribution_window_and_exclusions_confirmed=True,
             taxpayer_able_contributions='1000.49')
        ctx=dict(filing_status='single',agi=20000,taxpayer_age=35,spouse_age=35,taxpayer_can_be_claimed=False,ira_taxpayer=1000,ira_taxpayer_raw='1000.49',ira_spouse=0,tax_liability_limit=5000)
        r=a.calculate_saver(data,ctx);self.assertEqual(r['form_lines']['columns']['taxpayer']['1'],2001)
        self.assertEqual(r['nonrefundable_credit'],1000)
        data.update(taxpayer_able_contributions='0',taxpayer_employer_contributions='5000',spouse_employer_contributions='5000',taxpayer_distributions='1000.49',spouse_distributions='1000.49')
        ctx.update(filing_status='mfj',agi=40000,ira_taxpayer=0,ira_taxpayer_raw='0')
        r=a.calculate_saver(data,ctx)
        self.assertEqual(r['form_lines']['columns']['taxpayer']['4'],2001)
        self.assertEqual(r['form_lines']['columns']['spouse']['4'],2001)
        self.assertEqual(r['nonrefundable_credit'],2000)

    def test_saver_qss_rate_and_disabled_spouse_mfs_credit(self):
        data=a.default_inputs()['saver'];data.update(enabled=True,contributions_eligibility_confirmed=True,distribution_window_and_exclusions_confirmed=True,taxpayer_employer_contributions='2000')
        ctx=dict(filing_status='qss',agi=30000,taxpayer_age=40,spouse_age=40,ira_taxpayer=0,ira_spouse=0,tax_liability_limit=5000)
        self.assertEqual(a.calculate_saver(data,ctx)['nonrefundable_credit'],200)
        data=a.default_inputs()['elderly_credit'];data.update(enabled=True,eligibility_confirmed=True,nontaxable_benefits_confirmed=True)
        ctx.update(filing_status='mfs',agi=7500,taxpayer_age=70,ss_nontaxable=0,disability_income_available=0)
        r=a.calculate_elderly(data,ctx);self.assertFalse(r['can_compute']);self.assertEqual(r['nonrefundable_credit'],0)

    def test_monthly_deemed_income_reconciles_and_preserves_input(self):
        data=care();data['deemed_income_eligibility_confirmed']=True
        data['deemed_income_months']=[dict(a.row_templates()['care.deemed_income_months'],month=i,taxpayer_income='6000' if i==12 else '0',deemed_owner='spouse' if i<=5 else 'none') for i in range(1,13)]
        ctx=dict(filing_status='mfj',agi=20000,earned_taxpayer=6000,earned_spouse=0,benefits_received=0,tax_liability_limit=5000)
        before=deepcopy(data);r=a.calculate_care(data,ctx)
        #Oneperson=>5*$250=1250spouseearnings;AGI20000=>32% credit400.
        self.assertEqual(r['nonrefundable_credit'],400);self.assertEqual(data,before)
        data['deemed_income_months'][0]['taxpayer_income']='1'
        with self.assertRaises(ValueError):a.calculate_care(data,ctx)

    def test_observed_ira_contribution_requires_saver_review(self):
        data=engine.default_return()
        for key in ('full_year_us_resident','filing_status_confirmed','all_income_reported','no_amt_preferences'):data['eligibility'][key]=True
        data['w2']=[dict(engine.ROW_DEFAULTS['w2'],employer='Synthetic',wages='30000',medicare_wages='30000',social_security_wages='30000')]
        data['ira'].update(enabled=True,traditional_taxpayer='7000',contributions_and_coverage_confirmed=True,compensation_and_magi_confirmed=True,no_rollovers_recharacterizations_or_prior_excess=True)
        r=engine.calculate_return(data);self.assertFalse(r['can_prepare']);self.assertTrue(any('Saver credit' in b for b in r['blocking_issues']))
        data['saver'].update(enabled=True,contributions_eligibility_confirmed=True,distribution_window_and_exclusions_confirmed=True)
        r=engine.calculate_return(data);self.assertTrue(r['can_prepare'],r['blocking_issues'])
        self.assertEqual(r['lines']['16'],728);self.assertEqual(r['lines']['20'],728);self.assertEqual(r['lines']['24'],0)

    def test_qualified_disability_distribution_in_saver_window(self):
        data=engine.default_return()
        for key in ('full_year_us_resident','filing_status_confirmed','all_income_reported','no_amt_preferences'):data['eligibility'][key]=True
        data['taxpayer']['age']=50
        data['w2']=[dict(engine.ROW_DEFAULTS['w2'],employer='Synthetic',wages='5000',medicare_wages='5000',social_security_wages='5000')]
        data['retirement'].update(disability_taxpayer_gross='15000',disability_taxpayer_taxable='15000',disability_before_minimum_retirement_age_confirmed=True,disability_amounts_confirmed=True,early_distribution_exception_confirmed=True,qualified_plan_confirmed=True)
        data['ira'].update(enabled=True,traditional_taxpayer='2000',contributions_and_coverage_confirmed=True,compensation_and_magi_confirmed=True,no_rollovers_recharacterizations_or_prior_excess=True)
        data['saver'].update(enabled=True,contributions_eligibility_confirmed=True,distribution_window_and_exclusions_confirmed=True)
        r=engine.calculate_return(data);self.assertFalse(r['can_prepare']);self.assertTrue(any('omit known2025' in b for b in r['blocking_issues']))
        data['saver']['taxpayer_distributions']='15000'
        r=engine.calculate_return(data);self.assertTrue(r['can_prepare'],r['blocking_issues'])
        self.assertEqual(r['schedules']['form_8880']['nonrefundable_credit'],0)


if __name__=='__main__':unittest.main()
