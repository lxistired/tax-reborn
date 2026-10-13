"""Independent, local US2025 IRA/HSA/education/Marketplace worksheets.

Pure dictionary APIs; no import of the return engine and no third-party runtime.
All money inputs are decimal USD strings; outputs follow whole-dollar form lines.
"""
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING, ROUND_FLOOR
import re

SOURCES = {
    'ira': 'https://www.irs.gov/publications/p590a',
    'ira_1040': 'https://www.irs.gov/instructions/i1040gi',
    'hsa': 'https://www.irs.gov/instructions/i8889',
    'hsa_excise': 'https://www.irs.gov/pub/irs-prior/f5329--2025.pdf',
    'education': 'https://www.irs.gov/instructions/i8863',
    'education_form': 'https://www.irs.gov/pub/irs-prior/f8863--2025.pdf',
    'marketplace': 'https://www.irs.gov/instructions/i8962',
}
D = Decimal
STATUSES = {'single', 'mfj', 'mfs', 'hoh', 'qss'}


def default_inputs():
    return {
        'ira': {'enabled': False, 'traditional_taxpayer': '0', 'traditional_spouse': '0',
                'roth_taxpayer': '0', 'roth_spouse': '0',
                'prior_basis_taxpayer': '0', 'prior_basis_spouse': '0',
                'taxpayer_covered_by_employer_plan': False,
                'spouse_covered_by_employer_plan': False,
                'contributions_and_coverage_confirmed': False,
                'compensation_and_magi_confirmed': False,
                'no_rollovers_recharacterizations_or_prior_excess': False,
                'mfs_living_arrangement_confirmed': False,
                'mfs_lived_apart_entire_year': False},
        'hsa': {'enabled': False, 'accounts': [], 'family_allocation_taxpayer_percent': '50',
                'family_allocation_confirmed': False,
                'spouse_coverage': ['none'] * 12, 'spouse_coverage_confirmed': False},
        'education': {'enabled': False, 'students': [],
                      'claim_eligibility_confirmed': False,
                      'claimed_on_another_return': False,
                      'no_foreign_magi_or_prior_credit_recapture': False,
                      'claimant_full_time_student': False,
                      'claimant_earned_income': '0', 'claimant_support': '0',
                      'claimant_parent_alive': True,
                      'claimant_refundability_facts_confirmed': False},
        'marketplace': {'enabled': False, 'region': 'contiguous', 'months': [],
                        'dependents_magi': '0', 'foreign_excluded_income': '0',
                        'tax_family_and_household_income_confirmed': False,
                        'coverage_and_slcsp_inputs_confirmed': False,
                        'no_qsehra_or_ichra': False,
                        'lawful_presence_confirmed': False,
                        'no_shared_policy_or_marriage_allocation': False,
                        'mfs_no_abuse_or_abandonment_exception': False,
                        'below_poverty_exception': 'none',
                        'below_poverty_exception_confirmed': False,
                        'annual_calculation': False,
                        'annual_calculation_eligible_confirmed': False}
    }


def _money(value, label, signed=False):
    if not isinstance(value, str) or not re.fullmatch(r'-?\d+(?:\.\d{1,2})?', value):
        raise ValueError(label + ' must be a decimal USD string with at most two cents digits.')
    amount = D(value)
    if abs(amount) > D('100000000000') or (amount < 0 and not signed):
        raise ValueError(label + ' is outside its monetary range.')
    return amount


def _whole(value):
    return int(D(value).quantize(D('1'), rounding=ROUND_HALF_UP))


def _ctxmoney(context, key, signed=False):
    if key not in context:
        raise ValueError('Missing derived context.' + key)
    value = context[key]
    if type(value) is int:
        value = str(value)
    return _whole(_money(value, 'context.' + key, signed=signed))


def _bool(value, key):
    if type(value) is not bool:
        raise ValueError(key + ' must be a boolean.')
    return value


def _status(context):
    status = context.get('filing_status')
    if status not in STATUSES:
        raise ValueError('context.filing_status is invalid.')
    return status


def _age(context, owner):
    value = context.get(owner + '_age')
    if type(value) is not int or not 0 <= value <= 120:
        raise ValueError('context.' + owner + '_age is invalid.')
    return value


def _schema(data, template, label):
    if not isinstance(data, dict):
        raise ValueError(label + ' must be an object.')
    unknown = set(data) - set(template)
    if unknown:
        raise ValueError('Unknown ' + label + ' fields: ' + ', '.join(sorted(unknown)))
    result = deepcopy(template)
    result.update(deepcopy(data))
    for key, default in template.items():
        if isinstance(default, bool):
            _bool(result[key], label + '.' + key)
    return result


def _result(name):
    return {'tax_year': 2025, 'currency': 'USD', 'module': name, 'can_compute': True,
            'deduction': 0, 'nonrefundable_credit': 0, 'refundable_credit': 0,
            'repayment': 0, 'other_income': 0, 'additional_tax': 0,
            'blocking_issues': [], 'warnings': [], 'trace': [], 'form_lines': {}}


def _require(result, condition, message):
    if not condition and message not in result['blocking_issues']:
        result['blocking_issues'].append(message)
        result['can_compute'] = False


def _log(result, label, amount, source):
    result['trace'].append({'label': label, 'amount': int(amount), 'source': SOURCES[source]})


def _inactive(data, result):
    if data['enabled']:
        return False
    # Disabled stale monetary entries must not hide distributions/APTC/excise facts.
    def populated(value, key=''):
        if isinstance(value, list):
            return bool(value) and key != 'spouse_coverage'
        if isinstance(value, str) and re.fullmatch(r'-?\d+(?:\.\d+)?', value):
            return D(value) != 0 and key != 'family_allocation_taxpayer_percent'
        return False
    _require(result, not any(populated(v, k) for k, v in data.items()),
             'Disabled section contains monetary/document data; enable it or remove the entries explicitly.')
    return True


def calculate_ira(data, context):
    """Traditional IRA deduction and nondeductible basis; contribution ceilings.

    MAGI must exclude this deduction and add back student-loan/special exclusions.
    Compensation is eligible IRA compensation after SEhalf/qualified-plan deduction.
    SSA/contribution/distribution interactions are gated rather than guessed.
    """
    data = _schema(data, default_inputs()['ira'], 'ira')
    r = _result('ira')
    values = {k: _whole(_money(data[k], 'ira.' + k)) for k in
              ('traditional_taxpayer', 'traditional_spouse', 'roth_taxpayer', 'roth_spouse',
               'prior_basis_taxpayer', 'prior_basis_spouse')}
    if _inactive(data, r):
        return r
    status = _status(context)
    _require(r, data['contributions_and_coverage_confirmed'],
             'Confirm tax-year2025 eligible IRA contributions, timely contribution date and both employer-plan coverage statuses.')
    _require(r, data['compensation_and_magi_confirmed'],
             'Confirm IRA-eligible compensation and Pub590A modified AGI, including required addbacks.')
    _require(r, data['no_rollovers_recharacterizations_or_prior_excess'],
             'IRA rollovers/recharacterizations/prior excess corrections require separate worksheets not implemented here.')
    _require(r, not context.get('social_security_received', False),
             'IRA with SocialSecurity requires Pub590A AppendixB integrated worksheets; do not use this non-SSA worksheet.')
    _require(r, not context.get('ira_distribution_received', False),
             'IRA contributions plus distributions/conversions require Form8606 basis allocation not implemented here.')
    magi = _ctxmoney(context, 'magi_before_ira', signed=True)
    compensation = {o: max(0, _ctxmoney(context, 'compensation_' + o)) for o in ('taxpayer', 'spouse')}
    if status != 'mfj' and any(values[k] for k in ('traditional_spouse', 'roth_spouse', 'prior_basis_spouse')):
        raise ValueError('Spouse IRA amounts may be included only in a joint return.')
    if status == 'mfs':
        _require(r, data['mfs_living_arrangement_confirmed'], 'Confirm whether MFS spouses lived apart throughout2025.')
    owners = ('taxpayer', 'spouse') if status == 'mfj' else ('taxpayer',)
    total_contrib = sum(values['traditional_' + o] + values['roth_' + o] for o in owners)
    pool = sum(compensation[o] for o in owners)
    _require(r, total_contrib <= pool,
             'IRA contributions exceed eligible household compensation; Form5329 excess/correction facts are required.')
    for owner in owners:
        age = _age(context, owner)
        limit = 8000 if age >= 50 else 7000
        traditional, roth = values['traditional_' + owner], values['roth_' + owner]
        _require(r, traditional + roth <= limit,
                 owner + ' traditional plus Roth contributions exceed2025 annual limit; Form5329 excess/corrections are not implemented.')
        covered = data[owner + '_covered_by_employer_plan']
        other_covered = data[('spouse' if owner == 'taxpayer' else 'taxpayer') + '_covered_by_employer_plan']
        apart = status == 'mfs' and data['mfs_lived_apart_entire_year']
        lower = upper = None
        if covered:
            if status in ('mfj', 'qss'):
                lower, upper = 126000, 146000
            elif status == 'mfs' and not apart:
                lower, upper = 0, 10000
            else:
                lower, upper = 79000, 89000
        elif other_covered and (status == 'mfj' or (status == 'mfs' and not apart)):
            lower, upper = (236000, 246000) if status == 'mfj' else (0, 10000)
        reduced_limit = limit
        if upper is not None and magi >= upper:
            reduced_limit = 0
        elif upper is not None and magi > lower:
            # Explicit IRS worksheet: increase to next$10, minimum$200.
            raw = D(upper - magi) * D(limit) / D(upper - lower)
            reduced_limit = min(limit, max(200, int((raw / 10).to_integral_value(rounding=ROUND_CEILING)) * 10))
        available_comp = compensation[owner]
        if status == 'mfj':
            other = 'spouse' if owner == 'taxpayer' else 'taxpayer'
            available_comp = max(available_comp, pool - values['traditional_' + other] - values['roth_' + other])
        deduction = max(0, min(traditional, reduced_limit, available_comp, max(0, limit - roth)))
        nondeductible = max(0, traditional - deduction)
        # Roth contributions have their own MAGI ceiling; no deduction is claimed.
        roth_low, roth_high = (236000, 246000) if status in ('mfj', 'qss') else ((0, 10000) if status == 'mfs' and not apart else (150000, 165000))
        roth_base = min(limit, available_comp)
        roth_limit = max(0, roth_base - traditional)
        if magi >= roth_high:
            roth_limit = 0
        elif magi > roth_low:
            reduction = _whole(D(roth_base) * D(magi - roth_low) / D(roth_high - roth_low))
            phase_raw = D(roth_base - reduction)
            phase_limit = max(200, int((phase_raw / 10).to_integral_value(rounding=ROUND_CEILING)) * 10)
            roth_limit = min(roth_limit, phase_limit)
        _require(r, roth <= roth_limit,
                 owner + ' Roth contribution exceeds MAGI/combined IRA limit; excess/correction Form5329 is required.')
        r['form_lines'][owner] = {'annual_limit': limit, 'phaseout_lower': lower,
                                 'phaseout_upper': upper, 'reduced_deduction_limit': reduced_limit,
                                 'eligible_compensation': available_comp, 'deduction': deduction,
                                 'nondeductible': nondeductible, 'roth_contribution_limit': roth_limit,
                                 'form8606_line1': nondeductible,
                                 'form8606_line2': values['prior_basis_' + owner],
                                 'form8606_line14_basis': values['prior_basis_' + owner] + nondeductible}
        r['deduction'] += deduction
        _log(r, owner + ' IRA deduction', deduction, 'ira_1040')
        if nondeductible:
            r['warnings'].append(owner + ': nondeductible traditional contribution must be reported on Form8606; basis retained for future distributions.')
    return r


def _coverage(value, label):
    if not isinstance(value, list) or len(value) != 12 or any(v not in ('none', 'self', 'family') for v in value):
        raise ValueError(label + ' requires12 first-day month entries: none/self/family.')
    return value


def calculate_hsa(data, context):
    """8889 contribution deduction/distribution income and current5329 excise."""
    data = _schema(data, default_inputs()['hsa'], 'hsa')
    r = _result('hsa')
    share = _money(data['family_allocation_taxpayer_percent'], 'hsa.family_allocation_taxpayer_percent')
    if not 0 <= share <= 100:
        raise ValueError('HSA family allocation percent must be0..100.')
    spouse_coverage = _coverage(data['spouse_coverage'], 'hsa.spouse_coverage')
    if _inactive(data, r):
        return r
    status = _status(context)
    if not isinstance(data['accounts'], list) or len(data['accounts']) > 2:
        raise ValueError('HSA accounts are aggregate annual amounts, at mostone perowner.')
    accounts = {}
    for item in data['accounts']:
        a = _schema(item, row_templates()['hsa.accounts'], 'hsa.account')
        owner = a['owner']
        if owner not in ('taxpayer', 'spouse') or (owner == 'spouse' and status != 'mfj') or owner in accounts:
            raise ValueError('HSA owner must be unique; spouse included only in MFJ.')
        _coverage(a['coverage'], 'hsa.account.coverage')
        for k, v in row_templates()['hsa.accounts'].items():
            if isinstance(v, str) and k != 'owner':
                _money(a[k], 'hsa.account.' + k)
        accounts[owner] = a
        _require(r, a['first_day_coverage_and_eligibility_confirmed'],
                 owner + ': confirm monthly first-day qualifying HDHP, no disqualifying FSA/other coverage/Medicare and no dependency.')
        _require(r, a['no_prior_excess_or_testing_failure'],
                 owner + ': prior HSA/MSA excess and testing-period failure require5329/8889PartIII history not implemented.')
    if not accounts:
        raise ValueError('Enabled HSA requires at leastone aggregate owner account.')
    coverage = {o: list(accounts[o]['coverage']) if o in accounts else (list(spouse_coverage) if o == 'spouse' else ['none'] * 12)
                for o in ('taxpayer', 'spouse')}
    married = status in ('mfj', 'mfs')
    if married and 'spouse' not in accounts:
        _require(r, data['spouse_coverage_confirmed'], 'Confirm spouse monthly eligibility/coverage; a spouse familyHDHP can change even your self-only contribution limit.')
    if married and any('family' in c for c in coverage.values()):
        _require(r, data['family_allocation_confirmed'], 'Confirm agreed allocation of shared8550 family limit; catch-up belongs to each owner separately.')
        if 'spouse' not in accounts:
            _require(r, data['spouse_coverage_confirmed'], 'Confirm spouse monthly eligibility even when spouse has no HSA on this return.')
    for owner, a in accounts.items():
        if a['last_month_rule']:
            _require(r, a['coverage'][11] != 'none', owner + ': last-month rule needs eligible December1 coverage.')
            _require(r, a['testing_period_obligation_confirmed'], owner + ': last-month rule requires Dec2025-Dec2026 testing-period obligation acknowledgment.')
            if a['coverage'][11] != 'none':
                coverage[owner] = [a['coverage'][11]] * 12
            r['warnings'].append(owner + ': preserve last-month-rule records; a2026 testing failure can cause income and10% additional tax.')
    for owner, a in accounts.items():
        age = _age(context, owner)
        base = D(0)
        eligible_months = 0
        for i, own in enumerate(coverage[owner]):
            if own == 'none':
                continue
            eligible_months += 1
            other = coverage['spouse' if owner == 'taxpayer' else 'taxpayer'][i] if married else 'none'
            family = own == 'family' or other == 'family'
            if family:
                monthly = D(8550)
                if other != 'none':
                    monthly *= (share if owner == 'taxpayer' else 100 - share) / 100
            else:
                monthly = D(4300)
            base += monthly
        base_limit = _whole(base / 12)
        catchup = _whole(D(1000 * eligible_months) / 12) if age >= 55 else 0
        limit = base_limit + catchup
        n = {k: _whole(_money(a[k], 'hsa.account.' + k)) for k in
             ('personal_contributions', 'employer_contributions', 'archer_msa_contributions',
              'qualified_funding_distribution', 'distributions', 'rollover_distributions',
              'excess_withdrawal_distributions', 'exception_taxable_distributions',
              'qualified_medical_expenses', 'year_end_balance', 'excess_contributions_withdrawn')}
        if n['archer_msa_contributions'] or n['qualified_funding_distribution']:
            _require(r, False, owner + ': ArcherMSA/shared limits or IRA-HSA funding-distribution lifetime/testing facts require additional worksheets not implemented.')
        employer = n['employer_contributions']
        raw_excess = max(0, n['personal_contributions'] + employer - limit)
        removed = n['excess_contributions_withdrawn']
        if removed > raw_excess:
            raise ValueError('HSA excess withdrawals cannot exceed current raw excess.')
        if removed:
            _require(r, a['excess_withdrawal_and_income_reported_confirmed'],
                     owner + ': confirm excess timely withdrawn by return due date and related earnings reported as income.')
        employer_excess = max(0, employer - limit)
        if employer_excess:
            _require(r, a['employer_excess_in_wages_confirmed'],
                     owner + ': employer excess must be correctly included in W2 income/corrected before completing this worksheet.')
            if removed:
                _require(r, False, owner + ': withdrawn employer excess needs employer/W2 correction allocation; not assumed.')
        personal = max(0, n['personal_contributions'] - removed)
        deduction = min(personal, max(0, limit - employer))
        excess = max(0, raw_excess - removed)
        excise = _whole(D(min(excess, n['year_end_balance'])) * D('.06'))
        if excess:
            _require(r, a['year_end_balance_confirmed'], owner + ': current6%excess tax needs verified year-endHSA balance, not a defaultzero.')
        distributions = n['distributions'] - n['rollover_distributions'] - n['excess_withdrawal_distributions']
        if distributions < 0 or n['qualified_medical_expenses'] > distributions:
            raise ValueError('HSA rollover/qualified medical amounts exceed total non-rollover distributions.')
        if distributions:
            _require(r, a['medical_expenses_confirmed'],
                     owner + ': verify eligible medical expenses after HSA establishment, unreimbursed and unused for other deductions.')
        if n['distributions']:
            _require(r, a['distribution_breakdown_confirmed'], owner + ': reconcile1099-SA gross, rollover and timely excess-withdrawal distributions before taxing the remainder.')
        if n['excess_withdrawal_distributions']:
            _require(r, a['excess_withdrawal_and_income_reported_confirmed'],
                     owner + ': excluding excess-withdrawal distributions needs timely correction and separate reporting of earnings in the withdrawal year.')
        taxable = distributions - n['qualified_medical_expenses']
        exception_amount = n['exception_taxable_distributions']
        if exception_amount > taxable:
            raise ValueError('HSA20%tax exception amount cannot exceed taxable distributions.')
        if exception_amount:
            _require(r, a['distribution_exception_confirmed'], owner + ': verify actual dates/qualifying disability or death for the entered exception portion.')
        if taxable and age == 65:
            _require(r, a['distribution_timing_confirmed'], owner + ': year-endage65 does not establish distribution after65thbirthday; confirm timing and any taxable prebirthday portion.')
        if age >= 66:
            exception_amount = taxable
        distribution_tax = _whole(D(taxable - exception_amount) * D('.20'))
        r['deduction'] += deduction
        r['other_income'] += taxable
        r['additional_tax'] += excise + distribution_tax
        r['form_lines'][owner] = {'base_limit': base_limit, 'catchup': catchup,
                                 'contribution_limit': limit, 'employer_contributions': employer,
                                 'line13_deduction': deduction, 'excess_contributions': excess,
                                 'form5329_current_excess_tax': excise, 'line14c_distributions': distributions,
                                 'line15_qualified_medical': n['qualified_medical_expenses'],
                                 'line16_taxable_distributions': taxable, 'exception_taxable_distributions': exception_amount,
                                 'line17b_additional_tax': distribution_tax}
        _log(r, owner + ' HSA deduction', deduction, 'hsa')
        _log(r, owner + ' HSA taxable distributions', taxable, 'hsa')
        _log(r, owner + ' HSA additional/excise tax', excise + distribution_tax, 'hsa')
        if excise:
            _log(r, owner + ' Form5329PartVII current excess tax', excise, 'hsa_excise')
        if excess:
            r['warnings'].append(owner + ': current excess remains; preserve5329 carryforward and correct future contributions.')
    return r


def calculate_education(data, context):
    """8863 AOTC/LLC, expense allocation, phaseout and claimant refund restriction."""
    data = _schema(data, default_inputs()['education'], 'education')
    r = _result('education')
    for k in ('claimant_earned_income', 'claimant_support'):
        _money(data[k], 'education.' + k)
    if _inactive(data, r):
        return r
    status = _status(context)
    magi = _ctxmoney(context, 'magi', signed=True)
    tax_limit = max(0, _ctxmoney(context, 'tax_liability_limit'))
    age = _age(context, 'taxpayer')
    _require(r, data['claim_eligibility_confirmed'], 'Confirm education claimant/dependent allocation, timely TINs, eligible institutions and qualifying tax-year payments.')
    _require(r, data['no_foreign_magi_or_prior_credit_recapture'],
             'Foreign/territory education MAGI exclusions or prior-credit recapture require separate worksheets not implemented.')
    if not isinstance(data['students'], list) or len(data['students']) > 100:
        raise ValueError('Education students must be a list of at most100 distinct students.')
    students = []
    identifiers = set()
    aotc_total = llc_expenses = 0
    for item in data['students']:
        s = _schema(item, row_templates()['education.students'], 'education.student')
        for key in ('student_id', 'name', 'institution_ein'):
            if not isinstance(s[key], str) or len(s[key]) > 1000:
                raise ValueError('Student identification must be text.')
        if not s['student_id'].strip() or s['student_id'] in identifiers:
            raise ValueError('Student IDs must be nonempty and unique; one credit perstudent.')
        identifiers.add(s['student_id'])
        if s['credit'] not in ('aotc', 'llc'):
            raise ValueError('Education credit must be aotc or llc.')
        if type(s['aotc_prior_years']) is not int or not 0 <= s['aotc_prior_years'] <= 100:
            raise ValueError('AOTC prior years must be a nonnegative integer.')
        for key in ('eligible_institution_and_payment_period_confirmed',
                    'qualified_expenses_and_no_double_benefit_confirmed',
                    'dependency_claim_and_tin_confirmed', 'form_1098t_received_or_exception_confirmed'):
            _require(r, s[key], s['name'] + ': confirm ' + key + '.')
        n = {k: _money(s[k], 'education.student.' + k) for k in
             ('tuition_and_required_fees', 'course_materials', 'tax_free_assistance', 'expenses_used_elsewhere')}
        materials = n['course_materials'] if s['credit'] == 'aotc' or s['materials_paid_to_institution_required'] else 0
        # These amounts contribute to one Form8863 expense line. Add cents
        # before whole-dollar rounding, rather than rounding each category.
        adjusted = max(0, _whole(n['tuition_and_required_fees'] + materials - n['tax_free_assistance'] - n['expenses_used_elsewhere']))
        tentative = 0
        if s['credit'] == 'aotc':
            _require(r, s['aotc_prior_years'] < 4 and s['half_time_degree_program'] and
                     s['first_four_years_not_completed'] and s['no_felony_drug_conviction'],
                     s['name'] + ': AOTC requires fewer than4 prior claims, half-time credential enrollment, first4years not completed and no felony drug conviction; selectLLC explicitly ifeligible.')
            _require(r, bool(re.fullmatch(r'\d{2}-?\d{7}', s['institution_ein'])),
                     s['name'] + ': AOTC requires an institution EIN.')
            tentative = min(adjusted, 2000) + _whole(D(min(max(0, adjusted - 2000), 2000)) * D('.25'))
            aotc_total += tentative
        else:
            llc_expenses += adjusted
        students.append({'student_id': s['student_id'], 'credit': s['credit'],
                         'adjusted_qualified_expenses': adjusted, 'line30_aotc': tentative,
                         'line31_llc_expenses': adjusted if s['credit'] == 'llc' else 0})
    high, span = (180000, 20000) if status == 'mfj' else (90000, 10000)
    factor = min(D(1), max(D(0), D(high - magi) / D(span)))
    eligible = status != 'mfs' and not data['claimed_on_another_return']
    aotc = _whole(D(aotc_total) * factor) if eligible else 0
    llc = _whole(D(_whole(D(min(llc_expenses, 10000)) * D('.20'))) * factor) if eligible else 0
    refundable_restricted = (age < 18 or (age == 18 or (18 < age < 24 and data['claimant_full_time_student']))
                             and _money(data['claimant_earned_income'], 'education.claimant_earned_income') <
                             _money(data['claimant_support'], 'education.claimant_support') / 2)
    refundable_restricted = refundable_restricted and data['claimant_parent_alive'] and status != 'mfj'
    if aotc and age < 24 and status != 'mfj':
        _require(r, data['claimant_refundability_facts_confirmed'],
                 'Under24 claimant AOTC refund requires verified full-time status, earned income, total support and whether a parent was alive.')
        if data['claimant_parent_alive'] and (age == 18 or (18 < age < 24 and data['claimant_full_time_student'])):
            _require(r, _money(data['claimant_support'], 'education.claimant_support') > 0,
                     'Under24 support comparison requires actual positive total support; missing/defaultzero cannot establish refundable eligibility.')
    refundable = 0 if refundable_restricted else _whole(D(aotc) * D('.40'))
    nonref_available = aotc - refundable + llc
    r['refundable_credit'] = refundable
    r['nonrefundable_credit'] = min(tax_limit, nonref_available)
    r['form_lines'] = {'students': students, 'line1': aotc_total,
                       'phaseout_factor': str(factor), 'line7': aotc,
                       'line8': refundable, 'line9': aotc - refundable,
                       'line10': llc_expenses, 'line11': min(llc_expenses, 10000),
                       'line18': llc, 'line19': r['nonrefundable_credit'],
                       'tax_limit': tax_limit, 'refund_restricted_under24': bool(refundable_restricted)}
    if not eligible:
        r['warnings'].append('MFS or claimed-on-another-return status makes education credits zero.')
    _log(r, 'Refundable AOTC', refundable, 'education_form')
    _log(r, 'Nonrefundable education credit after tax limit', r['nonrefundable_credit'], 'education_form')
    return r


def _applicable_figure(percent):
    #2025IRS8962Table2: fixed4-place figures, including quarter-basis-point rounding.
    if percent <= 150:
        return D('0.0000')
    if percent >= 400:
        return D('0.0850')
    value = D(percent - 150) * D('.0004') if percent <= 300 else D('.0600') + D(percent - 300) * D('.00025')
    return value.quantize(D('.0001'), rounding=ROUND_HALF_UP)


def calculate_marketplace(data, context):
    """8962 annual/monthly PTC and2025 capped excess-APTC reconciliation."""
    data = _schema(data, default_inputs()['marketplace'], 'marketplace')
    r = _result('marketplace')
    _money(data['dependents_magi'], 'marketplace.dependents_magi', signed=True)
    _money(data['foreign_excluded_income'], 'marketplace.foreign_excluded_income')
    if _inactive(data, r):
        return r
    status = _status(context)
    for key in ('tax_family_and_household_income_confirmed', 'coverage_and_slcsp_inputs_confirmed',
                'lawful_presence_confirmed', 'no_shared_policy_or_marriage_allocation', 'no_qsehra_or_ichra'):
        _require(r, data[key], 'Marketplace: confirm ' + key + '; policy/immigration/HRA/marriage exceptions require Pub974 worksheets.')
    _require(r, not _ctxmoney(context, 'self_employed_health_insurance'),
             'Marketplace PTC with self-employed health-insurance deduction requires Pub974 iterative worksheet not implemented here.')
    size = context.get('tax_family_size')
    if type(size) is not int or not 1 <= size <= 100:
        raise ValueError('PTC tax family size must be1..100.')
    region = data['region']
    if region not in ('contiguous', 'alaska', 'hawaii'):
        raise ValueError('PTC region must be contiguous/alaska/hawaii, using higherFPL for applicable moves.')
    first, increment = {'contiguous': (15060, 5380), 'alaska': (18810, 6730), 'hawaii': (17310, 6190)}[region]
    fpl = first + (size - 1) * increment
    parent_magi = (_ctxmoney(context, 'household_agi', signed=True) +
                 _ctxmoney(context, 'household_ss_nontaxable') + _ctxmoney(context, 'household_tax_exempt_interest') +
                 _whole(_money(data['foreign_excluded_income'], 'marketplace.foreign_excluded_income')))
    dependent_magi = _whole(_money(data['dependents_magi'], 'marketplace.dependents_magi', signed=True))
    income = max(0, parent_magi + dependent_magi)
    percent = 401 if income > fpl * 4 else int((D(income) * 100 / D(fpl)).to_integral_value(rounding=ROUND_FLOOR))
    if data['below_poverty_exception'] not in ('none', 'marketplace_estimated_at_least100', 'lawful_immigrant_no_medicaid'):
        raise ValueError('Invalid below-poverty exception.')
    applicable = True
    if percent < 100:
        _require(r, data['below_poverty_exception_confirmed'],
                 'Below100%FPL requires confirmed Marketplace-estimate/APTC/nonrecklessness or lawful-immigrant Medicaid exclusion exception, or confirmednoexception.')
        applicable = data['below_poverty_exception'] != 'none'
    if status == 'mfs':
        _require(r, data['mfs_no_abuse_or_abandonment_exception'],
                 'MFS abuse/abandonment/living-apart eligibility requires separate8962 exception review; ordinaryMFS must confirm noexception.')
        applicable = False
    if not isinstance(data['months'], list) or len(data['months']) != 12:
        raise ValueError('Provide all12 unique1095-A months, including explicitzero months.')
    rows = []
    seen = set()
    raw_totals = {key: D(0) for key in ('enrollment_premium', 'slcsp_premium', 'advance_credit')}
    raw_premiums, raw_benchmarks = set(), set()
    for item in data['months']:
        row = _schema(item, row_templates()['marketplace.months'], 'marketplace.month')
        month = row['month']
        if type(month) is not int or not 1 <= month <= 12 or month in seen:
            raise ValueError('Marketplace months must be unique1..12.')
        seen.add(month)
        raw_values = {k: _money(row[k], 'marketplace.month.' + k) for k in raw_totals}
        for key in raw_totals:
            raw_totals[key] += raw_values[key]
        raw_premiums.add(raw_values['enrollment_premium'])
        raw_benchmarks.add(raw_values['slcsp_premium'])
        values = {k: _whole(v) for k, v in raw_values.items()}
        if row['coverage_eligible'] and values['enrollment_premium']:
            _require(r, row['premiums_paid_and_no_other_mec_confirmed'],
                     'Month' + str(month) + ': verify premiums paid and no affordable/minimum-value employer or other eligible MEC.')
            _require(r, values['slcsp_premium'] > 0,
                     'Month' + str(month) + ': obtain correctSLCSP from Marketplace; a missingbenchmark cannot be inferred.')
        rows.append(dict(row, **values))
    rows.sort(key=lambda row: row['month'])
    aptc = sum(row['advance_credit'] for row in rows)
    if percent < 100 and data['below_poverty_exception'] == 'marketplace_estimated_at_least100':
        _require(r, aptc > 0, 'Below-poverty Marketplace-estimate exception requires APTC in at leastone month.')
    figure = _applicable_figure(percent)
    annual_contribution = _whole(D(income) * figure) if applicable else 0
    monthly_contribution = _whole(D(annual_contribution) / 12)
    annual = data['annual_calculation']
    if annual:
        _require(r, data['annual_calculation_eligible_confirmed'] and
                 all(row['coverage_eligible'] and row['premiums_paid_and_no_other_mec_confirmed'] for row in rows) and
                 len(raw_premiums) == 1 and len(raw_benchmarks) == 1,
                 '8962annual line11 requires all12months qualifying, unchanged premiums/SLCSP for each policy, verifiedannualeligibility; otherwise usemonthly lines12-23.')
        premium = _whole(raw_totals['enrollment_premium'])
        benchmark = _whole(raw_totals['slcsp_premium'])
        aptc = _whole(raw_totals['advance_credit'])
        allowed = min(premium, max(0, benchmark - annual_contribution)) if applicable else 0
    else:
        allowed = 0
        for row in rows:
            credit = min(row['enrollment_premium'], max(0, row['slcsp_premium'] - monthly_contribution)) if applicable and row['coverage_eligible'] else 0
            row['allowed_credit'] = credit
            allowed += credit
    excess = max(0, aptc - allowed)
    repayment_limit = None if percent >= 400 else ((375 if percent < 200 else 975 if percent < 300 else 1625) * (1 if status == 'single' else 2))
    repayment = excess if repayment_limit is None else min(excess, repayment_limit)
    r['repayment'] = repayment
    r['refundable_credit'] = max(0, allowed - aptc)
    r['form_lines'] = {'line1': size, 'line2a': parent_magi, 'line2b': dependent_magi,
                       'line3': income, 'line4': fpl, 'line5': percent,
                       'line7': str(figure), 'line8a': annual_contribution, 'line8b': monthly_contribution,
                       'line10_annual': annual, 'months': rows, 'line24': allowed,
                       'line25': aptc, 'line26': r['refundable_credit'], 'line27': excess,
                       'line28': repayment_limit, 'line29': repayment}
    if annual:
        r['form_lines']['line11_annual'] = {'enrollment_premium': premium,
                                          'slcsp_premium': benchmark, 'contribution': annual_contribution,
                                          'allowed_credit': allowed, 'advance_credit': aptc}
    _log(r, '2025PTC allowed', allowed, 'marketplace')
    _log(r, 'Net premium tax credit', r['refundable_credit'], 'marketplace')
    _log(r, 'ExcessAPTC repayment after2025cap', repayment, 'marketplace')
    return r


def row_templates():
    return {
        'hsa.accounts': {'owner': 'taxpayer', 'coverage': ['none'] * 12,
                         'first_day_coverage_and_eligibility_confirmed': False,
                         'personal_contributions': '0', 'employer_contributions': '0',
                         'archer_msa_contributions': '0', 'qualified_funding_distribution': '0',
                         'distributions': '0', 'rollover_distributions': '0',
                         'excess_withdrawal_distributions': '0',
                         'exception_taxable_distributions': '0',
                         'distribution_breakdown_confirmed': False,
                         'distribution_timing_confirmed': False,
                         'qualified_medical_expenses': '0', 'medical_expenses_confirmed': False,
                         'distribution_exception_confirmed': False,
                         'year_end_balance': '0',
                         'year_end_balance_confirmed': False,
                         'excess_contributions_withdrawn': '0',
                         'excess_withdrawal_and_income_reported_confirmed': False,
                         'employer_excess_in_wages_confirmed': False,
                         'no_prior_excess_or_testing_failure': False,
                         'last_month_rule': False, 'testing_period_obligation_confirmed': False},
        'education.students': {'student_id': '', 'name': '', 'credit': 'aotc',
                               'tuition_and_required_fees': '0', 'course_materials': '0',
                               'materials_paid_to_institution_required': False,
                               'tax_free_assistance': '0', 'expenses_used_elsewhere': '0',
                               'eligible_institution_and_payment_period_confirmed': False,
                               'qualified_expenses_and_no_double_benefit_confirmed': False,
                               'dependency_claim_and_tin_confirmed': False,
                               'form_1098t_received_or_exception_confirmed': False,
                               'institution_ein': '', 'aotc_prior_years': 0,
                               'half_time_degree_program': False,
                               'first_four_years_not_completed': False,
                               'no_felony_drug_conviction': False},
        'marketplace.months': {'month': 1, 'enrollment_premium': '0', 'slcsp_premium': '0',
                               'advance_credit': '0', 'coverage_eligible': False,
                               'premiums_paid_and_no_other_mec_confirmed': False}
    }


def capabilities():
    return {'tax_year': 2025,
            'implemented': ['TraditionalIRA deduction, contribution limits and no-distribution8606basis',
                            'Roth contribution MAGI screening',
                            'HSA monthly eligibility/proration, employer reduction, family sharing, catch-up and last-month rule',
                            'HSA taxable distributions, actual-date20%exceptions and current-excess6%tax',
                            'AOTC/LLC adjusted expenses, phaseout, nonrefundable tax limit and claimant-under24 refund tests',
                            '2025 annual/monthly8962PTC, below-poverty exceptions and capped excessAPTC repayment'],
            'unsupported': ['IRA excess correction/SSA-contribution AppendixB/distribution-contribution8606 allocation',
                            'HSA prior excess/testing failures, MSA/funding-distribution special worksheets and employer-excess correction allocation',
                            'Education foreignMAGI/recapture and scholarship taxability/529 optimization',
                            'PTC shared-policy allocations/year-of-marriage alternative/QSEHRA-ICHRA/mixed lawful presence/SE-health iteration'],
            'sources': dict(SOURCES)}


def ui_fields():
    """Plain-language qualifications and enums for the shared desktop/mobile UI."""
    return {
        'marketplace.region': {'type': 'select', 'label': 'Federal poverty-line region', 'options': ['contiguous', 'alaska', 'hawaii'], 'help': 'Use2024FPL for2025coverage; select higherAlaska/Hawaii table when required by a move or spouses in different states.'},
        'marketplace.below_poverty_exception': {'type': 'select', 'label': 'Income below100%FPL exception', 'options': ['none', 'marketplace_estimated_at_least100', 'lawful_immigrant_no_medicaid'], 'help': 'Estimated-income exception needs Marketplace estimate at least100%, APTC in a month, no intentional/reckless misstatement and all other eligibility. Immigrant exception needs lawful presence and Medicaid ineligibility due to immigration status.'},
        'education.students.*.credit': {'type': 'select', 'label': 'Credit for this student', 'options': ['aotc', 'llc'], 'help': 'One credit perstudent; AOTC needs first4years, half-time degree program, fewer than4 prior claims and no felony drug conviction. LLC books qualify only when required institution payment.'},
        'hsa.accounts.*.owner': {'type': 'select', 'label': 'Account beneficiary', 'options': ['taxpayer', 'spouse']},
        'hsa.accounts.*.coverage.*': {'type': 'select', 'label': 'First-day eligible coverage', 'options': ['none', 'self', 'family'], 'help': 'none includes Medicare, disqualifying coverage/FSA, dependency or otherwise ineligible; confirm eligibility before marking self/family.'},
        'hsa.spouse_coverage.*': {'type': 'select', 'label': 'Spouse first-day coverage even without an HSA', 'options': ['none', 'self', 'family']},
        'hsa.family_allocation_taxpayer_percent': {'type': 'percent', 'label': 'Agreed family limit allocated to taxpayer', 'min': 0, 'max': 100, 'help': 'The base8550 family limit is shared; the other spouse gets the remainder. Each55+ catch-up stays with its own account.'},
        'ira.contributions_and_coverage_confirmed': {'type': 'checkbox', 'label': '2025contributions/timing and both employer coverage statuses verified', 'help': 'Exclude rollover, prior-year contribution and plan deferrals; coverage includes employer/self-employed SEP,SIMPLE,qualified plans and W2Box13 retirement-plan status.'},
        'ira.compensation_and_magi_confirmed': {'type': 'checkbox', 'label': 'IRA compensation and modified AGI verified', 'help': 'Compensation excludes nonqualified deferred pay, uses SE profit less SEhalf/qualified-plan deductions, and does not net a business loss against wages. MAGI is beforeIRA deduction with student-loan and statutory addbacks.'},
        'hsa.accounts.*.first_day_coverage_and_eligibility_confirmed': {'type': 'checkbox', 'label': 'Monthly HSA eligibility and tax-year contribution amounts verified', 'help': 'QualifyingHDHP, no disqualifyingFSA/coverage, no Medicare or dependency on firstday of each marked eligiblemonth. Employer/Cafeteria contributions use2025 amounts, not blindly allW2CodeW if other-year contributions exist.'},
        'hsa.accounts.*.distribution_breakdown_confirmed': {'type': 'checkbox', 'label': '1099-SA distribution breakdown verified', 'help': 'Gross includes rollovers and timely excess corrections; identify their separate amounts. Qualified rollovers need60-day/once-per-year rules. Excess-withdrawal amounts include earnings.'},
        'hsa.accounts.*.exception_taxable_distributions': {'type': 'money', 'label': 'Taxable distributions exempt from20% additional tax', 'help': 'Enter only dollars distributed after65thbirthday, qualifying disability or death. These dollars remain taxable income. Zero means noexception; age65atyearend alone doesnot establish timing.'},
        'hsa.accounts.*.distribution_timing_confirmed': {'type': 'checkbox', 'label': 'Age65 distribution dates and prebirthday portion verified'},
        'hsa.accounts.*.distribution_exception_confirmed': {'type': 'checkbox', 'label': 'Entered20%exception amount and supporting dates/status verified'},
        'hsa.accounts.*.year_end_balance_confirmed': {'type': 'checkbox', 'label': 'HSA year-end value including2025contributions made in2026 verified', 'help': 'Required for the6%tax on current excess; an unverified defaultzero cannot eliminate the tax.'},
        'hsa.accounts.*.personal_contributions': {'type': 'money', 'label': 'Nonpayroll personal2025 HSA contributions', 'help': 'Exclude employer contributions and salary reduction through a cafeteria plan; those belong in employer_contributions/W2CodeW. Also exclude trustee transfers and rollovers.'},
        'hsa.accounts.*.excess_withdrawal_distributions': {'type': 'money', 'label': '1099-SA gross portion from timely excess correction', 'help': 'Include both withdrawn principal and related earnings only when already in the entered gross distributions. The earnings are separately reported as income in the withdrawal year.'},
        'education.claimant_refundability_facts_confirmed': {'type': 'checkbox', 'label': 'Under24 claimant refund facts verified', 'help': 'Use the return claimant’s age/full-time status/earned income/total support/parent alive facts, not the dependent college student’s age. A parent age40 may receive a refundable credit for a student age20.'},
        'education.students.*.qualified_expenses_and_no_double_benefit_confirmed': {'type': 'checkbox', 'label': 'Qualified expenses and no double benefit verified', 'help': 'Exclude room/board, insurance, transportation and personal expenses; subtract tax-free grants/aid and amounts used for529/Coverdell/other deductions. Payment is in2025 for2025or first3months2026academic period.'},
        'marketplace.coverage_and_slcsp_inputs_confirmed': {'type': 'checkbox', 'label': 'Monthly1095-A amounts and correct applicable SLCSP verified', 'help': 'Do not add duplicateSLCSP amounts from same-state policies for the same coveragefamily. Correct missing/wrong benchmarks with Marketplace records; record zero months explicitly.'},
        'marketplace.tax_family_and_household_income_confirmed': {'type': 'checkbox', 'label': 'Tax family and household MAGI verified', 'help': 'Include claimed dependents only when required to file for income, plus their MAGI, tax-exempt interest, nontaxableSocialSecurity and foreignexcluded-income addbacks.'},
        'marketplace.dependents_magi': {'type': 'money', 'label': 'Required-filer dependents combined MAGI', 'min': -100000000000, 'max': 100000000000, 'help': 'This signed amount already includes the dependents own MAGI addbacks. Do not include a dependent who files only to recover withheld tax and was not required to file.'},
        'marketplace.annual_calculation_eligible_confirmed': {'type': 'checkbox', 'label': 'Annual8962line11 eligibility verified', 'help': 'All12months, unchanged premiums and correctSLCSP for each policy, no shared allocation or alternative marriage calculation. If this applies selectannual_calculation; otherwise usemonthly.'}
    }
