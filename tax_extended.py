"""Independent IRS2025 EITC, NIIT, AMT and passive rental worksheets.

Pure stdlib, Decimal money, explicit eligibility, no runtime network. Inputs
reference verified source documents; long-tail special transactions are listed
in blocking_issues rather than silently processed as ordinary transactions.
"""
from bisect import bisect_right
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR
from datetime import date, timedelta
import re

D=Decimal
URL='https://www.irs.gov/pub/irs-pdf/'


def person_date_rules(person, path='taxpayer'):
    """TY2025 age policies, independently written from IRS p596/p501/i1040gi.

    An EIC upper age65 boundary uses the birthday itself. Standard/Schedule1A
    age65 and EIC lower age25 use the day before the birthday. Never use one
    generic age>=65 test for both. No DOB keeps the legacy explicit-age input.
    """
    dates={}
    for key in ('birth_date','death_date'):
        value=person.get(key,'')
        if not isinstance(value,str) or value and not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
            raise ValueError(path+'.'+key+' must be an ISO date YYYY-MM-DD or an empty value.')
        try:dates[key]=date.fromisoformat(value) if value else None
        except ValueError:raise ValueError(path+'.'+key+' is not a valid calendar date.') from None
    dob,death=dates['birth_date'],dates['death_date'];end=date(2025,12,31)
    if death and death.year!=2025:raise ValueError(path+'.death_date must be in tax year2025; earlier spouse deaths do not belong in this field.')
    if death and not dob:raise ValueError(path+'.birth_date is required to evaluate age at death.')
    if dob and not date(1905,1,1)<=dob<=end:raise ValueError(path+'.birth_date must be between1905-01-01 and2025-12-31.')
    if dob and death and death<dob:raise ValueError(path+'.death_date cannot precede birth_date.')
    reference=death or end
    def years(on):return on.year-dob.year-int((on.month,on.day)<(dob.month,dob.day))
    calendar_age=years(reference) if dob else person.get('age',0)
    # This reproduces the published Jan1 and day-before examples, including
    # Gregorian leap-year validation, without parsing locale-dependent dates.
    prior_day_age=years(reference+timedelta(days=1)) if dob else person.get('age',0)
    return {'birth_date':person.get('birth_date',''),'death_date':person.get('death_date',''),
            'reference_date':reference.isoformat(),'basis':'birth_date' if dob else 'explicit_age',
            'calendar_age':calendar_age,'day_before_birthday_age':prior_day_age,
            'senior_age65':prior_day_age>=65,
            'no_child_eic_age_eligible':prior_day_age>=25 and calendar_age<65,
            'sources':[URL+'p596.pdf',URL+'p501.pdf',URL+'i1040gi.pdf']}


def senior_age65(person):return person_date_rules(person)['senior_age65']


def no_child_eic_age_eligible(person):return person_date_rules(person)['no_child_eic_age_eligible']


def whole(value):return int(D(value).quantize(D('1'),rounding=ROUND_HALF_UP))


def amount(value,path,signed=False):
    if not isinstance(value,str) or not re.fullmatch(r'-?\d{1,12}(?:\.\d{1,2})?',value):raise ValueError(path+' must be a decimal USD string with at most two fractional digits.')
    number=D(value)
    if number<0 and not signed:raise ValueError(path+' cannot be negative.')
    return whole(number)


def default_inputs():
    return {
      'eitc':{'claim':False,'eligibility_confirmed':False,'main_home_us_half_year':False,
              'not_qualifying_child_of_another':False,'no_disallowed_claim_history':False,
              'mfs_qualifying_separation':False},
      'niit':{'eligibility_confirmed':False,'allocable_state_income_tax':'0',
              'deductions_confirmed':False,'investment_interest_eligible':False,
              'investment_interest_carryover':'0','carryover_confirmed':False},
      'amt':{'eligibility_confirmed':False,'iso_adjustment':'0','private_activity_bond_interest':'0',
             'other_adjustments':'0','capital_gain_adjustment':'0',
             'special_distribution_same_basis_confirmed':False},
      'rentals':[]}


RENTAL_TEMPLATE={
 'name':'','owner':'taxpayer','rent':'0','advertising':'0','auto_travel':'0','cleaning':'0',
 'commissions':'0','insurance':'0','legal_professional':'0','management_fees':'0',
 'mortgage_interest':'0','other_interest':'0','repairs':'0','supplies':'0','taxes':'0',
 'utilities':'0','depreciation':'0','other_expenses':'0','prior_unallowed_loss':'0',
 'eligibility_confirmed':False,'active_participation':False,'ownership_at_least_10_percent':False,
 'at_risk_confirmed':False,'no_personal_use_or_substantial_services':False,
 'depreciation_schedule_confirmed':False,'prior_loss_active_participation':False,
 'prior_loss_amount_confirmed':False,'qbi_eligible':False,'qbi_status_confirmed':False,
 'niit_carryover_eligible':False,'same_amt_basis_and_depreciation':False}

DEPENDENT_FIELDS={'eitc_qualifying_child':False,'eitc_status_reviewed':False,'eitc_relationship_residency_confirmed':False,
 'eitc_tiebreaker_confirmed':False,'eitc_full_time_student':False,'eitc_permanently_disabled':False}


def ui_schema():
    labels={'eitc':'Earned Income Credit','niit':'Net Investment Income Tax','amt':'Alternative Minimum Tax','rentals':'Rental Properties'}
    fields={}
    groups=default_inputs()
    for group,values in groups.items():
        template=RENTAL_TEMPLATE if group=='rentals' else values
        for name,value in template.items():
            path=group+('.*.' if group=='rentals' else '.')+name
            descriptor={'label':name.replace('_',' ').capitalize(),'type':'boolean' if type(value) is bool else 'money','help':''}
            if name=='name':descriptor['type']='text'
            if name=='owner':descriptor.update(type='enum',options=[{'value':'taxpayer','label':'Taxpayer'},{'value':'spouse','label':'Spouse (joint return)'}])
            if name in ('other_adjustments','capital_gain_adjustment'):descriptor['signed']=True
            if group=='amt' and name.endswith('adjustment') or group=='amt' and name=='other_adjustments':descriptor['help']='Verified regular-vs-AMT difference from source records; do not enter gross exercise proceeds or an unsupported basis guess.'
            if group=='amt' and name=='special_distribution_same_basis_confirmed':
                descriptor.update(label='I verified the same capital basis for regular tax and AMT',
                    help='For these1099-DIV special distributions, verify no AMT capital-basis adjustment, basis carry-in or separate AMT ScheduleD difference. A zero adjustment amount alone is not confirmation. Leave unchecked until verified.')
            if name=='depreciation':descriptor['help']='Deductible amount from the verified asset depreciation schedule; new-asset Form4562 computation is not performed here.'
            if name=='allocable_state_income_tax':descriptor['help']='Only the actual itemized income tax allocated to investment income. Property taxes and amounts excluded by the SALT limit are not included.'
            fields[path]=descriptor
    for name in DEPENDENT_FIELDS:fields['dependents.*.'+name]={'label':name.replace('_',' ').capitalize(),'type':'boolean','help':'EITC child residency/tiebreaker tests differ from child-tax-credit tests.'}
    return {'ui_fields':fields,'ui_modules':[{'id':key,'label':label,'step':'income' if key=='rentals' else 'deductions','description':'IRS2025 source-based worksheet with explicit qualification checks.'} for key,label in labels.items()]}


def normalize_extra(data,status):
    for group,template in default_inputs().items():
        if group=='rentals':continue
        submitted=data[group]
        if not isinstance(submitted,dict):raise ValueError(group+' must be an object.')
        unknown=set(submitted)-set(template)
        if unknown:raise ValueError('Unknown '+group+' fields: '+', '.join(sorted(unknown)))
        normalized=deepcopy(template);normalized.update(submitted)
        for key,value in normalized.items():
            if isinstance(template[key],bool):
                if type(value) is not bool:raise ValueError(group+'.'+key+' must be boolean.')
            else:amount(value,group+'.'+key,signed=group=='amt' and key in ('other_adjustments','capital_gain_adjustment'))
        data[group]=normalized
    if not isinstance(data['rentals'],list) or len(data['rentals'])>500:raise ValueError('rentals must contain at most500 property records.')
    rows=[]
    for index,row in enumerate(data['rentals']):
        if not isinstance(row,dict):raise ValueError('Rental row must be an object.')
        unknown=set(row)-set(RENTAL_TEMPLATE)
        if unknown:raise ValueError('Unknown rental fields: '+', '.join(sorted(unknown)))
        merged=deepcopy(RENTAL_TEMPLATE);merged.update(row)
        for key,value in merged.items():
            path=f'rentals[{index}].{key}'
            if isinstance(RENTAL_TEMPLATE[key],bool):
                if type(value) is not bool:raise ValueError(path+' must be boolean.')
            elif key=='owner':
                if value not in ('taxpayer','spouse') or value=='spouse' and status!='mfj':raise ValueError(path+' spouse income only belongs in MFJ.')
            elif key=='name':
                if not isinstance(value,str) or len(value)>1000:raise ValueError(path+' must be text.')
            else:amount(value,path)
        rows.append(merged)
    data['rentals']=rows
    return data


def result(source):return {'blocking_issues':[],'warnings':[],'trace':[],'form_lines':{},'source':URL+source+'.pdf'}


def allocation(total,weights):
    """Largest remainders retain exact integer totals across property rows."""
    if not weights or not sum(weights):return [0]*len(weights)
    raw=[D(total)*D(value)/D(sum(weights)) for value in weights]
    allocated=[int(value.to_integral_value(rounding=ROUND_FLOOR)) for value in raw]
    for index in sorted(range(len(weights)),key=lambda i:(raw[i]-allocated[i],-i),reverse=True)[:total-sum(allocated)]:allocated[index]+=1
    return allocated


def rental_return(rows,context):
    output=result('f8582');properties=[]
    expense_keys=[key for key in RENTAL_TEMPLATE if key not in ('name','owner','rent','prior_unallowed_loss') and not isinstance(RENTAL_TEMPLATE[key],bool)]
    for index,row in enumerate(rows):
        for key in ('eligibility_confirmed','at_risk_confirmed','no_personal_use_or_substantial_services','qbi_status_confirmed','same_amt_basis_and_depreciation'):
            if not row[key]:output['blocking_issues'].append(f'Rental {index+1}: confirm {key}. Only ordinary US passive real-estate rentals, no vacation-home/self-rental/services/disposal/REP special cases, are computed.')
        if amount(row['depreciation'],'depreciation') and not row['depreciation_schedule_confirmed']:output['blocking_issues'].append(f'Rental {index+1}: verify existing asset depreciation schedule; a new depreciation/recapture calculation is not supplied by this input.')
        prior=amount(row['prior_unallowed_loss'],'prior_unallowed_loss')
        if prior and not row['prior_loss_amount_confirmed']:output['blocking_issues'].append(f'Rental {index+1}: prior-year Form8582 suspended loss must be verified.')
        if prior and row['qbi_eligible']:output['blocking_issues'].append(f'Rental {index+1}: QBI character of prior passive carryover requires a separate verified199A loss record not implemented in this rental carry-in.')
        rent=amount(row['rent'],'rent');expenses=sum(amount(row[key],key) for key in expense_keys);profit=rent-expenses
        active=row['active_participation'] and row['ownership_at_least_10_percent'] and (not prior or row['prior_loss_active_participation'])
        properties.append({'name':row['name'],'owner':row['owner'],'rent':rent,'expenses':expenses,'current_profit_loss':profit,'prior_loss':prior,'overall':profit-prior,'active_allowance_eligible':active,'qbi_eligible':row['qbi_eligible'],'niit_carryover_eligible':row['niit_carryover_eligible']})
    overall=sum(row['overall'] for row in properties);active_net=sum(row['overall'] for row in properties if row['active_allowance_eligible'])
    # i8582 line6 excludes passive net losses, taxableSS, IRA/student deductions
    # AND deductible one-half SE tax. HSA and SE-health deductions remain.
    magi=max(0,context['magi_without_rentals']+max(0,overall))
    status=context['filing_status'];mfs=status=='mfs'
    ceiling=12500 if mfs else 25000;phase_start=50000 if mfs else 100000;phase_end=75000 if mfs else 150000
    capacity=max(0,min(ceiling,whole(D(max(0,phase_end-magi))*D('.5'))))
    if mfs and context['mfs_lived_with_spouse']:capacity=0
    allowance=min(max(0,-active_net),max(0,-overall),capacity)
    loss_weights=[max(0,-row['overall']) for row in properties]
    special_weights=[value if row['active_allowance_eligible'] else 0 for row,value in zip(properties,loss_weights)]
    specials=allocation(allowance,special_weights)
    remaining=[loss-special for loss,special in zip(loss_weights,specials)]
    suspended_total=max(0,-overall-allowance)
    suspended=allocation(suspended_total,remaining)
    for row,special,unused in zip(properties,specials,suspended):
        row.update(special_allowance=special,suspended_loss_carryout=unused,reported_income_loss=row['overall']+unused)
    income=sum(row['reported_income_loss'] for row in properties)
    if income!=(max(0,overall)-allowance):raise ArithmeticError('Rental allocation did not preserve the allowed income/loss.')
    output.update(income=income,properties=properties,magi=magi,qbi=sum(row['reported_income_loss'] for row in properties if row['qbi_eligible']),
                  suspended_loss_carryout=suspended_total,niit_income=income,
                  form_lines={'1d':active_net,'3':overall,'5':phase_end,'6':magi,'8':capacity,'9':allowance,'10':sum(max(0,row['overall']) for row in properties),'11':sum(loss_weights)-suspended_total})
    return output


def eic_table(amount_value,status,children,rules):
    amount_value=max(0,int(amount_value));family='mfj' if status=='mfj' else 'single';children=min(3,children)
    if amount_value>=rules['eic_limits'][family][children] or amount_value==0:return 0
    rows=rules['eic_table'];row=rows[bisect_right([r[0] for r in rows],amount_value)-1]
    return row[(6 if family=='mfj' else 2)+children]


def earned_income_credit(data,context,rules):
    output=result('i1040gi');output.update(credit=0,qualifying_children=0,ineligible_reasons=[],excluded_children=[])
    if not data['claim']:return output
    if not data['eligibility_confirmed']:output['blocking_issues'].append('EITC qualification facts must be reviewed and confirmed.');return output
    for key in ('not_qualifying_child_of_another','no_disallowed_claim_history'):
        if not data[key]:output['blocking_issues'].append('EITC requires '+key+'; Form8862 or child-of-another exceptions are not modeled.')
    persons=context['taxpayer'],context['spouse'];status=context['filing_status']
    if not persons[0]['valid_ssn'] or status=='mfj' and not persons[1]['valid_ssn']:output['ineligible_reasons'].append('Required taxpayer/spouse employment-valid SSN by the due date is absent.')
    if persons[0]['can_be_claimed'] or status=='mfj' and persons[1]['can_be_claimed']:output['ineligible_reasons'].append('Taxpayer/spouse can be claimed as a dependent.')
    children=[]
    for index,child in enumerate(context['dependents']):
        if not child['eitc_qualifying_child']:
            if not child['eitc_status_reviewed']:output['blocking_issues'].append(f'Dependent {index+1}: explicitly review EITC qualifying-child status before computing a no-child or fewer-child credit.')
            continue
        if not(child['eitc_relationship_residency_confirmed'] and child['eitc_tiebreaker_confirmed']):output['blocking_issues'].append(f'EITC child {index+1}: relationship, US-residency, joint-return and tiebreaker facts are unconfirmed.')
        age_ok=child['age']<19 or child['age']<24 and child['eitc_full_time_student'] or child['eitc_permanently_disabled']
        younger=child['eitc_permanently_disabled'] or child['age']<persons[0]['age'] or status=='mfj' and child['age']<persons[1]['age']
        if child['valid_ssn'] and age_ok and younger:children.append(index+1)
        else:output['excluded_children'].append({'index':index+1,'reason':'Child cannot be counted in the EITC table age/SSN column; other eligible children or self-only credit can still apply.'})
    n=min(3,len(children));output['qualifying_children']=n
    if status=='mfs' and (not n or not data['mfs_qualifying_separation']):output['ineligible_reasons'].append('MFS requires a qualifying child and statutory living-apart/legal-separation exception.')
    if n==0:
        if not (no_child_eic_age_eligible(persons[0]) or status=='mfj' and no_child_eic_age_eligible(persons[1])):output['ineligible_reasons'].append('No-child EITC age25-through64 test is not met.')
        if not data['main_home_us_half_year']:output['ineligible_reasons'].append('No-child EITC principal home must be in the US more than half the year.')
    if context['investment_income']>11950:output['ineligible_reasons'].append('2025 investment income exceeds11950.')
    family='mfj' if status=='mfj' else 'single';limit=rules['eic_limits'][family][n]
    earned=max(0,context['earned_income']);agi=context['agi']
    if earned<=0 or earned>=limit or agi>=limit:output['ineligible_reasons'].append('Earned income/AGI does not meet the2025 EITC limits.')
    if output['ineligible_reasons']:return output
    earned_credit=eic_table(earned,status,n,rules)
    phase_start=(17730 if status=='mfj' else 10620) if n==0 else (30470 if status=='mfj' else 23350)
    agi_credit=eic_table(agi,status,n,rules) if agi!=earned and agi>=phase_start else earned_credit
    output.update(credit=min(earned_credit,agi_credit),form_lines={'earned_income':earned,'earned_table_credit':earned_credit,'agi':agi,'agi_table_credit':agi_credit,'credit':min(earned_credit,agi_credit)},children_indices=children)
    return output


def investment_interest(data,context):
    output=result('f4952');paid=context['paid'];carry=amount(data['investment_interest_carryover'],'niit.investment_interest_carryover')
    if (paid or carry) and not data['investment_interest_eligible']:output['blocking_issues'].append('Investment interest requires verified investment-loan allocation, no exempt-income/personal/passive interest and no preferred-gain election.')
    if carry and not data['carryover_confirmed']:output['blocking_issues'].append('Verify prior Form4952 line7 investment-interest carryover.')
    income=max(0,context['interest']+context['ordinary_dividends']-context['qualified_dividends']+context['annuity']+context.get('other_investment_income',0)+max(0,context['net_gain']-context['preferred_gain']))
    deduction=min(paid+carry,income);output.update(deduction=deduction,carryout=max(0,paid+carry-income),form_lines={'1':paid,'2':carry,'3':paid+carry,'4h':income,'6':income,'7':max(0,paid+carry-income),'8':deduction})
    return output


def net_investment_tax(data,context):
    output=result('f8960');status=context['filing_status'];threshold=250000 if status in ('mfj','qss') else 125000 if status=='mfs' else 200000
    investment=context['interest']+context['ordinary_dividends']+context['annuity']+context['rental_income']+context['capital_gain_loss']+context.get('other_investment_income',0)
    state=amount(data['allocable_state_income_tax'],'niit.allocable_state_income_tax')
    if state>context['itemized_salt']:raise ValueError('NIIT allocable income taxes cannot exceed the SALT amount actually deducted on ScheduleA.')
    if state and not data['deductions_confirmed']:output['blocking_issues'].append('NIIT income-tax allocation must be substantiated; property tax and nondeducted SALT are excluded.')
    deductions=state+context['deducted_investment_interest'];nii=max(0,investment-deductions);excess=max(0,context['agi']-threshold)
    tax=whole(D(min(nii,excess))*D('.038'))
    if nii and excess and not data['eligibility_confirmed']:output['blocking_issues'].append('Form8960 NIIT sources/exclusions and deductions must be confirmed; foreign/entity/disposal adjustments are not inferred.')
    if nii and excess and context['rental_prior_loss_unverified']:output['blocking_issues'].append('Rental carry-in NIIT character/pre2013 treatment requires a verified NIIT loss record.')
    # Fill the printed component rows as well as their totals. The supported
    # profile has ordinary passive rentals and capital gains/losses with no
    # non-section1411, entity-disposal or foreign-company adjustments. Those
    # unsupported adjustments are not inferred from a subtotal.
    output.update(tax=tax,form_lines={
        '1':context['interest'],'2':context['ordinary_dividends'],'3':context['annuity'],
        '4a':context['rental_income'],'4b':0,'4c':context['rental_income'],
        '5a':context['capital_gain_loss'],'5b':0,'5c':0,'5d':context['capital_gain_loss'],
        '6':0,'7':context.get('other_investment_income',0),'8':investment,
        '9a':context['deducted_investment_interest'],'9b':state,'9c':0,'9d':deductions,
        '10':0,'11':deductions,'12':nii,'13':context['agi'],'14':threshold,
        '15':excess,'16':min(nii,excess),'17':tax})
    return output


def amt_rate(income,status):
    bracket=119550 if status=='mfs' else 239100
    return whole(D(min(income,bracket))*D('.26')+D(max(0,income-bracket))*D('.28'))


def alternative_minimum_tax(data,context,rules):
    output=result('f6251');status=context['filing_status']
    prefs={key:amount(data[key],'amt.'+key,signed=key in ('other_adjustments','capital_gain_adjustment')) for key in ('iso_adjustment','private_activity_bond_interest','other_adjustments','capital_gain_adjustment')}
    if (any(prefs.values()) or not context['no_amt_preferences']) and not data['eligibility_confirmed']:output['blocking_issues'].append('AMT preference amounts and regular-vs-AMT basis/depreciation/related adjustments require explicit confirmation.')
    line1a=context['total_deductions']-context['senior_deduction'];line1b=context['agi']-line1a
    amti=line1b+context['deduction_addback']+sum(prefs.values())
    if status=='mfs' and amti>900350:amti+=min(68500,whole(D(amti-900350)*D('.25')))
    base_exemption=137000 if status in ('mfj','qss') else 68500 if status=='mfs' else 88100
    phase_start=1252700 if status in ('mfj','qss') else 626350
    exemption=max(0,base_exemption-whole(D(max(0,amti-phase_start))*D('.25')))
    taxable=max(0,amti-exemption)
    pref=max(0,context['preferred_income']+prefs['capital_gain_adjustment'])
    if context['preferred_income']+prefs['capital_gain_adjustment']<0:output['blocking_issues'].append('AMT capital adjustment crosses gain/loss classification; a separate AMT ScheduleD loss worksheet is required.')
    special=context.get('special_distribution_worksheet')
    if special and not data['special_distribution_same_basis_confirmed']:
        output['blocking_issues'].append('Special-rate distribution AMT requires separate confirmation that the capital basis is the same for regular tax and AMT; a zero capital_gain_adjustment alone does not establish this fact.')
    if special and prefs['capital_gain_adjustment']:
        output['blocking_issues'].append('Special-rate distributions with a different AMT capital basis require a separate AMT ScheduleD and are not supported.')
    # The distribution-only profile has identical regular/AMT capital basis.
    # Form6251 lines13/14/15 use ScheduleD worksheet13, ScheduleD19, and
    # worksheet10. Collectibles remain in the AMT 26/28% ordinary bucket;
    # unrecaptured1250 is separately capped at25% in lines35 through37.
    sd=special['form_lines'] if special else None
    line13=sd['13'] if special else pref
    line14=special['unrecaptured_1250_gain'] if special else 0
    line15=min(line13+line14,sd['10']) if special else line13
    line16=min(taxable,line15);ordinary=max(0,taxable-line16);ordinary_tax=amt_rate(ordinary,status)
    zero_limit,fifteen_limit=rules['capital_rates'][status]
    # PartIII zero/15% space is determined by REGULAR ordinary taxable income,
    # while the amount of gain and ordinary tax come from the AMT worksheet.
    regular_ordinary=sd['14'] if special else context['regular_ordinary_income']
    regular_fifteen_base=sd['21'] if special else regular_ordinary
    space_zero=max(0,zero_limit-regular_ordinary)
    line22=min(taxable,line13);at_zero=min(space_zero,line22)
    remaining=line22-at_zero
    space_fifteen=max(0,fifteen_limit-(space_zero+regular_fifteen_base))
    at_fifteen=min(remaining,space_fifteen);at_twenty=max(0,remaining-at_fifteen)
    line32=at_zero+at_fifteen
    line35=line36=line37=0
    if line32!=taxable and line14:
        line35=ordinary+line32+at_twenty
        line36=taxable-line35
        line37=whole(D(line36)*D('.25'))
    preferred_tax=ordinary_tax+whole(D(at_fifteen)*D('.15'))+whole(D(at_twenty)*D('.20'))+line37
    preliminary=min(preferred_tax,amt_rate(taxable,status));tmt=preliminary
    tax=max(0,tmt-context['regular_tax'])
    # TY2025 Form6251 line5 uses the same filing-status exemption for all ages.
    # The separate Form8615 kiddie-tax computation is screened by the caller.
    output.update(tax=tax,form_lines={'1a':line1a,'1b':line1b,'2a':context['deduction_addback'],'2g':prefs['private_activity_bond_interest'],'2i':prefs['iso_adjustment'],'2k':prefs['capital_gain_adjustment'],'3':prefs['other_adjustments'],'4':amti,'5':exemption,'6':taxable,'7':preliminary,'8':0,'9':tmt,'10':context['regular_tax'],'11':tax,'12':taxable,'13':line13,'14':line14,'15':line15,'16':line16,'17':ordinary,'18':ordinary_tax,'19':zero_limit,'20':regular_ordinary,'21':space_zero,'22':line22,'23':at_zero,'24':remaining,'25':fifteen_limit,'26':space_zero,'27':regular_fifteen_base,'28':space_zero+regular_fifteen_base,'29':space_fifteen,'30':at_fifteen,'31':whole(D(at_fifteen)*D('.15')),'32':line32,'33':at_twenty,'34':whole(D(at_twenty)*D('.20')),'35':line35,'36':line36,'37':line37,'38':preferred_tax,'39':amt_rate(taxable,status),'40':preliminary})
    if special:
        output.update(special_distribution_full_partIII=True,
            special_distribution_zero_liability_proved=tax==0,
            special_distribution_regular_tax=context['regular_tax'],
            special_distribution_same_capital_basis=data['special_distribution_same_basis_confirmed'] and not prefs['capital_gain_adjustment'])
    return output
