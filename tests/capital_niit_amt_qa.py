"""Independent IRS2025 high-income capital, NIIT and AMT regression facts."""
from pathlib import Path
import json

FIXTURE = Path(__file__).resolve().parents[1] / 'fixtures/capital_niit_amt_2025.json'


def cases():
    return json.loads(FIXTURE.read_text())['cases']


def return_for(engine, case):
    data = engine.default_return()
    data['name'] = 'Synthetic ' + case['name']
    data['taxpayer'].update(age=40, birth_date='1985-06-01', valid_ssn=True, valid_tin=True)
    data['eligibility'].update(full_year_us_resident=True, filing_status_confirmed=True,
        all_income_reported=True, no_amt_preferences=True, capital_gains_eligible=True)
    data['eitc'].update(claim=True, eligibility_confirmed=True, main_home_us_half_year=True,
        not_qualifying_child_of_another=True, no_disallowed_claim_history=True)
    data['niit'].update(eligibility_confirmed=True, deductions_confirmed=True)
    data['amt'].update(eligibility_confirmed=True)
    data['w2'] = [dict(engine.ROW_DEFAULTS['w2'], employer='Synthetic employer',
        wages=str(case['wages']), medicare_wages=str(case['wages']),
        federal_withholding=str(case['W2_withholding']))]
    data['interest'] = [dict(engine.ROW_DEFAULTS['interest'], payer='Synthetic bank',
        taxable=str(case['taxable_interest']), tax_exempt='0')]
    data['dividends'] = [dict(engine.ROW_DEFAULTS['dividends'], payer='Synthetic fund ' + str(i+1),
        ordinary=str(case['ordinary_dividends']) if i == 0 else '0', qualified='0',
        capital_gain_distributions=amount) for i, amount in enumerate(case['capital_distributions'])]
    if case.get('prior_zero_tax_exception_if_owed', False):
        data['estimated_penalty'].update(enabled=True, prior_year_tax='0', prior_year_agi='0',
            prior_year_full_12_months=True, prior_year_tax_verified=True,
            no_prior_year_tax_full_year_resident_confirmed=True, actual_payment_records_confirmed=True)
    return data


def check_app(engine):
    rows = []
    for case in cases():
        result = engine.calculate_return(return_for(engine, case))
        actual = {key: result['lines'][key] for key in case['expected']}
        assert actual == case['expected'], (case['name'], actual, case['expected'])
        assert result['can_prepare'], (case['name'], result['blocking_issues'])
        for key, expected in case['IRS_detail'].items():
            for prefix, module in [('NIIT_', 'form_8960'), ('AMT_', 'form_6251')]:
                if key.startswith(prefix):
                    assert result['schedules'][module]['form_lines'][key[len(prefix):]] == expected, (case['name'], key)
        rows.append({'name': case['name'], 'expected': case['expected'], 'actual': actual, 'passed': True})
    return {'tax_year': 2025, 'cases': len(rows), 'passed': len(rows), 'rows': rows,
        'scope': 'Independent IRS synthetic calculation and printed-line comparison; original native program and saved .tax acceptance are separate.'}
