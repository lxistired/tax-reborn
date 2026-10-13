"""Independent literal 2025 Forms2441/8880/ScheduleR acceptance.

Oracles were saved before executing the functions. Input adapters establish
synthetic eligibility facts; they never obtain expected amounts from product code.
"""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'fixtures' / 'additional_independent_2025.json'
FROZEN_SHA256 = '1f093ac6b39e47fce4314cb1cd6f2317a45e7b1181668fab5ee3d40613c242ef'
RAW = FIXTURE.read_bytes()
if hashlib.sha256(RAW).hexdigest() != FROZEN_SHA256:
    raise RuntimeError('Additional independent oracle changed after freeze.')
ORACLE = json.loads(RAW)
CASES = {c['id']: c for c in ORACLE['cases']}


def dollars(value):
    return int(Decimal(str(value)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


class AdditionalAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('independent_tax_additional', ROOT / 'tax_additional.py')
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def adapted(self, case):
        f = case['facts']; module = case['module']
        section = 'elderly_credit' if module == 'elderly' else module
        data = self.module.default_inputs()[section]
        data['enabled'] = True
        context = dict(filing_status=f['status'], agi=dollars(f['agi']),
                       taxpayer_age=f.get('taxpayer_age', 35), spouse_age=f.get('spouse_age', 35),
                       taxpayer_can_be_claimed=False, spouse_can_be_claimed=False,
                       tax_liability_limit=f['tax_limit'])
        if module == 'care':
            total=dollars(f['expenses']); count=f['persons']
            amounts=[total//count]*count; amounts[-1]+=total-sum(amounts)
            data['beneficiaries']=[dict(self.module.row_templates()['care.beneficiaries'],
                                       beneficiary_id='synthetic-'+str(i), name='Synthetic child '+str(i),
                                       age=8, qualified_expenses=str(v), qualification_residency_confirmed=True,
                                       care_before_13th_birthday_confirmed=True, valid_tin=True)
                                   for i,v in enumerate(amounts)]
            data['providers']=[dict(self.module.row_templates()['care.providers'],
                                    name='Synthetic Licensed Care',address='100 Test Lane, Test City',
                                    tin='12-3456789',amount_paid=str(total),eligible_provider_confirmed=True)]
            data.update(work_related_expenses_confirmed=True,provider_information_confirmed=True,
                        no_double_benefit_confirmed=True,benefits_qualification_confirmed=True,
                        benefits_expenses_incurred=str(total))
            context.update(earned_taxpayer=dollars(f['earned_taxpayer']),
                           earned_spouse=dollars(f.get('earned_spouse',0)),
                           benefits_received=dollars(f.get('benefits',0)))
            if f.get('spouse_student_months'):
                data['deemed_income_eligibility_confirmed']=True
                data['deemed_income_months']=[dict(month=i,taxpayer_income=str(context['earned_taxpayer'] if i==12 else 0),
                                                  spouse_income='0',deemed_owner='spouse' if i<=f['spouse_student_months'] else 'none') for i in range(1,13)]
        elif module == 'saver':
            data.update(taxpayer_employer_contributions=f['taxpayer_contribution'],
                        spouse_employer_contributions=f.get('spouse_contribution','0'),
                        taxpayer_distributions=f.get('taxpayer_distributions','0'),
                        spouse_distributions=f.get('spouse_distributions','0'),
                        contributions_eligibility_confirmed=True,
                        distribution_window_and_exclusions_confirmed=True,
                        all_distribution_years_joint=True)
            context.update(ira_taxpayer=0,ira_spouse=0)
        else:
            data.update(eligibility_confirmed=True,nontaxable_benefits_confirmed=True,
                        mfs_lived_apart_entire_year=f.get('mfs_lived_apart',False),
                        taxpayer_taxable_disability_income=f.get('taxable_disability','0'),
                        spouse_taxable_disability_income=f.get('spouse_taxable_disability','0'),
                        taxpayer_permanently_disabled=bool(f.get('taxable_disability')),
                        spouse_permanently_disabled=bool(f.get('spouse_taxable_disability')),
                        disability_income_in_return_confirmed=True,physician_statement_confirmed=True)
            context.update(ss_nontaxable=dollars(f.get('nontaxable_ss',0)),
                           disability_income_available=dollars(f.get('taxable_disability',0))+dollars(f.get('spouse_taxable_disability',0)))
        return data, context

    def run_case(self, case):
        data,context=self.adapted(case); before=deepcopy((data,context))
        result=getattr(self.module,'calculate_'+case['module'])(data,context)
        self.assertIs(result['can_compute'],True,result['blocking_issues'])
        self.assertEqual(result['blocking_issues'],[])
        self.assertEqual(result['nonrefundable_credit'],case['expected']['credit'])
        self.assertLessEqual(result['nonrefundable_credit'],context['tax_liability_limit'])
        self.assertIs(type(result['nonrefundable_credit']),int)
        self.assertEqual((data,context),before)
        self.assertEqual(result['tax_year'],2025)
        if 'taxable_benefits' in case['expected']:
            self.assertEqual(result['taxable_benefits'],case['expected']['taxable_benefits'])
        self.assertTrue(result['trace'])
        self.assertTrue(all(t['source'].startswith('https://www.irs.gov/') for t in result['trace']))
        return result

    def guard_case(self, guard):
        module=guard['module']; id=guard['id']
        base={'care':'care_43001','saver':'saver_single_23750','elderly':'elderly_single'}[module]
        if id=='care_deemed_missing_ack':base='care_student_deemed'
        if id=='care_benefits_unverified':base='care_two_fsa5000'
        if id=='saver_mfj_nonjoint_distributionyear':base='saver_shared_distributions'
        if id.startswith('elderly_disab'):base='elderly_disabled'
        data,context=self.adapted(CASES[base])
        if id=='care_missing_work_ack':data['work_related_expenses_confirmed']=False
        elif id=='care_missing_provider':data['providers']=[];data['provider_information_confirmed']=False
        elif id=='care_household_employee':data['providers'][0]['household_employee']=True
        elif id=='care_prior_expenses':data['prior_year_expenses_paid']='10'
        elif id=='care_self_employed_benefits':data['self_employed_benefits']='10'
        elif id=='care_disabled_nonzero':data['enabled']=False
        elif id=='care_missing_person_qualification':data['beneficiaries'][0]['qualification_residency_confirmed']=False
        elif id=='care_bad_tin':data['beneficiaries'][0]['valid_tin']=False
        elif id=='care_age13_not_disabled':data['beneficiaries'][0].update(age=13,care_before_13th_birthday_confirmed=False)
        elif id=='care_benefits_unverified':data['benefits_qualification_confirmed']=False
        elif id=='care_no_double_benefit':data['no_double_benefit_confirmed']=False
        elif id=='care_deemed_missing_ack':data['deemed_income_eligibility_confirmed']=False
        elif id=='saver_unverified_contributions':data['contributions_eligibility_confirmed']=False
        elif id=='saver_distribution_window':data['distribution_window_and_exclusions_confirmed']=False
        elif id=='saver_mfj_nonjoint_distributionyear':data['all_distribution_years_joint']=False
        elif id=='saver_disabled_nonzero':data['enabled']=False
        elif id=='elderly_missing_ack':data['eligibility_confirmed']=False
        elif id=='elderly_benefits_unverified':data['nontaxable_benefits_confirmed']=False
        elif id=='elderly_disabled_no_physician':data['physician_statement_confirmed']=False
        elif id=='elderly_disability_not_in_income':context['disability_income_available']=0
        else:raise AssertionError('Unknown authored guard '+id)
        result=getattr(self.module,'calculate_'+module)(data,context)
        # A known ineligible careperson may be rejected or explicitly excluded;
        # qualification failures must not quietly retain a payable credit.
        if id=='care_age13_not_disabled' and result['can_compute']:
            self.assertEqual(result['nonrefundable_credit'],0)
        else:
            self.assertIs(result['can_compute'],False,result)
            self.assertTrue(result['blocking_issues'])

    def test_fixture_integrity(self):
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),FROZEN_SHA256)
        self.assertEqual(len(CASES),30)
        self.assertEqual(len(ORACLE['whole_returns']),5)
        self.assertEqual(len(ORACLE['scope_guards']),20)

    def test_saver_student_excluded_without_claiming_credit(self):
        data,context=self.adapted(CASES['saver_single_23750']);data['taxpayer_full_time_student']=True
        result=self.module.calculate_saver(data,context)
        self.assertEqual(result['nonrefundable_credit'],0)

    def test_saver_claimed_dependent_excluded(self):
        data,context=self.adapted(CASES['saver_single_23750']);context['taxpayer_can_be_claimed']=True
        self.assertEqual(self.module.calculate_saver(data,context)['nonrefundable_credit'],0)

    def test_elderly_mfs_cohabited_no_credit(self):
        data,context=self.adapted(CASES['elderly_mfs_apart']);data['mfs_lived_apart_entire_year']=False
        self.assertIs(self.module.calculate_elderly(data,context)['can_compute'],False)

    def test_invalid_schema_rejected(self):
        for module,base in [('care','care_43001'),('saver','saver_single_23750'),('elderly','elderly_single')]:
            for field,value in [('enabled','true'),('unknown_field',True)]:
                with self.subTest(module=module,field=field):
                    data,context=self.adapted(CASES[base]);data[field]=value
                    with self.assertRaises(ValueError):getattr(self.module,'calculate_'+module)(data,context)

    def test_care_positive_expenses_require_provider_rows_even_with_ack(self):
        data,context=self.adapted(CASES['care_43001']);data['providers']=[]
        result=self.module.calculate_care(data,context)
        self.assertIs(result['can_compute'],False)
        self.assertTrue(result['blocking_issues'])

    def test_care_provider_identity_cannot_be_empty_with_ack(self):
        data,context=self.adapted(CASES['care_43001'])
        data['providers'][0].update(name='',address='',tin='')
        result=self.module.calculate_care(data,context)
        self.assertIs(result['can_compute'],False)
        self.assertTrue(result['blocking_issues'])

    def test_provider_identification_wrong_type_is_value_error(self):
        data,context=self.adapted(CASES['care_43001']);data['providers'][0]['name']=123
        with self.assertRaises(ValueError):self.module.calculate_care(data,context)

    def test_deemed_months_cannot_duplicate(self):
        data,context=self.adapted(CASES['care_student_deemed']);data['deemed_income_months'][1]['month']=1
        with self.assertRaises(ValueError):self.module.calculate_care(data,context)

    def test_household_box10_sum_cents_before_rounding(self):
        sys.path.insert(0,str(ROOT));import tax_engine as engine
        data=engine.default_return();data['filing_status']='mfj'
        for key in ('full_year_us_resident','filing_status_confirmed','all_income_reported','no_amt_preferences'):
            data['eligibility'][key]=True
        data['eligibility']['eitc_not_applicable']=True
        for owner,wage in [('taxpayer','60000'),('spouse','30000')]:
            row=deepcopy(engine.ROW_DEFAULTS['w2']);row.update(employer='Synthetic '+owner,owner=owner,wages=wage,
                social_security_wages=wage,medicare_wages=wage,dependent_care_benefits='1000.49',
                social_security_withholding=format((Decimal(wage)*Decimal('.062')).quantize(Decimal('.01')),'f'),
                medicare_withholding=format((Decimal(wage)*Decimal('.0145')).quantize(Decimal('.01')),'f'))
            data['w2'].append(row)
        data['care'],_=self.adapted(CASES['care_two_fsa5000'])
        for person in data['care']['beneficiaries']:person['qualified_expenses']='750'
        data['care']['providers'][0]['amount_paid']='1500'
        data['care']['benefits_expenses_incurred']='1500'
        result=engine.calculate_return(data)
        self.assertIs(result['can_prepare'],True,result['blocking_issues'])
        #Household2441 line12:1000.49+1000.49=2000.98=>2001.
        #Excluded1500;taxable line1e501;salary90000+501=>AGI90501.
        self.assertEqual(result['schedules']['form_2441']['form_lines']['12'],2001)
        self.assertEqual(result['additional_lines']['1e'],501)
        self.assertEqual(result['lines']['11b'],90501)

    def test_observed_ira_cannot_silently_omit_possible_saver_credit(self):
        sys.path.insert(0,str(ROOT));import tax_engine as engine
        data=engine.default_return()
        for key in ('full_year_us_resident','filing_status_confirmed','all_income_reported','no_amt_preferences'):
            data['eligibility'][key]=True
        data['eligibility']['eitc_not_applicable']=True
        row=deepcopy(engine.ROW_DEFAULTS['w2']);row.update(employer='Synthetic Payroll',wages='30000',federal_withholding='2000',
            social_security_wages='30000',medicare_wages='30000',social_security_withholding='1860',medicare_withholding='435')
        data['w2']=[row]
        data['ira'].update(enabled=True,traditional_taxpayer='7000',contributions_and_coverage_confirmed=True,
            compensation_and_magi_confirmed=True,no_rollovers_recharacterizations_or_prior_excess=True)
        r=engine.calculate_return(data)
        self.assertIs(r['can_prepare'],False)
        self.assertTrue(any('saver' in issue.lower() for issue in r['blocking_issues']))
        data['saver'].update(enabled=True,contributions_eligibility_confirmed=True,distribution_window_and_exclusions_confirmed=True)
        r=engine.calculate_return(data)
        self.assertIs(r['can_prepare'],True,r['blocking_issues'])
        self.assertEqual(r['lines']['20'],728)  #same previouslyfrozenIRA/Saveroracle
        self.assertEqual(r['lines']['24'],0)
        self.assertEqual(r['lines']['35a'],2000)

    def whole_return(self, case):
        sys.path.insert(0,str(ROOT));import tax_engine as engine
        data=engine.default_return();data['name']='Held-out '+case['id']
        for key in ('full_year_us_resident','filing_status_confirmed','all_income_reported','no_amt_preferences'):
            data['eligibility'][key]=True
        data['eligibility']['eitc_not_applicable']=True
        wage='30000' if case['id'].startswith('saver_') else '60000';wh='2000' if wage=='30000' else '6500'
        row=deepcopy(engine.ROW_DEFAULTS['w2']);row.update(employer='Synthetic Employer',wages=wage,federal_withholding=wh,
            social_security_wages=wage,medicare_wages=wage,social_security_withholding=format((Decimal(wage)*Decimal('.062')).quantize(Decimal('.01')), 'f'),
            medicare_withholding=format((Decimal(wage)*Decimal('.0145')).quantize(Decimal('.01')), 'f'))
        data['w2']=[row]
        if case['id'].startswith('care_'):
            dep=deepcopy(engine.ROW_DEFAULTS['dependents']);dep.update(name='Synthetic child',age=8,qualifying_child=True,valid_ssn=True,valid_tin=True,eligibility_confirmed=True)
            data['dependents']=[dep];data['care'],_=self.adapted(CASES['care_43001'])
        if case['id']=='care_education_ctc_single_w2':
            import tax_credits
            edu=tax_credits.default_inputs()['education'];edu.update(enabled=True,claim_eligibility_confirmed=True,no_foreign_magi_or_prior_credit_recapture=True)
            student=tax_credits.row_templates()['education.students'];student.update(student_id='taxpayer',name='Synthetic adult student',credit='aotc',institution_ein='12-3456789',tuition_and_required_fees='4000',
                half_time_degree_program=True,first_four_years_not_completed=True,no_felony_drug_conviction=True,
                eligible_institution_and_payment_period_confirmed=True,qualified_expenses_and_no_double_benefit_confirmed=True,
                dependency_claim_and_tin_confirmed=True,form_1098t_received_or_exception_confirmed=True)
            edu['students']=[student];data['education']=edu
        if case['id']=='saver_single_w2':
            data['saver'],_=self.adapted(CASES['saver_single_25501'])
        if case['id']=='saver_ira_deduction_tax_cap':
            data['ira'].update(enabled=True,traditional_taxpayer='7000',contributions_and_coverage_confirmed=True,compensation_and_magi_confirmed=True,no_rollovers_recharacterizations_or_prior_excess=True)
            data['saver'],_=self.adapted(CASES['saver_single_23750']);data['saver']['taxpayer_employer_contributions']='0'
        if case['id']=='elderly_forced_itemized':
            data['taxpayer']['age']=65;data['w2']=[]
            ir=deepcopy(engine.ROW_DEFAULTS['interest']);ir.update(payer='Synthetic Bank',taxable='10000',federal_withholding='500');data['interest']=[ir]
            data['retirement']['social_security']='1000';data['retirement']['taxable_amounts_confirmed']=True
            data['itemized'].update(charity='100',force_itemized=True);data['eligibility']['itemized_eligible']=True;data['itemized']['charity_cash_only']=True
            data['schedule_1a']['eligibility_confirmed']=True
            data['elderly_credit'],_=self.adapted(CASES['elderly_single'])
        result=engine.calculate_return(data)
        self.assertIs(result['can_prepare'],True,result['blocking_issues'])
        for line,expected in case['expected'].items():
            with self.subTest(line=line):self.assertEqual(result['lines'][line],expected)


def make_literal(case):
    def test(self):self.run_case(case)
    return test

def make_guard(case):
    def test(self):self.guard_case(case)
    return test

def make_whole(case):
    def test(self):self.whole_return(case)
    return test

for c in ORACLE['cases']:setattr(AdditionalAcceptance,'test_literal_'+c['id'],make_literal(c))
for c in ORACLE['scope_guards']:setattr(AdditionalAcceptance,'test_guard_'+c['id'],make_guard(c))
for c in ORACLE['whole_returns']:setattr(AdditionalAcceptance,'test_whole_'+c['id'],make_whole(c))

if __name__=='__main__':unittest.main()
