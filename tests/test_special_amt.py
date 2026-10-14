"""Independent IRS2025 special distribution AMT full-return integration."""
from pathlib import Path
import json, sys, unittest, shutil, subprocess
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from test_special_dividends import prepared
import tax_engine as engine

CASES=json.loads((BASE/'fixtures/special_amt_2025.json').read_text())['cases']

def return_for(case):
    data=prepared(case)
    data['amt']['iso_adjustment']=case['iso_adjustment']
    data['amt']['special_distribution_same_basis_confirmed']=case['same_basis_confirmed']
    data['amt']['eligibility_confirmed']=True
    data['eligibility']['no_amt_preferences']=case['iso_adjustment']=='0'
    return data

class SpecialAMTTests(unittest.TestCase):
    def test_152_independent_full_returns_and_all_PartIII_lines(self):
        positive=0
        for case in CASES:
            with self.subTest(id=case['id']):
                r=engine.calculate_return(return_for(case))
                self.assertTrue(r['can_prepare'],r['blocking_issues'])
                amt=r['schedules']['form_6251'];want=case['expected']
                self.assertTrue(amt['special_distribution_full_partIII'])
                self.assertEqual(r['lines']['16'],want['regular_tax'])
                self.assertEqual(r['lines']['17'],want['AMT'])
                self.assertEqual(amt['tax'],want['AMT'])
                self.assertEqual(amt['form_lines']['4'],want['AMTI'])
                self.assertEqual(amt['form_lines']['5'],want['exemption'])
                self.assertEqual(amt['form_lines']['6'],want['taxable_AMTI'])
                self.assertEqual(amt['form_lines']['9'],want['tentative_minimum_tax'])
                self.assertEqual(amt['form_lines']['10'],want['regular_tax'])
                self.assertNotIn('special_distribution_AMT_TMT_not_computed',amt)
                for line,value in case['expected_partIII'].items():
                    self.assertEqual(amt['form_lines'][line],value,'6251 line'+line)
                self.assertIn('Form6251',r['summary']['schedules'])
                positive+=int(amt['tax']>0)
        self.assertEqual(positive,72)

    def test_prior_two_MFS_blocks_are_now_calculated(self):
        for case in CASES[-2:]:
            r=engine.calculate_return(return_for(case))
            self.assertTrue(r['can_prepare'],r['blocking_issues'])
            self.assertEqual(r['lines']['16'],37949)
            self.assertEqual(r['schedules']['form_6251']['form_lines']['9'],34743)
            self.assertEqual(r['lines']['17'],0)

    def test_different_AMT_basis_is_explicitly_blocked(self):
        data=return_for(CASES[0]);data['amt']['capital_gain_adjustment']='1'
        r=engine.calculate_return(data)
        self.assertFalse(r['can_prepare'])
        self.assertTrue(any('different AMT capital basis' in issue for issue in r['blocking_issues']))

    def test_same_basis_fact_defaults_false_and_old_review_cannot_substitute(self):
        self.assertFalse(engine.default_return()['amt']['special_distribution_same_basis_confirmed'])
        data=return_for(CASES[0]);data['amt'].pop('special_distribution_same_basis_confirmed')
        self.assertEqual(data['amt']['capital_gain_adjustment'],'0')
        self.assertTrue(data['dividends'][0]['special_distribution_confirmed'])
        r=engine.calculate_return(data)
        self.assertFalse(r['can_prepare'])
        self.assertTrue(any('requires separate confirmation' in issue for issue in r['blocking_issues']))

    def test_same_basis_schema_is_a_real_separate_checkbox_and_boolean_only(self):
        path='amt.special_distribution_same_basis_confirmed'
        field=engine.capabilities()['ui_fields'][path]
        self.assertEqual(field['type'],'boolean')
        self.assertIn('same capital basis',field['label'])
        self.assertIn('zero adjustment amount alone',field['help'])
        self.assertTrue(any(m['id']=='amt' for m in engine.capabilities()['ui_modules']))
        data=return_for(CASES[0]);data['amt']['special_distribution_same_basis_confirmed']='true'
        with self.assertRaisesRegex(ValueError,'must be boolean'):engine.calculate_return(data)

    @unittest.skipUnless(shutil.which('node'),'Node is needed only for browser renderer QA')
    def test_actual_AMT_interview_renders_and_changes_the_same_basis_checkbox(self):
        schema={'default_return':engine.default_return(),'capabilities':engine.capabilities()}
        process=subprocess.run(['node',str(BASE/'tests/check_same_basis_browser.cjs')],
            input=json.dumps(schema),capture_output=True,text=True,check=True)
        proof=json.loads(process.stdout)
        self.assertTrue(proof['actual_AMT_interview_rendered'])
        self.assertTrue(proof['default_unchecked'])
        self.assertTrue(proof['change_writes_boolean'])

    def test_unconfirmed_ISO_preference_is_blocked(self):
        case=next(c for c in CASES if c['expected']['AMT']>0)
        data=return_for(case);data['amt']['eligibility_confirmed']=False
        r=engine.calculate_return(data)
        self.assertFalse(r['can_prepare'])
        self.assertTrue(any('preference amounts' in issue for issue in r['blocking_issues']))

    def test_marketplace_comparator_combination_is_explicitly_blocked(self):
        data=return_for(CASES[0]);data['marketplace']['enabled']=True
        data['marketplace']['months']=[dict(engine.tax_credits.row_templates()['marketplace.months'],month=m) for m in range(1,13)]
        r=engine.calculate_return(data)
        self.assertFalse(r['can_prepare'])
        self.assertTrue(any('Form6251 line10 comparator' in issue for issue in r['blocking_issues']))

if __name__=='__main__':unittest.main()
