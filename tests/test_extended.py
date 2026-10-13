"""Directed TY2025 oracles from IRS printed tables and form arithmetic.

Literal expectations below were calculated from source form lines, not captured
from the engine. Original independent acceptance fixtures remain separate.
IRS sources: i1040tt EIC table, p596 Worksheet1, f6251 PartsI-III,
f8960 lines1-17, f8582 PartsI-VIII, f4952 lines1-8, i1040gi rounding.
"""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import json
import sys
import unittest

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import tax_engine as engine
import tax_extended as x
import tax_credits


def ready():
    value=engine.default_return()
    for key in ('full_year_us_resident','filing_status_confirmed','all_income_reported','no_amt_preferences'):
        value['eligibility'][key]=True
    return value


def wage(amount):
    return dict(engine.ROW_DEFAULTS['w2'],employer='Synthetic',wages=amount,medicare_wages=amount,
                social_security_wages=str(min(Decimal(amount),Decimal('176100'))))


def eic_inputs():
    return dict(x.default_inputs()['eitc'],claim=True,eligibility_confirmed=True,main_home_us_half_year=True,
                not_qualifying_child_of_another=True,no_disallowed_claim_history=True)


def child():
    return dict(engine.ROW_DEFAULTS['dependents'],name='Synthetic child',eligibility_confirmed=True,
                eitc_qualifying_child=True,eitc_relationship_residency_confirmed=True,eitc_tiebreaker_confirmed=True)


def rental(**kwargs):
    row=dict(x.RENTAL_TEMPLATE,name='Synthetic rental',eligibility_confirmed=True,active_participation=True,
             ownership_at_least_10_percent=True,at_risk_confirmed=True,no_personal_use_or_substantial_services=True,
             depreciation_schedule_confirmed=True,prior_loss_active_participation=True,prior_loss_amount_confirmed=True,
             qbi_status_confirmed=True,same_amt_basis_and_depreciation=True)
    row.update(kwargs)
    return row


def niit_context(**kwargs):
    value={'filing_status':'single','agi':300000,'interest':0,'ordinary_dividends':0,'annuity':0,
           'rental_income':0,'capital_gain_loss':0,'itemized_salt':0,'deducted_investment_interest':0,
           'rental_prior_loss_unverified':False}
    value.update(kwargs)
    return value


def amt_context(**kwargs):
    value={'filing_status':'single','taxpayer_age':35,'agi':100000,'total_deductions':15750,
           'senior_deduction':0,'deduction_addback':15750,'preferred_income':0,
           'regular_ordinary_income':84250,'regular_tax':13455,'no_amt_preferences':True}
    value.update(kwargs)
    return value


class ExtendedTaxTests(unittest.TestCase):
    def test_exact_eic_primary_example_and_starred_limits(self):
        # Official example:$2,455 single, one child=>$842; special table end rows.
        for amount,status,n,expected in [(2455,'single',1,842),(26213,'mfj',0,1),(26214,'mfj',0,0),
                                       (19103,'single',0,0),(50433,'single',1,3),(50434,'single',1,0),
                                       (57309,'single',2,1),(57310,'single',2,0),(61554,'single',3,1),
                                       (64429,'mfj',2,3),(64430,'mfj',2,0),(68674,'mfj',3,3),(68675,'mfj',3,0)]:
            with self.subTest(amount=amount,status=status,n=n):
                self.assertEqual(x.eic_table(amount,status,n,engine.RULES),expected)
        self.assertEqual(len(engine.RULES['eic_table']),1375)
        end=0
        for row in engine.RULES['eic_table']:
            self.assertEqual(row[0],end);end=row[1]
        self.assertEqual(end,68700)

    def test_eic_agi_does_not_reduce_credit_before_phaseout(self):
        ctx={'filing_status':'single','taxpayer':ready()['taxpayer'],'spouse':ready()['spouse'],
             'dependents':[child()],'earned_income':2455,'agi':1000,'investment_income':0}
        result=x.earned_income_credit(eic_inputs(),ctx,engine.RULES)
        self.assertEqual(result['credit'],842)
        self.assertFalse(result['blocking_issues'])
        ctx.update(earned_income=25000,agi=50433)
        result=x.earned_income_credit(eic_inputs(),ctx,engine.RULES)
        self.assertEqual(result['credit'],3)
        self.assertEqual(result['form_lines']['agi_table_credit'],3)

    def test_eic_eligibility_child_review_investment_and_separation(self):
        ctx={'filing_status':'single','taxpayer':ready()['taxpayer'],'spouse':ready()['spouse'],
             'dependents':[dict(child(),eitc_qualifying_child=False)],'earned_income':2455,'agi':2455,'investment_income':0}
        self.assertTrue(x.earned_income_credit(eic_inputs(),ctx,engine.RULES)['blocking_issues'])
        ctx['dependents'][0]['eitc_status_reviewed']=True
        self.assertFalse(x.earned_income_credit(eic_inputs(),ctx,engine.RULES)['blocking_issues'])
        ctx['dependents']=[child()];ctx['investment_income']=11951
        self.assertEqual(x.earned_income_credit(eic_inputs(),ctx,engine.RULES)['credit'],0)
        ctx['investment_income']=0;ctx['filing_status']='mfs'
        self.assertEqual(x.earned_income_credit(eic_inputs(),ctx,engine.RULES)['credit'],0)
        data=eic_inputs();data['mfs_qualifying_separation']=True
        self.assertEqual(x.earned_income_credit(data,ctx,engine.RULES)['credit'],842)

    def test_eic_whole_return_and_annuity_is_not_worksheet_investment(self):
        data=ready();data['w2']=[wage('2455')];data['dependents']=[child()];data['eitc']=eic_inputs()
        result=engine.calculate_return(data)
        self.assertTrue(result['can_prepare'],result['blocking_issues'])
        self.assertEqual(result['lines']['27a'],842);self.assertEqual(result['lines']['35a'],842)
        data['taxpayer']['age']=62;data['retirement'].update(annuity_gross='12000',annuity_taxable='12000',annuity_taxable_amounts_confirmed=True)
        # p596 investment worksheet excludes pension/annuity;AGI14455 below child phaseout.
        result=engine.calculate_return(data)
        self.assertTrue(result['can_prepare'],result['blocking_issues']);self.assertEqual(result['lines']['27a'],842)

    def test_eic_child_without_ssn_does_not_disqualify_other_children(self):
        ctx={'filing_status':'single','taxpayer':ready()['taxpayer'],'spouse':ready()['spouse'],
             'dependents':[child(),dict(child(),valid_ssn=False)],'earned_income':2455,'agi':2455,'investment_income':0}
        result=x.earned_income_credit(eic_inputs(),ctx,engine.RULES)
        self.assertEqual(result['credit'],842);self.assertEqual(result['qualifying_children'],1)
        self.assertEqual(result['excluded_children'][0]['index'],2)
        ctx['dependents']=[dict(child(),valid_ssn=False)]
        result=x.earned_income_credit(eic_inputs(),ctx,engine.RULES)
        self.assertEqual(result['credit'],189);self.assertEqual(result['qualifying_children'],0)

    def test_niit_annuity_capital_loss_deductions_and_thresholds(self):
        data=dict(x.default_inputs()['niit'],eligibility_confirmed=True)
        result=x.net_investment_tax(data,niit_context(annuity=100000,capital_gain_loss=-3000))
        self.assertEqual(result['form_lines']['12'],97000);self.assertEqual(result['tax'],3686)
        data.update(allocable_state_income_tax='5000',deductions_confirmed=True)
        result=x.net_investment_tax(data,niit_context(interest=10000,itemized_salt=5000,deducted_investment_interest=2000))
        self.assertEqual(result['tax'],114)
        for status,agi,expected in [('single',200001,0),('mfj',260000,380),('qss',260000,380),('mfs',130000,190)]:
            data['allocable_state_income_tax']='0'
            self.assertEqual(x.net_investment_tax(data,niit_context(filing_status=status,agi=agi,interest=10000))['tax'],expected)
        data['allocable_state_income_tax']='1'
        with self.assertRaises(ValueError):x.net_investment_tax(data,niit_context(interest=10000))

    def test_niit_requires_character_for_prior_rental_loss(self):
        data=dict(x.default_inputs()['niit'],eligibility_confirmed=True)
        result=x.net_investment_tax(data,niit_context(interest=50000,rental_income=-10000,rental_prior_loss_unverified=True))
        self.assertEqual(result['tax'],1520);self.assertTrue(result['blocking_issues'])

    def test_investment_interest_4952_no_preferred_gain_election(self):
        data=dict(x.default_inputs()['niit'],investment_interest_eligible=True,investment_interest_carryover='500',carryover_confirmed=True)
        ctx={'paid':10000,'interest':2000,'ordinary_dividends':4000,'qualified_dividends':3000,
             'annuity':0,'net_gain':5000,'preferred_gain':5000}
        result=x.investment_interest(data,ctx)
        self.assertEqual(result['deduction'],3000);self.assertEqual(result['carryout'],7500)
        self.assertFalse(result['blocking_issues'])

    def test_actual_niit_whole_return_annuity(self):
        data=ready();data['taxpayer']['age']=62;data['w2']=[wage('200000')]
        data['retirement'].update(annuity_gross='100000',annuity_taxable='100000',annuity_taxable_amounts_confirmed=True)
        data['niit']['eligibility_confirmed']=True
        result=engine.calculate_return(data)
        self.assertTrue(result['can_prepare'],result['blocking_issues']);self.assertEqual(result['lines']['23'],3800)
        self.assertEqual(result['schedules']['form_8960']['form_lines']['3'],100000)

    def test_amt_iso_real_regular_table_and_total_liability(self):
        data=ready();data['w2']=[wage('100000')];data['amt'].update(iso_adjustment='200000',eligibility_confirmed=True)
        result=engine.calculate_return(data)
        self.assertTrue(result['can_prepare'],result['blocking_issues'])
        # Printed tax table84250..84300=>13455;6251(300000-88100)*26%=55094.
        self.assertEqual(result['lines']['16'],13455);self.assertEqual(result['lines']['17'],41639)
        self.assertEqual(result['lines']['24'],55094)
        self.assertEqual(result['schedules']['form_6251']['form_lines']['4'],300000)

    def test_amt_preferential_rates_use_regular_ordinary_space(self):
        data=dict(x.default_inputs()['amt'],iso_adjustment='100000',eligibility_confirmed=True)
        ctx=amt_context(agi=200000,total_deductions=20000,deduction_addback=20000,preferred_income=100000,regular_ordinary_income=80000,regular_tax=15000)
        result=x.alternative_minimum_tax(data,ctx,engine.RULES)
        self.assertEqual(result['form_lines']['18'],29094);self.assertEqual(result['form_lines']['31'],15000)
        self.assertEqual(result['form_lines']['9'],44094);self.assertEqual(result['tax'],29094)
        ctx['regular_ordinary_income']=20000;ctx['regular_tax']=25000
        result=x.alternative_minimum_tax(data,ctx,engine.RULES)
        self.assertEqual(result['form_lines']['23'],28350);self.assertEqual(result['form_lines']['31'],10748)
        self.assertEqual(result['form_lines']['9'],39842)

    def test_amt_mfs_addition_phaseout_senior_and_low_income(self):
        data=dict(x.default_inputs()['amt'],eligibility_confirmed=True)
        ctx=amt_context(filing_status='mfs',agi=1000000,total_deductions=0,deduction_addback=0,regular_tax=300000,regular_ordinary_income=1000000)
        result=x.alternative_minimum_tax(data,ctx,engine.RULES)
        self.assertEqual(result['form_lines']['4'],1024913);self.assertEqual(result['form_lines']['5'],0)
        self.assertEqual(result['form_lines']['7'],284585);self.assertEqual(result['tax'],0)
        ctx=amt_context(agi=100000,total_deductions=23750,senior_deduction=6000,deduction_addback=17750,taxpayer_age=70)
        self.assertEqual(x.alternative_minimum_tax(data,ctx,engine.RULES)['form_lines']['4'],100000)
        ctx=amt_context(agi=5000,total_deductions=15750,regular_tax=0,taxpayer_age=18,regular_ordinary_income=0)
        result=x.alternative_minimum_tax(data,ctx,engine.RULES)
        self.assertEqual(result['form_lines']['1b'],-10750);self.assertEqual(result['tax'],0)
        self.assertFalse(result['blocking_issues'])

    def test_smaller_itemized_election_can_reduce_amt(self):
        data=ready();data['w2']=[wage('100000')];data['amt'].update(iso_adjustment='200000',eligibility_confirmed=True)
        data['itemized'].update(charity='10000',charity_cash_only=True);data['eligibility']['itemized_eligible']=True
        standard=engine.calculate_return(data)
        data['itemized']['force_itemized']=True
        itemized=engine.calculate_return(data)
        self.assertTrue(itemized['can_prepare'],itemized['blocking_issues'])
        self.assertEqual(standard['lines']['24'],55094);self.assertEqual(itemized['lines']['24'],52494)
        self.assertEqual(itemized['summary']['deduction_type'],'itemized')

    def test_rental_allowance_phaseout_mfs_and_carryout(self):
        row=rental(rent='20000',other_expenses='50000')
        for income,allowance,carry in [(100000,25000,5000),(120000,15000,15000),(150000,0,30000)]:
            result=x.rental_return([row],{'filing_status':'single','magi_without_rentals':income,'mfs_lived_with_spouse':False})
            self.assertEqual(result['income'],-allowance);self.assertEqual(result['suspended_loss_carryout'],carry)
            self.assertFalse(result['blocking_issues'])
        result=x.rental_return([row],{'filing_status':'mfs','magi_without_rentals':60000,'mfs_lived_with_spouse':False})
        self.assertEqual(result['income'],-7500)
        self.assertEqual(x.rental_return([row],{'filing_status':'mfs','magi_without_rentals':60000,'mfs_lived_with_spouse':True})['income'],0)

    def test_rental_multi_property_netting_allocations_and_prior_losses(self):
        rows=[rental(other_expenses='20000'),rental(other_expenses='10000',active_participation=False),rental(rent='5000')]
        result=x.rental_return(rows,{'filing_status':'single','magi_without_rentals':120000,'mfs_lived_with_spouse':False})
        self.assertEqual(result['income'],-15000);self.assertEqual(result['suspended_loss_carryout'],10000)
        self.assertEqual([r['suspended_loss_carryout'] for r in result['properties']],[3333,6667,0])
        row=rental(rent='5000',prior_unallowed_loss='20000')
        result=x.rental_return([row],{'filing_status':'single','magi_without_rentals':130000,'mfs_lived_with_spouse':False})
        self.assertEqual(result['income'],-10000);self.assertEqual(result['suspended_loss_carryout'],5000)

    def test_rental_magi_se_half_addback_and_qbi(self):
        data=ready();data['w2']=[wage('60000')]
        data['businesses']=[dict(engine.ROW_DEFAULTS['businesses'],revenue='50000',active_business=True,expenses_eligible=True,at_risk_confirmed=True,qbi_eligible=True)]
        data['rentals']=[rental(other_expenses='25000')]
        result=engine.calculate_return(data)
        self.assertTrue(result['can_prepare'],result['blocking_issues'])
        self.assertEqual(result['schedules']['schedule_e']['magi'],110000)
        self.assertEqual(result['schedules']['schedule_e']['income'],-20000)
        self.assertEqual(result['lines']['11b'],86467)
        data=ready();data['w2']=[wage('60000')];data['rentals']=[rental(rent='30000',other_expenses='20000',qbi_eligible=True)]
        result=engine.calculate_return(data)
        self.assertEqual(result['lines']['8'],10000);self.assertEqual(result['lines']['13a'],2000)

    def test_rental_unconfirmed_and_special_qbi_carryin_block(self):
        row=rental(prior_unallowed_loss='1000',qbi_eligible=True)
        result=x.rental_return([row],{'filing_status':'single','magi_without_rentals':60000,'mfs_lived_with_spouse':False})
        self.assertTrue(any('QBI' in b for b in result['blocking_issues']))
        data=ready();data['rentals']=[{'rent':'10000'}]
        self.assertFalse(engine.calculate_return(data)['can_prepare'])

    def test_combined_line_cents_and_identity_packet_presence(self):
        data=ready();data['w2']=[wage('60000')]
        data['interest']=[{'taxable':'100','federal_withholding':'500.49'}]
        data['dividends']=[{'ordinary':'100','federal_withholding':'500.49'}]
        data['payments'].update(estimated='500.49',prior_year_credit='500.49')
        result=engine.calculate_return(data)
        self.assertEqual(result['lines']['25b'],1001);self.assertEqual(result['lines']['26'],1001)
        self.assertEqual(len(result['form_readiness']['missing_identity']),7)
        data['identity'].update(first_name=' Synthetic\n',last_name='Person',ssn='000-00-0000',address='1 Synthetic Rd',city='Test',state='NY',zip='00000')
        result=engine.calculate_return(data)
        self.assertEqual(result['identity']['first_name'],'Synthetic')
        self.assertEqual(result['form_readiness']['missing_identity'],[])
        self.assertFalse(result['form_readiness']['filing_packet_ready']);self.assertFalse(result['form_readiness']['electronic_filing'])
        data['filing_status']='mfj'
        self.assertEqual(len(engine.calculate_return(data)['form_readiness']['missing_identity']),3)
        data['identity']['ssn']='invalid'
        with self.assertRaises(ValueError):engine.calculate_return(data)

    def test_integrated_ira_hsa_adjustments_and_hsa_additional_tax(self):
        data=ready();data['w2']=[wage('60000')]
        data['ira'].update(enabled=True,traditional_taxpayer='7000',contributions_and_coverage_confirmed=True,
                           compensation_and_magi_confirmed=True,no_rollovers_recharacterizations_or_prior_excess=True)
        account=dict(tax_credits.row_templates()['hsa.accounts'],coverage=['self']*12,
                     personal_contributions='3000',employer_contributions='1300',distributions='5000',qualified_medical_expenses='4000',
                     first_day_coverage_and_eligibility_confirmed=True,no_prior_excess_or_testing_failure=True,
                     distribution_breakdown_confirmed=True,medical_expenses_confirmed=True)
        data['hsa'].update(enabled=True,accounts=[account])
        result=engine.calculate_return(data)
        self.assertTrue(result['can_prepare'],result['blocking_issues'])
        #8889income1000/deduction3000/tax200; IRA7000 =>AGI51000.
        self.assertEqual(result['lines']['8'],1000);self.assertEqual(result['lines']['10'],10000)
        self.assertEqual(result['lines']['11b'],51000);self.assertEqual(result['lines']['15'],35250)
        self.assertEqual(result['lines']['16'],3995);self.assertEqual(result['lines']['23'],200)
        self.assertEqual(result['lines']['24'],4195)

    def test_integrated_education_with_ctc_limit_and_refund(self):
        data=ready();data['filing_status']='mfj';data['w2']=[wage('50000')]
        data['eligibility']['eitc_not_applicable']=True
        data['dependents']=[dict(engine.ROW_DEFAULTS['dependents'],name='Child',eligibility_confirmed=True)]
        student=dict(tax_credits.row_templates()['education.students'],student_id='synthetic-taxpayer',name='Adult student',
                     tuition_and_required_fees='4000',institution_ein='00-0000000',half_time_degree_program=True,
                     first_four_years_not_completed=True,no_felony_drug_conviction=True,
                     eligible_institution_and_payment_period_confirmed=True,qualified_expenses_and_no_double_benefit_confirmed=True,
                     dependency_claim_and_tin_confirmed=True,form_1098t_received_or_exception_confirmed=True)
        data['education'].update(enabled=True,students=[student],claim_eligibility_confirmed=True,no_foreign_magi_or_prior_credit_recapture=True)
        result=engine.calculate_return(data)
        self.assertTrue(result['can_prepare'],result['blocking_issues'])
        #MFJ18500taxable=>1853table;1500AOTC leaves353CTC;1700ACTC+1000refAOTC.
        self.assertEqual(result['lines']['16'],1853);self.assertEqual(result['lines']['20'],1500)
        self.assertEqual(result['lines']['19'],353);self.assertEqual(result['lines']['28'],1700)
        self.assertEqual(result['lines']['29'],1000);self.assertEqual(result['lines']['24'],0)
        self.assertEqual(result['lines']['35a'],2700)

    def test_integrated_marketplace_credit_and_repayment_positions(self):
        data=ready();data['w2']=[wage('37650')]
        months=[dict(tax_credits.row_templates()['marketplace.months'],month=i,enrollment_premium='600',slcsp_premium='650',advance_credit='500',
                     coverage_eligible=True,premiums_paid_and_no_other_mec_confirmed=True) for i in range(1,13)]
        data['marketplace'].update(enabled=True,months=months,tax_family_and_household_income_confirmed=True,
                     coverage_and_slcsp_inputs_confirmed=True,no_qsehra_or_ichra=True,lawful_presence_confirmed=True,
                     no_shared_policy_or_marriage_allocation=True,annual_calculation=True,annual_calculation_eligible_confirmed=True)
        result=engine.calculate_return(data)
        self.assertTrue(result['can_prepare'],result['blocking_issues'])
        #250%FPL:37650*.04=1506;7800-1506=6294;APT6000=>credit294.
        self.assertEqual(result['lines']['16'],2393);self.assertEqual(result['lines']['31'],294)
        self.assertEqual(result['lines']['17'],0);self.assertEqual(result['lines']['37'],2099)
        for row in months:row['advance_credit']='750'
        result=engine.calculate_return(data)
        self.assertEqual(result['lines']['17'],975);self.assertEqual(result['lines']['31'],0)
        self.assertEqual(result['lines']['24'],3368);self.assertEqual(result['lines']['37'],3368)

    def test_new_schema_pure_json_no_floats_unknown_inputs(self):
        data=ready();data['w2']=[wage('60000')];original=deepcopy(data)
        self.assertEqual(engine.calculate_return(data),engine.calculate_return(json.loads(json.dumps(data))))
        self.assertEqual(data,original)
        for section,key in [('amt','iso_adjustment'),('niit','investment_interest_carryover')]:
            value=deepcopy(data);value[section][key]=1000.0
            with self.assertRaises(ValueError):engine.calculate_return(value)
        data['rentals']=[rental(nonexistent_field=True)]
        with self.assertRaises(ValueError):engine.calculate_return(data)
        schema=engine.capabilities()
        self.assertIn('hsa.accounts.*.distribution_exception_confirmed',schema['ui_fields'])
        self.assertIn('dependents.*.eitc_status_reviewed',schema['ui_fields'])

    def test_missing_w2_fica_boxes_cannot_silently_skip_taxes(self):
        data=ready();data['w2']=[dict(wage('300000'),medicare_wages='0')]
        result=engine.calculate_return(data)
        self.assertFalse(result['can_prepare']);self.assertTrue(any('Box5' in b for b in result['blocking_issues']))
        data['w2'][0].update(medicare_wages='300000',medicare_withholding='5250')
        result=engine.calculate_return(data)
        self.assertTrue(result['can_prepare'],result['blocking_issues']);self.assertEqual(result['lines']['23'],900)
        self.assertEqual(result['lines']['25c'],900)
        data=ready();data['w2']=[dict(wage('60000'),social_security_wages='0',social_security_tips='0')]
        data['businesses']=[dict(engine.ROW_DEFAULTS['businesses'],revenue='50000',active_business=True,expenses_eligible=True,at_risk_confirmed=True,qbi_eligible=True)]
        result=engine.calculate_return(data)
        self.assertFalse(result['can_prepare']);self.assertTrue(any('boxes3+7' in b for b in result['blocking_issues']))
        # Box7tips legitimately fill the SS wage base when Box3 itself is zero.
        data['w2'][0]['social_security_tips']='60000'
        self.assertTrue(engine.calculate_return(data)['can_prepare'])


if __name__=='__main__':unittest.main()
