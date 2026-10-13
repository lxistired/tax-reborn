"""Literal official2025 worksheet oracles, frozen before calculation functions ran."""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'fixtures' / 'credit_cases_2025.json'
FROZEN_SHA256 = 'e5a68f152b820f69a4455ce8b34a17ecc094b594018bfb29c6c1f497aff73629'
RAW = FIXTURE.read_bytes()
if hashlib.sha256(RAW).hexdigest() != FROZEN_SHA256:
    raise RuntimeError('Credit oracle changed after pre-execution freeze.')
ORACLE = json.loads(RAW)
CASES = {c['id']: c for c in ORACLE['cases']}


def adapted_data(case):
    data = deepcopy(case['data'])
    # IRS8889source review after freeze: clarify the same synthetic facts,
    # without changing any of the literal expected monetary values.
    if case['function'] == 'hsa':
        for account in data['accounts']:
            if account['distributions'] != '0':
                account['distribution_breakdown_confirmed'] = True
        if case['id'] == 'hsa_age65_distribution_exception':
            data['accounts'][0].update(distribution_exception_confirmed=True,
                                      distribution_timing_confirmed=True,
                                      exception_taxable_distributions='1000')  #alloccurred after65thbirthday
    return data


def nested(value, path):
    for part in path.split('.'):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def patch(value, change):
    target = value
    for part in change['path'][:-1]:
        target = target[int(part)] if isinstance(target, list) else target[part]
    part = change['path'][-1]
    target[int(part) if isinstance(target, list) else part] = deepcopy(change['value'])


class CreditAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('independent_credit_module', ROOT / 'tax_credits.py')
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def run_case(self, c):
        data, context = adapted_data(c), deepcopy(c['context'])
        before = deepcopy((data, context))
        result = getattr(self.module, 'calculate_' + c['function'])(data, context)
        self.assertIs(result['can_compute'], True, result['blocking_issues'])
        self.assertEqual(result['blocking_issues'], [])
        self.assertEqual((data, context), before)
        self.assertEqual(result['tax_year'], 2025)
        for key in ('deduction', 'other_income', 'additional_tax', 'nonrefundable_credit', 'refundable_credit', 'repayment'):
            self.assertIs(type(result[key]), int)
            self.assertGreaterEqual(result[key], 0)
        for path, expected in c['expected'].items():
            with self.subTest(path=path):
                self.assertEqual(nested(result, path), expected)
        self.assertTrue(result['trace'])
        self.assertTrue(all(t['source'].startswith('https://www.irs.gov/') for t in result['trace']))
        if c['function'] == 'education':
            self.assertLessEqual(result['nonrefundable_credit'], int(context['tax_liability_limit']))
        if c['function'] == 'marketplace':
            f = result['form_lines']
            self.assertFalse(result['refundable_credit'] and result['repayment'])
            self.assertEqual(f['line26'], max(0, f['line24'] - f['line25']))
            self.assertEqual(f['line27'], max(0, f['line25'] - f['line24']))
        return result

    def test_fixture_integrity(self):
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), FROZEN_SHA256)
        self.assertEqual(len(CASES), 28)
        self.assertEqual(len(ORACLE['blocking_cases']), 21)
        expected_hash = hashlib.sha256(json.dumps([c['expected'] for c in ORACLE['cases']], sort_keys=True).encode()).hexdigest()
        self.assertEqual(expected_hash, '32ea6e439bec7678e8db90300e7cdb0b3f07473f79b5cda0521f272907fdee65')

    def test_defaults_are_inactive(self):
        context = CASES['ira_uncovered_full']['context']
        for name, data in self.module.default_inputs().items():
            with self.subTest(module=name):
                result = getattr(self.module, 'calculate_' + name)(data, context)
                self.assertIs(result['can_compute'], True)
                self.assertTrue(all(result[k] == 0 for k in ['deduction', 'other_income', 'additional_tax', 'nonrefundable_credit', 'refundable_credit', 'repayment']))

    def test_disabled_data_cannot_hide_aptc(self):
        c = CASES['ptc_250percent_annual_net_credit']
        data = deepcopy(c['data']); data['enabled'] = False
        result = self.module.calculate_marketplace(data, c['context'])
        self.assertIs(result['can_compute'], False)

    def test_ptc_2025_table_quarter_rounding(self):
        # Literal values read separately from official8962Table2.
        for percent, figure in [(150, '0.0000'), (200, '0.0200'), (250, '0.0400'),
                                (301, '0.0603'), (303, '0.0608'), (353, '0.0733'),
                                (399, '0.0848'), (401, '0.0850')]:
            self.assertEqual(str(self.module._applicable_figure(percent)), figure)

    def test_age65_unverified_timing_blocks(self):
        c = CASES['hsa_age65_distribution_exception']
        data = adapted_data(c); data['accounts'][0]['distribution_timing_confirmed'] = False
        result = self.module.calculate_hsa(data, c['context'])
        self.assertIs(result['can_compute'], False)
        self.assertTrue(any('65thbirthday' in issue for issue in result['blocking_issues']))

    def test_age65_prebirthday_distribution_tax(self):
        c = CASES['hsa_age65_distribution_exception']
        data = adapted_data(c)
        data['accounts'][0].update(exception_taxable_distributions='0', distribution_exception_confirmed=False)
        result = self.module.calculate_hsa(data, c['context'])
        self.assertIs(result['can_compute'], True)
        self.assertEqual(result['other_income'], 1000)
        self.assertEqual(result['additional_tax'], 200)

    def test_hsa_mixed_distribution_exception(self):
        c = CASES['hsa_nonmedical_distribution']
        data = adapted_data(c)
        data['accounts'][0].update(exception_taxable_distributions='400', distribution_exception_confirmed=True)
        result = self.module.calculate_hsa(data, c['context'])
        self.assertIs(result['can_compute'], True)
        self.assertEqual(result['other_income'], 1000)
        self.assertEqual(result['additional_tax'], 120)  #20%*(1000-400)

    def test_timely_excess_correction_not_taxed_as_medical_distribution(self):
        c = CASES['hsa_current_excess6percent']
        data = adapted_data(c)
        data['accounts'][0].update(excess_contributions_withdrawn='700',
                                  distributions='750', excess_withdrawal_distributions='750',
                                  excess_withdrawal_and_income_reported_confirmed=True,
                                  distribution_breakdown_confirmed=True)
        result = self.module.calculate_hsa(data, c['context'])
        self.assertIs(result['can_compute'], True)
        self.assertEqual(result['deduction'], 4300)
        self.assertEqual(result['other_income'], 0)  #$50earningsalreadyseparatelyreportedperconfirmation
        self.assertEqual(result['additional_tax'], 0)

    def test_annual_ptc_combines_cents_before_rounding(self):
        c = CASES['ptc_250percent_annual_net_credit']
        data = deepcopy(c['data'])
        for row in data['months']:
            row.update(enrollment_premium='600.49', slcsp_premium='650.49')
        result = self.module.calculate_marketplace(data, c['context'])
        self.assertIs(result['can_compute'], True)
        self.assertEqual(result['form_lines']['line11_annual']['enrollment_premium'], 7206)
        self.assertEqual(result['form_lines']['line11_annual']['slcsp_premium'], 7806)
        self.assertEqual(result['form_lines']['line24'], 6300)  #7806-1506
        self.assertEqual(result['refundable_credit'], 300)  #6300-6000

    def test_annual_ptc_cents_change_is_not_unchanged_premium(self):
        c = CASES['ptc_250percent_annual_net_credit']
        data = deepcopy(c['data'])
        data['months'][0]['enrollment_premium'] = '600.10'
        result = self.module.calculate_marketplace(data, c['context'])
        self.assertIs(result['can_compute'], False)

    def test_ptc_negative_required_filer_dependent_magi(self):
        c = CASES['ptc_250percent_annual_net_credit']
        data, context = deepcopy(c['data']), deepcopy(c['context'])
        data['dependents_magi'] = '-5000'
        context.update(household_agi='40000', tax_family_size=2)
        result = self.module.calculate_marketplace(data, context)
        self.assertIs(result['can_compute'], True)
        self.assertEqual(result['form_lines']['line3'], 35000)
        self.assertEqual(result['form_lines']['line5'], 171)  #floor35000/20440*100
        self.assertEqual(result['form_lines']['line8a'], 294)  #35000*.0084
        self.assertEqual(result['refundable_credit'], 1200)  #premium7200limiting;APT6000

    def test_married_hsa_cannot_guess_spouse_coverage(self):
        c = CASES['hsa_self_limit_employer']
        data, context = adapted_data(c), deepcopy(c['context'])
        context['filing_status'] = 'mfj'
        result = self.module.calculate_hsa(data, context)
        self.assertIs(result['can_compute'], False)


    def test_aotc_combined_expenses_sum_cents_before_rounding(self):
        c = CASES['aotc_full_and_tax_limit']
        data = adapted_data(c); context = deepcopy(c['context'])
        data['students'][0].update(tuition_and_required_fees='1500.49', course_materials='1501.49', tax_free_assistance='0', expenses_used_elsewhere='0')
        context['tax_liability_limit'] = 5000
        result = self.module.calculate_education(data, context)
        #Official same-line rounding:3001.98=>3002;2000+.25*1002=>2251.
        self.assertEqual(result['form_lines']['students'][0]['adjusted_qualified_expenses'], 3002)
        self.assertEqual(result['form_lines']['line7'], 2251)
        self.assertEqual(result['refundable_credit'], 900)
        self.assertEqual(result['nonrefundable_credit'], 1351)

    def test_llc_combined_expenses_sum_cents_before_rounding(self):
        c = CASES['llc_external_books_excluded']
        data = adapted_data(c); context = deepcopy(c['context'])
        data['students'][0].update(tuition_and_required_fees='1001.49', course_materials='1001.49', materials_paid_to_institution_required=True, tax_free_assistance='0', expenses_used_elsewhere='0')
        context['magi'] = 60000; context['tax_liability_limit'] = 5000
        result = self.module.calculate_education(data, context)
        #2002.98=>2003;*.20=>400.60=>401.
        self.assertEqual(result['form_lines']['students'][0]['adjusted_qualified_expenses'], 2003)
        self.assertEqual(result['nonrefundable_credit'], 401)


def case_test(c):
    def test(self): self.run_case(c)
    test.__doc__ = c['manual_workings']
    return test


def guard_test(g):
    def test(self):
        base = CASES[g['base']]
        value = {'data': adapted_data(base), 'context': deepcopy(base['context'])}
        for change in g['patches']: patch(value, change)
        before = deepcopy(value)
        function = getattr(self.module, 'calculate_' + base['function'])
        if g['mode'] == 'reject':
            with self.assertRaises(ValueError): function(value['data'], value['context'])
        else:
            result = function(value['data'], value['context'])
            self.assertIs(result['can_compute'], False, g['reason'])
            self.assertTrue(result['blocking_issues'])
        self.assertEqual(value, before)
    test.__doc__ = g['reason']
    return test


for CASE in ORACLE['cases']:
    setattr(CreditAcceptance, 'test_oracle_' + CASE['id'], case_test(CASE))
for GUARD in ORACLE['blocking_cases']:
    setattr(CreditAcceptance, 'test_guard_' + GUARD['id'], guard_test(GUARD))


class IntegratedCreditAcceptance(unittest.TestCase):
    """Whole-return literals independently calculated before integrated engine runs."""
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT))
        spec = importlib.util.spec_from_file_location('integrated_credit_return_engine', ROOT / 'tax_engine.py')
        cls.engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.engine)
        cls.base = json.loads((ROOT / 'fixtures' / 'independent_cases.json').read_text())['supported_cases'][0]['input']

    def data(self, *case_ids, wages='60000', withholding='6500'):
        data = deepcopy(self.base)
        data['taxpayer']['age'] = 40
        data['w2'][0].update(wages=wages, federal_withholding=withholding,
                             social_security_wages=wages, medicare_wages=wages)
        # Construct internally consistent synthetic payroll boxes. A lower wage
        # must not retain the original$60000case's Medicare withholding$870.
        wage = Decimal(wages)
        data['w2'][0]['social_security_withholding'] = str((wage * Decimal('.062')).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
        data['w2'][0]['medicare_withholding'] = str((wage * Decimal('.0145')).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
        for case_id in case_ids:
            case = CASES[case_id]
            data[case['function']] = adapted_data(case)
        return data

    def assert_lines(self, data, expected):
        before = deepcopy(data)
        result = self.engine.calculate_return(data)
        self.assertIs(result['can_prepare'], True, result['blocking_issues'])
        self.assertEqual(data, before)
        for line, amount in expected.items():
            with self.subTest(line=line): self.assertEqual(result['lines'][line], amount)
        return result

    def test_ira_deduction_into_complete_return(self):
        #53000AGI-15750=37250; independently read IRS Single row4235.
        self.assert_lines(self.data('ira_uncovered_full'),
                          {'10': 7000, '11a': 53000, '15': 37250, '16': 4235,
                           '24': 4235, '33': 6500, '35a': 2265})

    def test_hsa_deduction_into_complete_return(self):
        #57000AGI-15750=41250; IRS Single row4715.
        self.assert_lines(self.data('hsa_self_limit_employer'),
                          {'10': 3000, '11a': 57000, '15': 41250, '16': 4715,
                           '24': 4715, '35a': 1785})

    def test_aotc_nonref_and_refundable_return_lines(self):
        #Regular5075-nonref1500=3575; payments6500+refund1000=7500.
        self.assert_lines(self.data('aotc_full_and_tax_limit'),
                          {'16': 5075, '20': 1500, '24': 3575, '29': 1000,
                           '32': 1000, '33': 7500, '35a': 3925})

    def test_ira_hsa_aotc_combined_return(self):
        #AGI60000-7000-3000=50000; TI34250/table3875;
        #3875-1500=2375;6500+1000-2375=5125refund.
        self.assert_lines(self.data('ira_uncovered_full', 'hsa_self_limit_employer', 'aotc_full_and_tax_limit'),
                          {'10': 10000, '11a': 50000, '15': 34250, '16': 3875,
                           '20': 1500, '24': 2375, '29': 1000, '33': 7500, '35a': 5125})

    def test_ptc_return_credit_not_income(self):
        #TI37650-15750=21900/table2393; PTC294 ispayment31.
        self.assert_lines(self.data('ptc_250percent_annual_net_credit', wages='37650', withholding='5000'),
                          {'11a': 37650, '15': 21900, '16': 2393, '24': 2393,
                           '31': 294, '33': 5294, '35a': 2901})

    def test_ptc_repayment_income_tax_line17(self):
        #Sameordinary2393+975caprepayment=3368,6500-3368=3132.
        self.assert_lines(self.data('ptc_repayment_cap_250percent', wages='37650'),
                          {'16': 2393, '17': 975, '24': 3368, '31': 0, '35a': 3132})

    def test_hsa_taxable_distribution_and_additional_tax(self):
        #61000AGI,TI45250/table5195; add20%tax200=>5395.
        self.assert_lines(self.data('hsa_nonmedical_distribution'),
                          {'8': 1000, '11a': 61000, '15': 45250, '16': 5195,
                           '23': 200, '24': 5395, '35a': 1105})

    def test_hsa_current_excess_excise_return(self):
        #AGI55700,TI39950/table4559; excise42 =>total4601.
        self.assert_lines(self.data('hsa_current_excess6percent'),
                          {'10': 4300, '11a': 55700, '15': 39950, '16': 4559,
                           '23': 42, '24': 4601, '35a': 1899})

    def test_mixed_1099_withholding_rounded_once(self):
        data = self.data()
        data['interest'] = [{'payer': 'Synthetic bank', 'taxable': '3000', 'tax_exempt': '0', 'federal_withholding': '500.49'}]
        data['dividends'] = [{'payer': 'Synthetic broker', 'ordinary': '3000', 'qualified': '0', 'capital_gain_distributions': '0', 'federal_withholding': '500.49'}]
        result = self.engine.calculate_return(data)
        self.assertIs(result['can_prepare'], True, result['blocking_issues'])
        self.assertEqual(result['lines']['25b'], 1001)  #500.49+500.49=1000.98

if __name__ == '__main__':
    unittest.main(verbosity=2)
