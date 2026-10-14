"""Independent IRS2025 raw2a/2b/2d integration and rejected combinations."""
from pathlib import Path
import json,sys,unittest
from decimal import Decimal, ROUND_HALF_UP
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE))
import tax_engine as engine

CASES=json.loads((BASE/'fixtures/special_dividend_2025.json').read_text())['cases']

def prepared(case):
    data=engine.default_return();data['filing_status']=case['filing_status']
    for key in ('full_year_us_resident','filing_status_confirmed','all_income_reported','no_amt_preferences','capital_gains_eligible','qualified_dividends_eligible','eitc_not_applicable'):
        data['eligibility'][key]=True
    if case['filing_status'] in ('hoh','qss'):data['eligibility'][case['filing_status']+'_eligible']=True
    data['niit']['eligibility_confirmed']=True
    wages=Decimal(case['wages']);ss=min(wages,Decimal(176100))
    medicare=(wages*Decimal('.0145')+max(Decimal(0),wages-Decimal(200000))*Decimal('.009')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    data['w2']=[dict(engine.ROW_DEFAULTS['w2'],employer='Synthetic W2 payer',wages=case['wages'],social_security_wages=str(ss),social_security_withholding=str((ss*Decimal('.062')).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)),medicare_wages=case['wages'],medicare_withholding=str(medicare))]
    data['dividends']=case['dividends'];return data

class SpecialDividendTests(unittest.TestCase):

    def test_legacy_default_fingerprint_is_preserved(self):
        import hashlib,income_preparation
        legacy='{"capital_gain_distributions":"0.00","federal_withholding":"0.00","ordinary":"200.00","payer":"Synthetic payer","qualified":"0.00"}'
        row=dict(engine.ROW_DEFAULTS['dividends'],payer='Synthetic payer',ordinary='200')
        self.assertEqual(income_preparation.fingerprint('dividends',row),hashlib.sha256(legacy.encode()).hexdigest())

    def test_150_independent_full_return_line16_cases(self):
        for case in CASES:
            with self.subTest(id=case['id']):
                result=engine.calculate_return(prepared(case))
                self.assertEqual(result['lines']['15'],case['expected_1040_15'])
                self.assertEqual(result['lines']['16'],case['expected_1040_16'])
                self.assertEqual(result['schedules']['schedule_d_tax_worksheet']['form_lines']['47'],case['expected_1040_16'])
                self.assertEqual(result['lines']['7a'],engine.dollars(case['expected_raw_sum'][0]))
                amt=result['schedules']['form_6251']
                if amt['special_distribution_zero_liability_proved']:
                    self.assertTrue(result['can_prepare'],result['blocking_issues'])
                else:
                    self.assertFalse(result['can_prepare'])
                    self.assertTrue(any('PartIII' in item for item in result['blocking_issues']))
    def test_box_components_are_not_added_twice(self):
        case=next(c for c in CASES if c['profile']=='mixed' and c['filing_status']=='single' and c['expected_1040_15']==100000)
        result=engine.calculate_return(prepared(case))
        self.assertEqual(result['lines']['7a'],25000)
        self.assertEqual(result['schedules']['schedule_d']['collectibles_28_gain'],10000)
        self.assertEqual(result['schedules']['schedule_d']['unrecaptured_1250_gain'],10000)
    def test_valid_raw_components_can_round_to_one_dollar_over_total(self):
        case=dict(CASES[0],wages='60749')
        data=prepared(case);data['dividends']=[dict(engine.ROW_DEFAULTS['dividends'],capital_gain_distributions='1.01',unrecaptured_1250_gain='0.50',collectibles_gain='0.51',special_distribution_confirmed=True)]
        result=engine.calculate_return(data);worksheet=result['schedules']['schedule_d_tax_worksheet']['form_lines']
        self.assertEqual(result['lines']['15'],45000)
        self.assertEqual(worksheet['9'],1);self.assertEqual(worksheet['11'],2);self.assertEqual(worksheet['12'],1)
        self.assertTrue(result['can_prepare'],result['blocking_issues'])
    def test_unverified_components_block(self):
        data=prepared(CASES[0]);data['dividends']=[dict(row,special_distribution_confirmed=False) for row in data['dividends']]
        self.assertFalse(engine.calculate_return(data)['can_prepare'])
    def test_components_cannot_exceed_total(self):
        data=prepared(CASES[0]);data['dividends']=[dict(data['dividends'][0],capital_gain_distributions='1')]
        with self.assertRaisesRegex(ValueError,'Box2a'):engine.calculate_return(data)
    def test_unproved_trade_carryover_interest_combinations_block(self):
        for variant in ('trade','carryover','interest','foreign'):
            with self.subTest(variant=variant):
                data=prepared(CASES[0])
                if variant=='trade':data['capital_gains']=[dict(engine.ROW_DEFAULTS['capital_gains'],proceeds='100',cost_basis='50')]
                if variant=='carryover':data['carryovers']['capital_long']='1'
                if variant=='interest':data['itemized']['investment_interest']='1'
                if variant=='foreign':data['foreign_credit']['enabled']=True
                self.assertFalse(engine.calculate_return(data)['can_prepare'])
    def test_zero_default_rows_preserve_existing_ordinary_behavior(self):
        case=CASES[0];data=prepared(case);data['dividends']=[dict(engine.ROW_DEFAULTS['dividends'],ordinary='5000',qualified='5000',capital_gain_distributions='10000')]
        result=engine.calculate_return(data)
        self.assertNotIn('schedule_d_tax_worksheet',result['schedules'])
        self.assertNotIn('special_distribution_zero_liability_proved',result['schedules']['form_6251'])

if __name__=='__main__':unittest.main()
