"""Independently authored IRS TY2025 Form 8814 preparation calculation.

Ordinary domestic interest/dividend and ordinary capital distributions only.
No vendor code/assets, automatic election optimization, or electronic filing.
Source money totals are retained in cents; completed form lines use dollars.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, localcontext
import re

D = Decimal
SOURCES = {name: 'https://www.irs.gov/pub/irs-prior/' + name + '--2025.pdf'
           for name in ('f8814', 'i8814', 'p596', 'i6251')}
GROUP = 'child_income_election'
CONFIRMATIONS = (
    'eligible_parent_confirmed', 'only_interest_dividends_confirmed',
    'return_required_confirmed', 'no_withholding_or_estimated_payments_confirmed',
    'not_joint_return_confirmed', 'not_reported_elsewhere_confirmed',
    'ordinary_domestic_income_confirmed', 'no_private_activity_bond_interest_confirmed')
MONEY_FIELDS = ('taxable_interest', 'tax_exempt_interest', 'ordinary_dividends',
                'qualified_dividends', 'capital_gain_distributions')


def whole(value):
    return int(D(value).quantize(D('1'), rounding=ROUND_HALF_UP))


def money(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'\d{1,12}(?:\.\d{1,2})?', value):
        raise ValueError(label + ' must be a nonnegative USD decimal string with at most two fractional digits.')
    return D(value)


def default_inputs():
    return {GROUP: {'enabled': False, 'children': []}}


def row_templates():
    row = {'name': '', 'ssn': '', 'birth_date': '', 'full_time_student': False,
           **{key: '0' for key in MONEY_FIELDS},
           **{key: False for key in CONFIRMATIONS},
           'qualified_eligibility_confirmed': False,
           'ordinary_capital_distribution_confirmed': False}
    return {GROUP + '.children': row}


def normalize_group(data):
    if not isinstance(data, dict) or set(data) - {'enabled', 'children'}:
        raise ValueError('Invalid child_income_election object or unknown fields.')
    group = deepcopy(default_inputs()[GROUP]); group.update(deepcopy(data))
    if type(group['enabled']) is not bool:
        raise ValueError('child_income_election.enabled must be boolean.')
    if not isinstance(group['children'], list) or len(group['children']) > 50:
        raise ValueError('child_income_election.children must contain at most 50 records.')
    template = row_templates()[GROUP + '.children']; rows = []
    for index, item in enumerate(group['children']):
        label = 'child_income_election.children[' + str(index) + ']'
        if not isinstance(item, dict) or set(item) - set(template):
            raise ValueError(label + ' contains unknown fields or is not an object.')
        row = deepcopy(template); row.update(deepcopy(item))
        for key, default in template.items():
            value = row[key]
            if type(default) is bool:
                if type(value) is not bool: raise ValueError(label + '.' + key + ' must be boolean.')
            elif key in MONEY_FIELDS: money(value, label + '.' + key)
            elif not isinstance(value, str) or len(value) > 500:
                raise ValueError(label + '.' + key + ' must be text of at most 500 characters.')
        # Incomplete DOB remains a preparation block; malformed supplied dates
        # are rejected before any calculation or saved-return acceptance.
        if row['birth_date']:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', row['birth_date']):
                raise ValueError(label + '.birth_date requires YYYY-MM-DD.')
            try: born = date.fromisoformat(row['birth_date'])
            except ValueError: raise ValueError(label + '.birth_date is not a valid calendar date.') from None
            if born > date(2025, 12, 31) or born.year < 1905:
                raise ValueError(label + '.birth_date is outside the 2025 living-child range.')
        rows.append(row)
    group['children'] = rows
    return group


def normalize_extra(data):
    data[GROUP] = normalize_group(data[GROUP])
    return data


def ui_schema():
    prefix = GROUP + '.children.*.'
    fields = {GROUP + '.enabled': {'type': 'boolean', 'label': 'Elect to report child interest and dividends',
        'help': 'Each elected child needs a separate Form 8814. This election can increase tax; compare with the child filing separately before electing.'}}
    labels = {
        'name': 'Child full name', 'ssn': 'Child SSN', 'birth_date': 'Child date of birth (YYYY-MM-DD)',
        'full_time_student': 'Full-time student for at least five calendar months in 2025',
        'taxable_interest': 'Child taxable interest — Form 8814 line 1a',
        'tax_exempt_interest': 'Child tax-exempt interest — line 1b',
        'ordinary_dividends': 'Child ordinary dividends, including qualified dividends — line 2a',
        'qualified_dividends': 'Qualified dividends included above — line 2b',
        'capital_gain_distributions': 'Ordinary capital gain distributions — line 3',
        'eligible_parent_confirmed': 'This parent is eligible to make the election',
        'only_interest_dividends_confirmed': 'Child had only interest, dividends and capital gain distributions',
        'return_required_confirmed': 'Child is required to file a 2025 return',
        'no_withholding_or_estimated_payments_confirmed': 'No child federal withholding, estimated payments or prior-year credit applied to 2025',
        'not_joint_return_confirmed': 'Child is not filing a joint return',
        'not_reported_elsewhere_confirmed': 'These child amounts are not also entered elsewhere in this return or another return',
        'ordinary_domestic_income_confirmed': 'Ordinary domestic amounts; no Alaska dividends, nominee adjustments, foreign accounts/trusts or K-1 amounts',
        'no_private_activity_bond_interest_confirmed': 'Child tax-exempt interest has no private activity bond AMT preference',
        'qualified_eligibility_confirmed': 'Child qualified dividend eligibility and holding periods verified',
        'ordinary_capital_distribution_confirmed': 'Child capital distributions have no 25%, 28% or Section 1202 components'}
    for key, default in row_templates()[GROUP + '.children'].items():
        fields[prefix + key] = {'type': 'boolean' if type(default) is bool else 'money' if key in MONEY_FIELDS else 'text',
                               'label': labels[key], 'help': ''}
    fields[prefix + 'eligible_parent_confirmed']['help'] = 'Verify joint-parent, custodial-parent and higher-taxable-income rules in IRS Form 8814 instructions. This app does not infer another parent’s income or custody.'
    fields[prefix + 'birth_date']['help'] = 'January 1 birthdays count as the attained age on the preceding December 31 for this election. Under 19, or under 24 with verified full-time student status.'
    for key in MONEY_FIELDS:
        fields[prefix + key]['help'] = 'Enter the child’s full annual total, summing source amounts including cents before entering this completed form line. Do not enter this full amount again in parent interest/dividend records.'
    return {'ui_fields': fields, 'ui_modules': [{'id': GROUP, 'label': 'Child Interest and Dividends — Form 8814',
            'step': 'income', 'description': 'Per-child election, allocations into parent income, and additional tax with explicit eligibility checks.'}]}


def calculate(data, context=None):
    group = normalize_group(data)
    result = {'module': 'form_8814', 'tax_year': 2025, 'can_compute': True,
              'blocking_issues': [], 'warnings': [], 'trace': [], 'form_lines': {'children': []},
              'parent_ordinary_other_income': 0, 'parent_qualified_dividends': 0,
              'parent_capital_gain': 0, 'additional_tax': 0,
              'niit_other_investment_income': 0, 'eitc_other_investment_income': 0,
              'investment_interest_other_income': 0, 'elected_child_count': 0}
    def require(condition, message):
        if not condition:
            result['can_compute'] = False
            if message not in result['blocking_issues']: result['blocking_issues'].append(message)
    if not group['enabled']:
        require(not group['children'], 'Disabled Form 8814 election contains child records. Enable the election or remove the records.')
        return result
    require(bool(group['children']), 'Form 8814 election requires at least one child record.')
    seen = set(); multiple = len(group['children']) > 1
    for index, row in enumerate(group['children']):
        label = 'Form 8814 child ' + str(index + 1)
        before = len(result['blocking_issues'])
        tin = row['ssn'].replace('-', '')
        require(bool(row['name'].strip()) and bool(re.fullmatch(r'\d{9}', tin)), label + ': child name and documented nine-digit SSN are required.')
        require(not tin or tin not in seen, label + ': duplicate child SSN.')
        if tin: seen.add(tin)
        require(bool(row['birth_date']), label + ': child date of birth is required.')
        if row['birth_date']:
            born = date.fromisoformat(row['birth_date'])
            # The IRS January 1 rule is equivalently expressed by Jan 2 bounds.
            age_eligible = born >= date(2007, 1, 2) or born >= date(2002, 1, 2) and row['full_time_student']
            require(age_eligible, label + ': child must be under 19, or under 24 and a full-time student, using the IRS January 1 birthday rule.')
        for key in CONFIRMATIONS: require(row[key], label + ': confirm ' + key + '.')
        raw = {key: money(row[key], label + '.' + key) for key in MONEY_FIELDS}
        require(raw['qualified_dividends'] <= raw['ordinary_dividends'], label + ': qualified dividends cannot exceed ordinary dividends.')
        if raw['qualified_dividends']: require(row['qualified_eligibility_confirmed'], label + ': qualified dividend eligibility and holding periods must be verified.')
        if raw['capital_gain_distributions']: require(row['ordinary_capital_distribution_confirmed'], label + ': special 25%, 28% and Section 1202 capital distributions require a separate allocation profile.')
        raw_gross = raw['taxable_interest'] + raw['ordinary_dividends'] + raw['capital_gain_distributions']
        require(raw_gross < D('13500'), label + ': gross income must be less than $13,500 for the 2025 election.')
        lines = {'1a': whole(raw['taxable_interest']), '1b': whole(raw['tax_exempt_interest']),
                 '2a': whole(raw['ordinary_dividends']), '2b': whole(raw['qualified_dividends']),
                 '3': whole(raw['capital_gain_distributions'])}
        lines['4'] = lines['1a'] + lines['2a'] + lines['3']
        require(lines['4'] < 13500, label + ': rounded Form 8814 line 4 is $13,500 or more; the printed form does not permit the election.')
        lines.update({'5': None, '6': None, '7': None, '8': None, '9': None, '10': None, '11': None, '12': None})
        if lines['4'] > 2700:
            lines['5'] = 2700; lines['6'] = lines['4'] - 2700
            if lines['2b'] or lines['3']:
                with localcontext() as decimal_context:
                    decimal_context.prec = 40
                    q_ratio = (D(lines['2b']) / D(lines['4'])).quantize(D('.001'), rounding=ROUND_HALF_UP)
                    c_ratio = (D(lines['3']) / D(lines['4'])).quantize(D('.001'), rounding=ROUND_HALF_UP)
                lines['7'] = format(q_ratio, '.3f'); lines['8'] = format(c_ratio, '.3f')
                lines['9'] = whole(D(lines['6']) * q_ratio); lines['10'] = whole(D(lines['6']) * c_ratio)
            else: lines['9'] = None; lines['10'] = None
            lines['11'] = (lines['9'] or 0) + (lines['10'] or 0)
            lines['12'] = lines['6'] - lines['11']
            require(lines['12'] >= 0, label + ': three-place allocation rounding produced a negative residual; a reviewed higher-precision allocation is required.')
        lines['13'] = 1350; lines['14'] = max(0, lines['4'] - 1350)
        lines['15'] = 135 if lines['14'] >= 1350 else whole(D(lines['14']) * D('.10'))
        valid = len(result['blocking_issues']) == before
        packet = {'name': row['name'].strip(), 'ssn': row['ssn'], 'birth_date': row['birth_date'],
                  'multiple_children': multiple, 'eligibility_confirmed': valid, **lines,
                  'source_totals': {key: str(value) for key, value in raw.items()}}
        result['form_lines']['children'].append(packet)
        # Blocked rows remain visible as review workpapers, never enter a
        # completed parent return as partially accepted or guessed income.
        if not valid: continue
        ordinary = lines['12'] or 0; qualified = lines['9'] or 0; capital = lines['10'] or 0
        result['elected_child_count'] += 1
        result['parent_ordinary_other_income'] += ordinary
        result['parent_qualified_dividends'] += qualified
        result['parent_capital_gain'] += capital
        result['additional_tax'] += lines['15']
        result['niit_other_investment_income'] += ordinary
        result['eitc_other_investment_income'] += ordinary + lines['1b']
        result['investment_interest_other_income'] += ordinary
    result['warnings'].append('Form 8814 is an elected method. It can increase tax or reduce parent deductions/credits; no comparison with a separately filed child return has been performed.')
    for label, key in (('Schedule 1 line 8z — Form 8814', 'parent_ordinary_other_income'),
                       ('Form 1040 lines 3a and 3b — Form 8814', 'parent_qualified_dividends'),
                       ('Schedule D line 13 / Form 1040 line 7a — Form 8814', 'parent_capital_gain'),
                       ('Form 1040 line 16 additional tax — Form 8814', 'additional_tax')):
        result['trace'].append({'label': label, 'amount': result[key], 'source': SOURCES['f8814']})
    return result
