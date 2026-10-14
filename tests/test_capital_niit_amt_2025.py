"""Independent boundary cases and component rows for official NIIT export."""
import unittest
import tax_engine
import tax_extended
from capital_niit_amt_qa import check_app


class CapitalNIITAMT(unittest.TestCase):
    def test_eighteen_independent_high_income_and_threshold_returns(self):
        report = check_app(tax_engine)
        self.assertEqual(report['cases'], 18)
        self.assertEqual(report['passed'], 18)

    def test_niit_printed_components_reconcile_with_rental_loss_and_deductions(self):
        context = {'filing_status': 'single', 'agi': 300000, 'interest': 1000,
            'ordinary_dividends': 2000, 'annuity': 3000, 'rental_income': -4000,
            'capital_gain_loss': -3000, 'other_investment_income': 6000,
            'itemized_salt': 1000, 'deducted_investment_interest': 500,
            'rental_prior_loss_unverified': False}
        inputs = dict(tax_extended.default_inputs()['niit'], eligibility_confirmed=True,
            deductions_confirmed=True, allocable_state_income_tax='1000')
        result = tax_extended.net_investment_tax(inputs, context)
        # Literal IRS2025 printed rows; no packet-renderer output is an oracle.
        self.assertEqual(result['form_lines'], {'1':1000,'2':2000,'3':3000,
            '4a':-4000,'4b':0,'4c':-4000,'5a':-3000,'5b':0,'5c':0,'5d':-3000,
            '6':0,'7':6000,'8':5000,'9a':500,'9b':1000,'9c':0,'9d':1500,
            '10':0,'11':1500,'12':3500,'13':300000,'14':200000,'15':100000,
            '16':3500,'17':133})

    def test_unverified_character_remains_blocked(self):
        from capital_niit_amt_qa import cases, return_for
        data = return_for(tax_engine, cases()[1])
        data['niit']['eligibility_confirmed'] = False
        result = tax_engine.calculate_return(data)
        self.assertFalse(result['can_prepare'])
        self.assertTrue(any('NIIT sources/exclusions' in x for x in result['blocking_issues']))


if __name__ == '__main__':
    unittest.main()
