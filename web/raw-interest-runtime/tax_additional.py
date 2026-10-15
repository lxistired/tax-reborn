"""Independent TY2025 Forms2441/8880 and ScheduleR; pure Decimal worksheets."""
from copy import deepcopy
from decimal import Decimal,ROUND_HALF_UP,ROUND_CEILING
import re

D=Decimal
SOURCES={name:'https://www.irs.gov/pub/irs-pdf/'+name+'.pdf' for name in ('f2441','i2441','f8880','f1040sr','i1040sr')}


def default_inputs():
    return {
      'care':{'enabled':False,'beneficiaries':[],'providers':[],
              'work_related_expenses_confirmed':False,'provider_information_confirmed':False,
              'no_double_benefit_confirmed':False,'mfs_qualifying_separation':False,
              'benefits_carry_in':'0','benefits_forfeited_or_carried_out':'0','benefits_expenses_incurred':'0',
              'benefits_plan_limit':'5000','benefits_qualification_confirmed':False,
              'self_employed_benefits':'0','prior_year_expenses_paid':'0',
              'deemed_income_months':[],'deemed_income_eligibility_confirmed':False},
      'saver':{'enabled':False,'taxpayer_full_time_student':False,'spouse_full_time_student':False,
               'taxpayer_employer_contributions':'0','spouse_employer_contributions':'0',
               'taxpayer_able_contributions':'0','spouse_able_contributions':'0',
               'taxpayer_distributions':'0','spouse_distributions':'0',
               'current_year_excluded_distributions':'0',
               'contributions_eligibility_confirmed':False,'distribution_window_and_exclusions_confirmed':False,
               'all_distribution_years_joint':True},
      'elderly_credit':{'enabled':False,'eligibility_confirmed':False,'mfs_lived_apart_entire_year':False,
                        'taxpayer_after_minimum_retirement_age_confirmed':False,'spouse_after_minimum_retirement_age_confirmed':False,
                        'taxpayer_permanently_disabled':False,'spouse_permanently_disabled':False,
                        'taxpayer_taxable_disability_income':'0','spouse_taxable_disability_income':'0',
                        'disability_income_in_return_confirmed':False,'physician_statement_confirmed':False,
                        'other_nontaxable_pensions':'0','nontaxable_benefits_confirmed':False}}


def row_templates():
    return {
      'care.beneficiaries':{'beneficiary_id':'','name':'','age':8,'disabled_incapable_self_care':False,
                           'care_before_13th_birthday_confirmed':False,'qualification_residency_confirmed':False,
                           'valid_tin':True,'qualified_expenses':'0'},
      'care.providers':{'name':'','address':'','tin':'','amount_paid':'0','household_employee':False,'eligible_provider_confirmed':False},
      'care.deemed_income_months':{'month':1,'taxpayer_income':'0','spouse_income':'0','deemed_owner':'none'}}


def whole(value):return int(D(value).quantize(D('1'),rounding=ROUND_HALF_UP))


def money(value,label,signed=False):
    if not isinstance(value,str) or not re.fullmatch(r'-?\d{1,12}(?:\.\d{1,2})?',value):raise ValueError(label+' must be a USD decimal string with at most two fractional digits.')
    result=D(value)
    if result<0 and not signed:raise ValueError(label+' cannot be negative.')
    return result


def context_money(context,key,signed=False):
    value=context.get(key,0)
    if type(value) is not int or value<0 and not signed:raise ValueError('context.'+key+' must be a whole-dollar integer.')
    return value


def schema(data,template,label):
    if not isinstance(data,dict):raise ValueError(label+' must be an object.')
    unknown=set(data)-set(template)
    if unknown:raise ValueError('Unknown '+label+' fields: '+', '.join(sorted(unknown)))
    result=deepcopy(template);result.update(deepcopy(data))
    for key,default in template.items():
        value=result[key]
        if type(default) is bool and type(value) is not bool:raise ValueError(label+'.'+key+' must be boolean.')
        if isinstance(default,list) and (not isinstance(value,list) or len(value)>500):raise ValueError(label+'.'+key+' must be a list of at most500 rows.')
        if key in ('name','beneficiary_id','address','tin') and (not isinstance(value,str) or len(value)>2000):raise ValueError(label+'.'+key+' must be text of at most2000 characters.')
    return result


def output(name):return {'module':name,'tax_year':2025,'can_compute':True,'nonrefundable_credit':0,'taxable_benefits':0,'blocking_issues':[],'warnings':[],'trace':[],'form_lines':{}}


def require(result,condition,message):
    if not condition:
        result['can_compute']=False
        if message not in result['blocking_issues']:result['blocking_issues'].append(message)


def status(context):
    value=context.get('filing_status')
    if value not in ('single','mfj','mfs','hoh','qss'):raise ValueError('Invalid filing_status.')
    return value


def inactive(data,result,context_populated=False,ignored=()):
    if data['enabled']:return False
    populated=context_populated
    for key,value in data.items():
        if key in ignored:continue
        if isinstance(value,list) and value:populated=True
        if isinstance(value,str) and re.fullmatch(r'-?\d+(?:\.\d+)?',value) and D(value):populated=True
    require(result,not populated,'Disabled '+result['module']+' contains monetary/document data; enable it or remove the entries explicitly.')
    return True


def ui_schema():
    fields={}
    for group,template in default_inputs().items():
        for key,value in template.items():
            if isinstance(value,list):continue
            fields[group+'.'+key]={'label':key.replace('_',' ').capitalize(),'type':'boolean' if type(value) is bool else 'money','help':''}
    for path,template in row_templates().items():
        for key,value in template.items():
            kind='boolean' if type(value) is bool else 'integer' if type(value) is int else 'text' if key in ('beneficiary_id','name','address','tin') else 'money'
            descriptor={'type':kind,'label':key.replace('_',' ').capitalize(),'help':''}
            if key=='deemed_owner':descriptor.update(type='enum',options=['none','taxpayer','spouse'])
            if key in ('taxpayer_income','spouse_income'):descriptor['signed']=True
            fields[path+'.*.'+key]=descriptor
    fields['care.provider_information_confirmed']['help']='VerifiedW10/provider name, address and TIN; no spouse/childparent/dependent/ineligibleunder19provider. Householdemployees require ScheduleH, presently blocked.'
    fields['care.benefits_expenses_incurred']['help']='PartIII expenses incurred in2025 used for employee benefit exclusion; may differ from credit expenses incurred AND paid in2025.'
    fields['care.beneficiaries.*.qualified_expenses']['help']='Gross qualified care incurred AND paid in2025, including amounts paid withFSA benefits. The engine subtracts excluded benefits once; do not subtract them before entry.'
    fields['care.deemed_income_eligibility_confirmed']['help']='Use12 verified monthly earned-income records; each student qualifies under full-time5calendar-month rule or is incapable of self-care. Only one spouse may receive250/500deemed income in the same month.'
    fields['saver.distribution_window_and_exclusions_confirmed']['help']='Eligible distributions after2022 through2025return due date includingextensions; exclude permittedrollovers/conversions/excesscorrections/inheritednonspousalIRA and other formalexceptions.'
    fields['saver.all_distribution_years_joint']['help']='MFJ combines both spouses’ eligible distributions into BOTH columns. If a distribution-year return was notjoint, this simplified pooling is blocked.'
    fields['elderly_credit.other_nontaxable_pensions']['help']='ScheduleR13b statutory exclusions; exclude pensionbasis return, militarydisability and listedForeignService exclusions. NontaxableSocialSecurity is supplied automatically.'
    fields['elderly_credit.disability_income_in_return_confirmed']['help']='ScheduleR qualifying disability income received before employer MANDATORY retirementage. This is separate from MINIMUM retirementage determining1040line1h versus5b.'
    for owner in ('taxpayer','spouse'):fields['elderly_credit.'+owner+'_after_minimum_retirement_age_confirmed']['help']='Only disability pension AFTER employerMINIMUM retirementage goes in regularpension5b and is notEIC/Care earned income. It must still meet ScheduleR preMANDATORY retirementage conditions.'
    return {'ui_fields':fields,'ui_modules':[{'id':key,'label':label,'step':'deductions','description':'IRS2025 nonrefundable credit with explicit qualifications and tax-liability limits.'} for key,label in (('care','Child and Dependent Care'),('saver','Retirement Saver Credit'),('elderly_credit','Elderly or Disabled Credit'))]}


def calculate_care(data,context):
    data=schema(data,default_inputs()['care'],'care');r=output('care');s=status(context)
    benefits=context_money(context,'benefits_received');earned=[context_money(context,'earned_taxpayer',True),context_money(context,'earned_spouse',True)]
    values={key:whole(money(data[key],'care.'+key)) for key in ('benefits_carry_in','benefits_forfeited_or_carried_out','benefits_expenses_incurred','benefits_plan_limit','self_employed_benefits','prior_year_expenses_paid')}
    if inactive(data,r,benefits>0,('benefits_plan_limit',)):return r
    for key in ('work_related_expenses_confirmed','provider_information_confirmed','no_double_benefit_confirmed'):require(r,data[key],'Care: confirm '+key+'; nonwork care, reimbursed/duplicate expenses or ineligible providers cannot be assumed.')
    if s=='mfs':require(r,data['mfs_qualifying_separation'],'MFS care requires last6months livingapart, childmainhome and majorityhouseholdcost conditions; ordinaryMFS benefit spouse-income worksheet is not implemented.')
    require(r,not values['self_employed_benefits'],'Sole-proprietor/partnership dependent-care assistance requires separate deduction/allocation; not implemented.')
    require(r,not values['prior_year_expenses_paid'],'Prior-year care paid thisyear requires Form2441 WorksheetA not implemented here.')
    require(r,not values['benefits_carry_in'],'Prior-yearFSA grace-period benefits require verified owner/year allocation not implemented here.')
    people=[];ids=set();raw_expenses=D(0)
    for item in data['beneficiaries']:
        row=schema(item,row_templates()['care.beneficiaries'],'care.beneficiary')
        if not isinstance(row['beneficiary_id'],str) or not row['beneficiary_id'].strip() or row['beneficiary_id'] in ids:raise ValueError('Care beneficiary IDs must be nonempty and unique.')
        ids.add(row['beneficiary_id'])
        if type(row['age']) is not int or not 0<=row['age']<=120:raise ValueError('Care beneficiary age must be0..120.')
        require(r,row['qualification_residency_confirmed'] and row['valid_tin'],'Care beneficiary: verify qualifyingperson, residency/custodial-parent/support and timelyTIN conditions.')
        require(r,row['age']<13 or row['disabled_incapable_self_care'] or row['age']==13 and row['care_before_13th_birthday_confirmed'],'Care expenses must be for care before13thbirthday or a person incapable of self-care.')
        raw_expenses+=money(row['qualified_expenses'],'care.qualified_expenses');people.append(row)
    for item in data['providers']:
        row=schema(item,row_templates()['care.providers'],'care.provider');money(row['amount_paid'],'care.provider.amount_paid')
        require(r,row['eligible_provider_confirmed'],'Confirm provider is eligible, unrelated under disallowed-provider rules, with documented identity/due diligence.')
        require(r,all(row[key].strip() for key in ('name','address','tin')),'Care provider name/address/TIN or Tax-Exempt identifying entry is required; missing-TIN due-diligence exception needs a separate statement not implemented here.')
        require(r,not row['household_employee'],'Household employee care needs ScheduleH/payroll taxes, not implemented in this credit module.')
    n=len(people);expenses=whole(raw_expenses);cap=6000 if n>=2 else 3000 if n else 0
    if expenses or values['benefits_expenses_incurred']:require(r,bool(data['providers']),'Positive care expenses require actual provider records; an empty list cannot be replaced by an identity confirmation checkbox.')
    if data['deemed_income_months']:
        require(r,data['deemed_income_eligibility_confirmed'],'Verify qualifying full-time5monthstudent/disability and actual monthly income before using deemed earnings.')
        if len(data['deemed_income_months'])!=12:raise ValueError('Deemed income requires all12 monthly records.')
        seen=set();actual=[D(0),D(0)];effective=[D(0),D(0)];floor=500 if n>=2 else 250
        for item in data['deemed_income_months']:
            row=schema(item,row_templates()['care.deemed_income_months'],'care.month');month=row['month']
            if type(month) is not int or month not in range(1,13) or month in seen:raise ValueError('Care monthly records must contain unique months1..12.')
            seen.add(month);owner=row['deemed_owner']
            if owner not in ('none','taxpayer','spouse') or owner=='spouse' and s!='mfj':raise ValueError('Invalid deemed_owner; only one person may receive deemed income per month.')
            for i,key in enumerate(('taxpayer_income','spouse_income')):
                value=money(row[key],'care.month.'+key,True);actual[i]+=value
                effective[i]+=max(D(floor),value) if owner==('taxpayer','spouse')[i] else value
        for i in range(2 if s=='mfj' else 1):
            if whole(actual[i])!=earned[i]:raise ValueError('Care monthly actual earned income must reconcile annual earned income before benefits.')
            earned[i]=whole(effective[i])
    if s!='mfj':earned[1]=earned[0]
    used=benefits+values['benefits_carry_in']-values['benefits_forfeited_or_carried_out']
    if used<0:raise ValueError('Forfeited/carryout benefits exceed total received benefits.')
    if benefits or values['benefits_carry_in']:
        require(r,data['benefits_qualification_confirmed'],'Verify employeeFSA/Box10 benefits, qualifying incurredexpenses, planlimit and amounts not already inW2Box1.')
        require(r,n>0 or not values['benefits_expenses_incurred'],'Incurred dependent-care benefit expenses require qualifying people.')
    excluded=max(0,min(used,values['benefits_expenses_incurred'] if n else 0,*earned,min(5000,values['benefits_plan_limit'])))
    taxable=max(0,used-excluded)
    # Same household2441 benefits, distributed using actual per-ownerBox10 shares.
    owner_benefits=[context_money(context,'benefits_taxpayer'),context_money(context,'benefits_spouse')]
    if sum(owner_benefits)!=benefits:owner_benefits=[benefits,0]
    taxable_taxpayer=whole(D(taxable)*D(owner_benefits[0])/D(benefits)) if benefits else taxable
    taxable_by_owner={'taxpayer':taxable_taxpayer,'spouse':taxable-taxable_taxpayer}
    credit_earned=[earned[0]+taxable_by_owner['taxpayer'],earned[1]+taxable_by_owner['spouse']]
    if s!='mfj':credit_earned[1]=credit_earned[0]
    expense_base=max(0,min(max(0,cap-excluded),max(0,expenses-excluded),*credit_earned))
    agi=context_money(context,'agi',True);steps=int((D(max(0,agi-15000))/D(2000)).to_integral_value(rounding=ROUND_CEILING))
    rate=max(D('.20'),D('.35')-D(steps)*D('.01'));before=whole(D(expense_base)*rate)
    limit=max(0,context_money(context,'tax_liability_limit'));credit=min(before,limit)
    r.update(nonrefundable_credit=credit,taxable_benefits=taxable,taxable_by_owner=taxable_by_owner,
             form_lines={'3':max(0,min(cap-excluded,expenses-excluded)),'4':credit_earned[0],'5':credit_earned[1],'6':expense_base,'7':agi,'8':str(rate),'9a':before,'9b':0,'9c':before,'10':limit,'11':credit,
                         '12':benefits,'15':used,'16':values['benefits_expenses_incurred'],'18':earned[0],'19':earned[1],'25':excluded,'26':taxable,'27':cap,'28':excluded,'29':max(0,cap-excluded),'30':max(0,expenses-excluded),'31':max(0,min(cap-excluded,expenses-excluded))})
    r['trace']=[{'label':'Form2441 dependent-care credit','amount':credit,'source':SOURCES['f2441']},{'label':'Form1040 line1e taxable dependent-care benefits','amount':taxable,'source':SOURCES['i2441']}]
    return r


def calculate_saver(data,context):
    data=schema(data,default_inputs()['saver'],'saver');r=output('saver');s=status(context)
    amounts={key:whole(money(value,'saver.'+key)) for key,value in data.items() if isinstance(value,str)}
    if inactive(data,r):return r
    require(r,data['contributions_eligibility_confirmed'],'Saver credit: verify qualifying contributions/deferrals, no employer matching/rollovers/returnedexcess, age/dependency/student facts and no foreignMAGI exclusions.')
    require(r,data['distribution_window_and_exclusions_confirmed'],'Saver credit: verify all eligible distributions after2022 through2025return due date includingextensions and formal exceptions.')
    owners=('taxpayer','spouse') if s=='mfj' else ('taxpayer',);dist=whole(sum((money(data[o+'_distributions'],'saver.distributions') for o in owners),D(0)))
    if s=='mfj' and dist:require(r,data['all_distribution_years_joint'],'MFJ distributions from nonjoint prior-year returns require separate per-column exception records not implemented.')
    require(r,dist+amounts['current_year_excluded_distributions']>=context_money(context,'known_2025_distributions'),'Saver distributions omit known2025 plan/IRA amounts; include qualifying distributions or document the formal8880 exclusion amount.')
    if s!='mfj':require(r,not any(amounts[key] for key in amounts if key.startswith('spouse_')),'Spouse saver amounts only belong inMFJ.')
    contributions=[];columns={}
    for owner in owners:
        a=context.get(owner+'_age',0)
        if type(a) is not int or not 0<=a<=120:raise ValueError('Invalid saver age.')
        ira_raw=money(context.get('ira_'+owner+'_raw',str(context_money(context,'ira_'+owner))),'context.ira_'+owner+'_raw')
        line1=whole(ira_raw+money(data[owner+'_able_contributions'],'saver.able_contributions'))
        total=line1+amounts[owner+'_employer_contributions']
        eligible=a>=18 and not context.get(owner+'_can_be_claimed',False) and not data[owner+'_full_time_student']
        reduction=dist if s=='mfj' else amounts[owner+'_distributions'];base=min(2000,max(0,total-reduction)) if eligible else 0
        contributions.append(base);columns[owner]={'1':line1,'2':amounts[owner+'_employer_contributions'],'3':total,'4':reduction,'5':max(0,total-reduction),'6':base,'eligible':eligible}
    agi=context_money(context,'agi',True)
    limits=(47500,51000,79000) if s=='mfj' else (35625,38250,59250) if s=='hoh' else (23750,25500,39500)
    rate=D('.5') if agi<=limits[0] else D('.2') if agi<=limits[1] else D('.1') if agi<=limits[2] else D(0)
    before=whole(D(sum(contributions))*rate);limit=max(0,context_money(context,'tax_liability_limit'));credit=min(before,limit)
    r.update(nonrefundable_credit=credit,form_lines={'columns':columns,'7':sum(contributions),'8':agi,'9':str(rate),'10':before,'11':limit,'12':credit})
    r['trace']=[{'label':'Form8880 Saver credit','amount':credit,'source':SOURCES['f8880']}];return r


def calculate_elderly(data,context):
    data=schema(data,default_inputs()['elderly_credit'],'elderly_credit');r=output('elderly_credit');s=status(context)
    values={key:whole(money(data[key],'elderly_credit.'+key)) for key in ('taxpayer_taxable_disability_income','spouse_taxable_disability_income','other_nontaxable_pensions')}
    if inactive(data,r):return r
    require(r,data['eligibility_confirmed'] and data['nontaxable_benefits_confirmed'],'ScheduleR resident/age and all statutory nontaxable pension/benefit facts require confirmation.')
    if s=='mfs':require(r,data['mfs_lived_apart_entire_year'],'MFS ScheduleR requires living apart for the entireyear.')
    ages=[context.get('taxpayer_age',0),context.get('spouse_age',0)]
    if any(type(a) is not int or not 0<=a<=120 for a in ages):raise ValueError('Invalid ScheduleR age.')
    old=[age>=65 for age in ages];disabled=[data[o+'_permanently_disabled'] for o in ('taxpayer','spouse')]
    if any(disabled[i] and not old[i] for i in range(2 if s=='mfj' else 1)):
        require(r,data['physician_statement_confirmed'] and data['disability_income_in_return_confirmed'],'Under65 ScheduleR needs permanent-total disability retirement/physician statement and taxable disability before mandatoryretirementage included inreturn.')
        require(r,sum(values[o+'_taxable_disability_income'] for o in ('taxpayer','spouse'))<=context_money(context,'disability_income_available'),'Disability credit income exceeds the taxable income actually included inthisreturn.')
    if s=='mfj':
        if all(old):box=3
        elif any(old):box=6 if disabled[1 if old[0] else 0] else 7
        elif all(disabled):box=5
        elif any(disabled):box=4
        else:box=0
    else:box=(8 if old[0] else 9 if disabled[0] else 0) if s=='mfs' and data['mfs_lived_apart_entire_year'] else 0 if s=='mfs' else (1 if old[0] else 2 if disabled[0] else 0)
    initial=7500 if box in (3,5,6) else 3750 if box in (8,9) else 5000 if box else 0
    line11=values['taxpayer_taxable_disability_income']+values['spouse_taxable_disability_income'] if box==5 else 5000+values[('spouse' if old[0] else 'taxpayer')+'_taxable_disability_income'] if box==6 else values['taxpayer_taxable_disability_income']+ (values['spouse_taxable_disability_income'] if s=='mfj' else 0) if box in (2,4,9) else initial
    base=min(initial,line11);ss=context_money(context,'ss_nontaxable');nontax=ss+values['other_nontaxable_pensions'];agi=context_money(context,'agi',True)
    phase_start=10000 if s=='mfj' else 5000 if s=='mfs' else 7500
    excess=max(0,agi-phase_start);half=whole(D(excess)*D('.5'));remaining=max(0,base-nontax-half)
    before=whole(D(remaining)*D('.15'));limit=max(0,context_money(context,'tax_liability_limit'));credit=min(before,limit)
    r.update(nonrefundable_credit=credit,form_lines={'box':box,'10':initial,'11':line11,'12':base,'13a':ss,'13b':values['other_nontaxable_pensions'],'13c':nontax,'14':agi,'15':phase_start,'16':excess,'17':half,'18':nontax+half,'19':remaining,'20':before,'21':limit,'22':credit})
    r['trace']=[{'label':'ScheduleR elderly/disabled credit','amount':credit,'source':SOURCES['f1040sr']}];return r
