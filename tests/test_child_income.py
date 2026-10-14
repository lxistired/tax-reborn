"""Independent synthetic tests grounded in the printed 2025 IRS Form 8814.

Literal expected amounts are authored from IRS line instructions, never from
the App or vendor graph. Vendor resources, tables and private paths are absent.
"""
from copy import deepcopy
import json
import unittest

import tax_child_income as child


def row(**values):
    result = child.row_templates()['child_income_election.children']
    result.update(name='Synthetic Child', ssn='111-11-1111', birth_date='2015-07-01')
    for key in child.CONFIRMATIONS:
        result[key] = True
    result.update(qualified_eligibility_confirmed=True, ordinary_capital_distribution_confirmed=True)
    result.update(values)
    return result


def run(*children):
    return child.calculate({'enabled': True, 'children': list(children)})


class Form8814Tests(unittest.TestCase):
    def test_amount_boundaries_from_printed_form(self):
        cases = [
            ('1350', 0, 0, None), ('1351', 0, 0, None),
            ('1354', 0, 0, None), ('1355', 1, 0, None),
            ('2694', 134, 0, None), ('2695', 135, 0, None),
            ('2699', 135, 0, None), ('2700', 135, 0, None),
            ('2701', 135, 1, 1), ('4000', 135, 1300, 1300),
            ('13499', 135, 10799, 10799)]
        for interest, tax, ordinary, residual in cases:
            with self.subTest(interest=interest):
                result = run(row(taxable_interest=interest))
                self.assertTrue(result['can_compute'], result['blocking_issues'])
                self.assertEqual(result['additional_tax'], tax)
                self.assertEqual(result['parent_ordinary_other_income'], ordinary)
                self.assertEqual(result['form_lines']['children'][0]['12'], residual)

    def test_independent_allocation_examples(self):
        # interest, ordinary (including qualified), qualified, capital,
        # [line4, line6, line7, line8, line9, line10, line11, line12, line15]
        cases = [
            ('2000', '1000', '600', '1000', [4000, 1300, '.150', '.250', 195, 325, 520, 780, 135]),
            ('3000', '1000', '1000', '1000', [5000, 2300, '.200', '.200', 460, 460, 920, 1380, 135]),
            ('0', '4000', '4000', '0', [4000, 1300, '1.000', '.000', 1300, 0, 1300, 0, 135]),
            ('0', '0', '0', '4000', [4000, 1300, '.000', '1.000', 0, 1300, 1300, 0, 135]),
            ('3000', '1000', '0', '0', [4000, 1300, None, None, None, None, 0, 1300, 135]),
            ('0', '2190', '2190', '610', [2800, 100, '.782', '.218', 78, 22, 100, 0, 135]),
            ('8000', '3000', '1000', '1000', [12000, 9300, '.083', '.083', 772, 772, 1544, 7756, 135]),
            ('0', '3000', '1500', '3000', [6000, 3300, '.250', '.500', 825, 1650, 2475, 825, 135])]
        for interest, dividends, qualified, capital, expected in cases:
            with self.subTest(expected=expected):
                result = run(row(taxable_interest=interest, ordinary_dividends=dividends,
                                 qualified_dividends=qualified, capital_gain_distributions=capital))
                self.assertTrue(result['can_compute'], result['blocking_issues'])
                form = result['form_lines']['children'][0]
                actual = [form[key] for key in ('4', '6', '7', '8', '9', '10', '11', '12', '15')]
                expected = [value if not isinstance(value, str) or not value.startswith('.') else '0'+value for value in expected]
                self.assertEqual(actual, expected)
                self.assertEqual(result['parent_qualified_dividends'], expected[4] or 0)
                self.assertEqual(result['parent_capital_gain'], expected[5] or 0)
                self.assertEqual(result['parent_ordinary_other_income'], expected[7])

    def test_parent_investment_income_character(self):
        result = run(row(taxable_interest='2000', tax_exempt_interest='900', ordinary_dividends='1000',
                         qualified_dividends='600', capital_gain_distributions='1000'))
        self.assertEqual(result['niit_other_investment_income'], 780)
        self.assertEqual(result['investment_interest_other_income'], 780)
        self.assertEqual(result['eitc_other_investment_income'], 1680)
        self.assertEqual(result['parent_qualified_dividends'], 195)
        self.assertEqual(result['parent_capital_gain'], 325)
        # Child line1b is an EIC investment addback; it is not parent1040line2a.
        self.assertEqual(result['form_lines']['children'][0]['1b'], 900)

    def test_multiple_child_total_and_checkboxes(self):
        result = run(row(taxable_interest='4000'), row(name='Second Child', ssn='222-22-2222',
                     taxable_interest='2000', ordinary_dividends='1000', qualified_dividends='600',
                     capital_gain_distributions='1000'))
        self.assertTrue(result['can_compute'])
        self.assertEqual(result['additional_tax'], 270)
        self.assertEqual(result['parent_ordinary_other_income'], 2080)
        self.assertEqual(result['parent_qualified_dividends'], 195)
        self.assertEqual(result['parent_capital_gain'], 325)
        self.assertTrue(all(x['multiple_children'] for x in result['form_lines']['children']))

    def test_year_end_age_and_january_first(self):
        cases = [('2007-01-02', False, True), ('2007-01-01', False, False),
                 ('2007-01-01', True, True), ('2002-01-02', True, True),
                 ('2002-01-01', True, False), ('2006-07-01', False, False),
                 ('2006-07-01', True, True), ('2001-07-01', True, False)]
        for born, student, eligible in cases:
            with self.subTest(born=born, student=student):
                result = run(row(birth_date=born, full_time_student=student, taxable_interest='4000'))
                self.assertEqual(result['can_compute'], eligible)
                if not eligible: self.assertEqual(result['additional_tax'], 0)

    def test_all_factual_confirmations_default_to_block(self):
        for key in child.CONFIRMATIONS + ('qualified_eligibility_confirmed', 'ordinary_capital_distribution_confirmed'):
            with self.subTest(key=key):
                result = run(row(taxable_interest='2000', ordinary_dividends='1000',
                                qualified_dividends='600', capital_gain_distributions='1000', **{key: False}))
                self.assertFalse(result['can_compute'])
                self.assertEqual(result['additional_tax'], 0)
                self.assertEqual(result['parent_ordinary_other_income'], 0)

    def test_threshold_rejects_original_and_rounded_income(self):
        for value in ('13500', '15000', '13499.99'):
            with self.subTest(value=value): self.assertFalse(run(row(taxable_interest=value))['can_compute'])

    def test_completed_line_rounding_preserves_entered_cents(self):
        result = run(row(taxable_interest='2000.49', ordinary_dividends='1000.49',
                         qualified_dividends='600.49', capital_gain_distributions='1000.49'))
        form = result['form_lines']['children'][0]
        self.assertTrue(result['can_compute'])
        self.assertEqual(form['4'], 4000)
        self.assertEqual(form['source_totals']['taxable_interest'], '2000.49')
        self.assertEqual(result['parent_ordinary_other_income'], 780)

    def test_precision_conflict_cannot_report_negative_other_income(self):
        result = run(row(ordinary_dividends='2', qualified_dividends='2', capital_gain_distributions='3998'))
        self.assertFalse(result['can_compute'])
        self.assertTrue(any('higher-precision' in issue for issue in result['blocking_issues']))

    def test_invalid_and_incomplete_records(self):
        cases = [row(name='', taxable_interest='4000'), row(ssn='abc', taxable_interest='4000'),
                 row(birth_date='', taxable_interest='4000'), row(ordinary_dividends='1000', qualified_dividends='1001')]
        for item in cases: self.assertFalse(run(item)['can_compute'])
        self.assertFalse(run(row(taxable_interest='4000'), row(taxable_interest='4000'))['can_compute'])
        self.assertFalse(child.calculate({'enabled': True, 'children': []})['can_compute'])
        self.assertFalse(child.calculate({'enabled': False, 'children': [row()]})['can_compute'])

    def test_strict_schema_and_saved_json_roundtrip(self):
        for item in (row(taxable_interest=4.0), row(taxable_interest='-1'), row(birth_date='2025-02-30'),
                     row(full_time_student=1), dict(row(), unexpected='1')):
            with self.assertRaises(ValueError): run(item)
        document = child.default_inputs()
        document['child_income_election'] = {'enabled': True, 'children': [row(taxable_interest='4000.25')]}
        child.normalize_extra(document)
        saved = json.loads(json.dumps(document))
        child.normalize_extra(saved)
        self.assertEqual(saved, document)
        self.assertEqual(child.calculate(saved['child_income_election']), child.calculate(document['child_income_election']))

    def test_metadata_contract(self):
        fields = child.ui_schema()['ui_fields']
        self.assertIn('child_income_election.children.*.eligible_parent_confirmed', fields)
        self.assertIn('child_income_election.children.*.no_private_activity_bond_interest_confirmed', fields)
        self.assertEqual(fields['child_income_election.children.*.full_time_student']['type'], 'boolean')
        self.assertEqual(child.default_inputs()['child_income_election']['enabled'], False)


if __name__ == '__main__': unittest.main()
