"""Independent, offline US TY2025 adoption, energy, FTC and Form2210 worksheets.

All money is Decimal. No vendor code and no filing or payment service. Foreign
credit support is deliberately restricted to source-verified passive income.
The capital helpers use verified records, never infer missing cross-account lots.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import re

D=Decimal
SOURCES={name:'https://www.irs.gov/pub/irs-prior/'+name+'--2025.pdf' for name in
         ('f8839','i8839','f5695','i5695','f2210','i2210','f1116','i1116','i1040sd','i8949','p550','i1040s8')}
ENERGY_TYPES=('solar_electric','solar_water','wind','geothermal','battery','fuel_cell','insulation','door','window','central_ac','gas_water_heater','furnace_boiler','electric_panel','energy_audit','heat_pump','heat_pump_water_heater','biomass')
TEXT_KEYS={'name','tin','address','country','date','payment_date','prior_year_credit_date','qmid','kind','filing_date','withholding_method','method','enabled_property_code'}
DATE_KEYS={'date','payment_date','prior_year_credit_date','filing_date'}


def whole(value):return int(D(value).quantize(D('1'),rounding=ROUND_HALF_UP))


def money(value,label,signed=False):
    if not isinstance(value,str) or not re.fullmatch(r'-?\d{1,12}(?:\.\d{1,2})?',value):raise ValueError(label+' must be a USD decimal string with at most two fractional digits.')
    result=D(value)
    if result<0 and not signed:raise ValueError(label+' cannot be negative.')
    return result


def parse_date(value,label,empty=False):
    if empty and value=='':return None
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError(label+' requires an actual YYYY-MM-DD date.')
    try:return date.fromisoformat(value)
    except ValueError:raise ValueError(label+' is not a valid calendar date.') from None


def default_inputs():
    return {
      'capital_records':{'carry_in_confirmed':False,'wash_sale_all_accounts_reviewed':False},
      'adoption':{'enabled':False,'eligibility_confirmed':False,'no_reimbursement_or_double_benefit_confirmed':False,'mfs_qualifying_separation':False,'children':[],'carryforwards':[],'employer_benefits':'0'},
      'energy':{'enabled':False,'address':'','qualification_and_costs_confirmed':False,'placed_in_service_2025_confirmed':False,'home_ownership_use_confirmed':False,'no_joint_occupancy_or_business_allocation':False,'improvements_existing_main_home_confirmed':False,'residential_property_original_use_confirmed':False,'clean_carry_in':'0','carry_in_confirmed':False,'items':[]},
      'foreign_credit':{'enabled':False,'method':'simplified_election','all_foreign_income_passive_confirmed':False,'income_in_return_confirmed':False,'qualified_payee_statements_confirmed':False,'creditability_and_source_confirmed':False,'no_excluded_income_or_treaty_resourcing':False,'no_redeterminations_losses_or_carryovers':False,'carry_in':'0','taxes_deducted_elsewhere':'0','countries':[]},
      'estimated_penalty':{'enabled':False,'prior_year_tax':'0','prior_year_agi':'0','prior_year_full_12_months':False,'prior_year_tax_verified':False,'no_prior_year_tax_full_year_resident_confirmed':False,'actual_payment_records_confirmed':False,'withholding_method':'equal_installments','prior_year_credit_date':'2025-04-15','payments':[],'withholding_records':[],'balance_due_payment':'0','payment_date':'2026-04-15','annualized_income_requested':False,'waiver_disaster_farmer_or_special_rule':False,'early_filing_exception_requested':False}}


def row_templates():
    return {
      'adoption.children':{'name':'','tin':'','birth_year':2020,'disabled_over_17_confirmed':False,'foreign_child':False,'special_needs':False,'special_needs_determination_confirmed':False,'final_year':2025,'expenses_2024':'0','expenses_2025':'0','foreign_prior_expenses':'0','prior_credit_expenses_used':'0','shared_credit_limit':'17280','eligibility_timing_confirmed':False},
      'adoption.carryforwards':{'year':2024,'amount':'0','unexpired_source_confirmed':False},
      'energy.items':{'kind':'solar_electric','cost':'0','qmid':'','qualification_confirmed':False,'battery_at_least_3_kwh':False,'fuel_cell_capacity_kw':'0','fuel_cell_main_home_confirmed':False,'enabled_property_code':'','enabling_property_2025_confirmed':False,'certified_audit_report_confirmed':False},
      'foreign_credit.countries':{'country':'','ordinary_interest':'0','ordinary_dividends':'0','qualified_dividends':'0','tax_paid':'0','tax_reduction':'0','date':'2025-12-31'},
      'estimated_penalty.payments':{'date':'2025-04-15','amount':'0'},
      'estimated_penalty.withholding_records':{'date':'2025-04-15','amount':'0'}}


def schema(data,template,label):
    if not isinstance(data,dict):raise ValueError(label+' must be an object.')
    unknown=set(data)-set(template)
    if unknown:raise ValueError('Unknown '+label+' fields: '+', '.join(sorted(unknown)))
    merged=deepcopy(template);merged.update(deepcopy(data))
    for key,default in template.items():
        value=merged[key];path=label+'.'+key
        if type(default) is bool:
            if type(value) is not bool:raise ValueError(path+' must be boolean.')
        elif type(default) is int:
            if type(value) is not int or not 0<=value<=2025:raise ValueError(path+' must be an integer from0 to2025.')
        elif isinstance(default,list):
            if not isinstance(value,list) or len(value)>500:raise ValueError(path+' must contain at most500 records.')
        elif key in TEXT_KEYS:
            if not isinstance(value,str) or len(value)>1000:raise ValueError(path+' must be text of at most1000 characters.')
            if key in DATE_KEYS:parse_date(value,path)
        else:money(value,path)
    return merged


def normalize_extra(data):
    for group,template in default_inputs().items():data[group]=schema(data[group],template,group)
    for path,template in row_templates().items():
        group,key=path.split('.');data[group][key]=[schema(row,template,path) for row in data[group][key]]
    if data['foreign_credit']['method'] not in ('simplified_election','ordinary_passive_1116'):raise ValueError('Invalid foreign_credit.method.')
    if data['estimated_penalty']['withholding_method'] not in ('equal_installments','actual_dates'):raise ValueError('Invalid withholding_method.')
    for row in data['energy']['items']:
        if row['kind'] not in ENERGY_TYPES:raise ValueError('Invalid energy item kind.')
        if row['enabled_property_code'] not in ('','A','B','C','D','E','F','G'):raise ValueError('Invalid electricpanel enabledproperty code.')
    return data


def ui_schema():
    fields={}
    for group,template in default_inputs().items():
        for key,value in template.items():
            if not isinstance(value,list):fields[group+'.'+key]={'label':key.replace('_',' ').capitalize(),'type':'boolean' if type(value) is bool else 'text' if key in TEXT_KEYS else 'money','help':''}
    for path,template in row_templates().items():
        for key,value in template.items():fields[path+'.*.'+key]={'label':key.replace('_',' ').capitalize(),'type':'boolean' if type(value) is bool else 'integer' if type(value) is int else 'text' if key in TEXT_KEYS else 'money','help':''}
    fields['foreign_credit.method'].update(type='enum',options=['simplified_election','ordinary_passive_1116'])
    fields['estimated_penalty.withholding_method'].update(type='enum',options=['equal_installments','actual_dates'])
    fields['energy.items.*.kind'].update(type='enum',options=list(ENERGY_TYPES))
    fields['energy.items.*.enabled_property_code'].update(type='enum',options=['','A','B','C','D','E','F','G'],help='Actual enabledproperty: A windows,BcentralAC,Cgaswaterheater,Dfurnaceboiler,Eheatpump,Fheatpumpwaterheater,Gbiomass. No genericpanelupgrade credit.')
    fields['capital_records.carry_in_confirmed']['help']='Actual short/long LOSS carryovers from2024 IRS worksheet, positive amounts in carryovers.capital_short/long. No guessed netloss or duplicated current transaction.'
    fields['capital_records.wash_sale_all_accounts_reviewed']['help']='Verified61-day window, spouse/IRA/allbroker accounts and substantiallyidentical securities. This module applies documented disallowed loss; it does not discover missing replacement lots.'
    fields['adoption.children.*.final_year']['help']='0 if notfinal; otherwise actual finalizationyear. Domestic expense timing and foreign-finalization rules differ.'
    fields['adoption.children.*.foreign_prior_expenses']['help']='Foreign adoption paid before2024, not claimed earlier. Used only when foreign adoption finalized in2025.'
    fields['energy.items.*.cost']['help']='Qualified net cost after rebates/subsidies and personal/businessallocation; insulation/door/window exclude installationlabor, qualifyingequipment/cleanenergy include eligibleinstallationlabor.'
    fields['energy.items.*.qmid']['help']='Actual4-character qualifiedmanufacturer ID for2025 specified homeimprovement property; retain manufacturer certification.'
    fields['estimated_penalty.actual_payment_records_confirmed']['help']='Each datedestimated amount must reconcile payments.estimated, actualwithholding must reconcile25d + excessSS, and priorcredit paymentdate must reflect when overpayment arose. Balancepayment is not an estimatedpayment.'
    fields['estimated_penalty.annualized_income_requested']['help']='ScheduleAI is a separate method; this regular-installment calculation explicitly blocks requestedAI.'
    return {'ui_fields':fields,'ui_modules':[{'id':key,'label':label,'step':'income' if key=='capital_records' else 'deductions','description':'IRS2025 calculation with source records, explicit eligibility and unsupported-case blocks.'} for key,label in (('capital_records','Capital Carryovers and Wash Sales'),('adoption','Adoption Credit'),('energy','Home Energy Credits'),('foreign_credit','Foreign Tax Credit'),('estimated_penalty','Estimated Tax Penalty'))]}


def output(name):return {'module':name,'tax_year':2025,'can_compute':True,'nonrefundable_credit':0,'refundable_credit':0,'blocking_issues':[],'warnings':[],'trace':[],'form_lines':{}}


def require(result,condition,message):
    if not condition:
        result['can_compute']=False
        if message not in result['blocking_issues']:result['blocking_issues'].append(message)


def inactive(data,result,ignored=()):
    if data['enabled']:return False
    populated=any(isinstance(v,list) and bool(v) or isinstance(v,str) and k not in ignored and k not in TEXT_KEYS and money(v,k)!=0 for k,v in data.items())
    require(result,not populated,'Disabled '+result['module']+' contains actual monetary/document data; enable it or remove entries.')
    return True


def calculate_adoption(data,context):
    data=schema(data,default_inputs()['adoption'],'adoption');r=output('adoption')
    if inactive(data,r):return r
    s=context['filing_status'];magi=context['agi'];limit=max(0,context['tax_liability_limit'])
    for key in ('eligibility_confirmed','no_reimbursement_or_double_benefit_confirmed'):require(r,data[key],'Adoption: confirm '+key+'.')
    require(r,s!='mfs' or data['mfs_qualifying_separation'],'MFS adoption requires qualifying last6months separation, childmainhome and majorityhouseholdsupport tests.')
    require(r,not money(data['employer_benefits'],'employer_benefits'),'Employer adoption benefits require separate Form8839 PartIII exclusion/MAGI timing; not implemented here.')
    ratio=min(D(1),D(max(0,magi-259190))/D(40000));columns=[];seen=set()
    for item in data['children']:
        row=schema(item,row_templates()['adoption.children'],'adoption.child');name=row['name'].strip();tin=row['tin'].strip()
        require(r,bool(name) and bool(re.fullmatch(r'\d{9}',tin.replace('-',''))),'Adoption eligible child name and documented9-digitSSN/ATIN/ITIN required; unavailableTIN statements are not implemented.')
        if tin in seen and tin:raise ValueError('Duplicate adoption child TIN.')
        seen.add(tin)
        require(r,row['eligibility_timing_confirmed'],'Adoption child: verify under18/permanentlydisabled eligibility at expense time, nonspousechild and expense/document/finalization facts.')
        require(r,row['birth_year']>=2008 or row['disabled_over_17_confirmed'],'Over17 child requires verified permanent inability to selfcare; adoption-age timing exception needs separate review.')
        if row['final_year'] and row['final_year']<row['birth_year']:raise ValueError('Adoption finalization cannot precede birth.')
        cap=whole(money(row['shared_credit_limit'],'shared_credit_limit'));prior=whole(money(row['prior_credit_expenses_used'],'prior_credit_expenses_used'))
        if cap>17280 or prior>cap:raise ValueError('Adoption perchild sharedlimit/previouslyused expenses exceed17280 or remaininglimit.')
        remaining=cap-prior;exp24=money(row['expenses_2024'],'expenses_2024');exp25=money(row['expenses_2025'],'expenses_2025');foreign_prior=money(row['foreign_prior_expenses'],'foreign_prior_expenses')
        if row['special_needs']:
            require(r,not row['foreign_child'] and row['special_needs_determination_confirmed'],'Special-needs fullcredit requires USchild and actual state/tribal determination; ordinary specialcare alone doesnot establish eligibility.')
            qualified=remaining if row['final_year']==2025 else whole(exp25 if row['final_year'] and row['final_year']<2025 else exp24)
        elif row['foreign_child']:
            qualified=whole(exp24+exp25+foreign_prior) if row['final_year']==2025 else whole(exp25) if row['final_year'] and row['final_year']<2025 else 0
        else:
            require(r,not foreign_prior,'Domestic expenses before2024 require prior-year Form8839/amended-year records, not current-year duplication.')
            qualified=whole(exp24+exp25) if row['final_year']==2025 else whole(exp25) if row['final_year'] and row['final_year']<2025 else whole(exp24)
        allowed_base=min(remaining,qualified);reduction=whole(D(allowed_base)*ratio);credit=allowed_base-reduction;refundable=min(credit,5000)
        columns.append({'name':name,'tin':tin,'2':cap,'3':prior,'4':remaining,'5':qualified,'6':allowed_base,'10':reduction,'11a':credit,'11b':refundable,'foreign_child':row['foreign_child'],'special_needs':row['special_needs'],'final_year':row['final_year'],'birth_year':row['birth_year']})
    carry=[];years=set()
    for item in data['carryforwards']:
        row=schema(item,row_templates()['adoption.carryforwards'],'adoption.carryforward');year=row['year'];amount=whole(money(row['amount'],'carryforward.amount'))
        if year not in range(2020,2025) or year in years:raise ValueError('Adoption carryforwards require uniqueunexpired years2020..2024.')
        years.add(year);require(r,row['unexpired_source_confirmed'],'Verify prior8839 unexpired nonrefundable carryforward worksheet; refundable amountscannot carry.')
        carry.append((year,amount))
    total=sum(c['11a'] for c in columns);refund=sum(c['11b'] for c in columns);prior=sum(v for _,v in carry);nonrefund_base=total-refund+prior;credit=min(nonrefund_base,limit)
    consume=credit;out=[]
    for year,amount in sorted(carry)+[(2025,total-refund)]:
        used=min(amount,consume);consume-=used;left=amount-used
        out.append({'origin_year':year,'starting_amount':amount,'used_2025':used,'expired_after_2025':left if year==2020 else 0,'carry_to_2026':left if year>2020 else 0})
    r.update(nonrefundable_credit=credit,refundable_credit=refund,carryforward_to_2026=sum(x['carry_to_2026'] for x in out),carryforward_records=out,
             form_lines={'children':columns,'7':magi,'8':max(0,magi-259190),'9':str(ratio),'11c':refund,'12':total,'13':refund,'14':total-refund,'15':prior,'16':nonrefund_base,'17':min(nonrefund_base,limit),'18':credit})
    r['trace']=[{'label':'Form8839 refundable adoption credit,1040line30','amount':refund,'source':SOURCES['f8839']},{'label':'Form8839 nonrefundable adoption credit','amount':credit,'source':SOURCES['i8839']}]
    return r


def calculate_energy(data,context):
    data=schema(data,default_inputs()['energy'],'energy');r=output('energy');r.update(clean_credit=0,improvement_credit=0,clean_carryforward=0)
    if inactive(data,r):return r
    for key in ('qualification_and_costs_confirmed','placed_in_service_2025_confirmed','home_ownership_use_confirmed','no_joint_occupancy_or_business_allocation'):require(r,data[key],'Energy: confirm '+key+'; business/jointoccupant/condominium and multiyear enabling-property allocation need separate records.')
    require(r,bool(data['address'].strip()),'Energy property requires actualUS homeaddress; no placeholder location is assumed.')
    values={k:D(0) for k in ENERGY_TYPES};rows=[];fuel_limit=D(0);door=[]
    for item in data['items']:
        row=schema(item,row_templates()['energy.items'],'energy.item');kind=row['kind']
        if kind not in ENERGY_TYPES:raise ValueError('Invalid energy property kind.')
        cost=money(row['cost'],'energy.cost');require(r,row['qualification_confirmed'],'Each energy item requires actual manufacturer/efficiency standards, installationcost and subsidy records.')
        if kind in ('door','window','central_ac','gas_water_heater','furnace_boiler','electric_panel','heat_pump','heat_pump_water_heater','biomass') and cost:
            require(r,bool(re.fullmatch(r'[A-Za-z0-9]{4}',row['qmid'])),'Specified2025 energy property requires a valid actual4-character QMID, plus retainedmanufacturer certification.')
        if kind in ('insulation','door','window') and cost:require(r,data['improvements_existing_main_home_confirmed'],'Energy improvements must meet originaluser/5year/existingUS mainhome requirements; labor/newconstruction costs must be excluded.')
        if kind in ('central_ac','gas_water_heater','furnace_boiler','electric_panel','heat_pump','heat_pump_water_heater','biomass') and cost:require(r,data['residential_property_original_use_confirmed'],'Energy equipment must be originally placed inservice by taxpayer at qualifyingUSresidence.')
        if kind=='battery' and cost:require(r,row['battery_at_least_3_kwh'],'Cleanenergy battery requires at least3kWh capacity.')
        if kind=='energy_audit' and cost:require(r,row['certified_audit_report_confirmed'],'Audit requires actualqualifiedauditor and writtenreport for mainUS home.')
        if kind=='electric_panel' and cost:
            require(r,row['enabling_property_2025_confirmed'] and row['enabled_property_code'] in ('A','B','C','D','E','F','G'),'Electrical enablingproperty requiresactualenabledproperty code,200amp/code qualification andboth2025installations; multiyearinstallations require separate allocation.')
        if kind=='fuel_cell' and cost:
            require(r,row['fuel_cell_main_home_confirmed'],'Fuelcell costs qualifyonly for actualUSmainhome, not secondhome.')
            capacity=money(row['fuel_cell_capacity_kw'],'fuel_cell_capacity_kw')
            if capacity<D('.5') or capacity%D('.5'):raise ValueError('Fuelcell capacity must be at least0.5kW in0.5kW increments.')
            fuel_limit+=capacity*1000
        if kind=='door':door.append(cost)
        values[kind]+=cost;rows.append(dict(row,qualified_cost=whole(cost)))
    f={key:whole(values[kind]) for key,kind in (('1','solar_electric'),('2','solar_water'),('3','wind'),('4','geothermal'),('5b','battery'),('8','fuel_cell'),('18a','insulation'),('20c','window'),('22c','central_ac'),('23c','gas_water_heater'),('24c','furnace_boiler'),('25c','electric_panel'),('26b','energy_audit'))}
    f['6a']=sum(f[k] for k in ('1','2','3','4','5b'));f['6b']=whole(D(f['6a'])*D('.30'));f['9']=whole(D(f['8'])*D('.30'));f['10']=whole(fuel_limit);f['11']=min(f['9'],f['10'])
    f['12']=whole(money(data['clean_carry_in'],'clean_carry_in'))
    if f['12']:require(r,data['carry_in_confirmed'],'Cleanenergy carry-in needs actual2024 Form5695line16; no lost homeimprovement amount can carry.')
    f['13']=f['6b']+f['11']+f['12'];f['14']=max(0,context['clean_tax_liability_limit']);f['15']=min(f['13'],f['14']);f['16']=f['13']-f['15']
    f['18b']=min(1200,whole(D(f['18a'])*D('.30')))
    most_raw=max(door,default=D(0));most=whole(most_raw);rest=whole(sum(door,D(0))-most_raw)
    f.update({'19a':most,'19c':min(250,whole(D(most)*D('.30'))),'19f':rest,'19g':whole(D(rest)*D('.30'))});f['19h']=min(500,f['19c']+f['19g'])
    for base,dest in (('20c','20d'),('22c','22d'),('23c','23d'),('24c','24d'),('25c','25e')):f[dest]=min(600,whole(D(f[base])*D('.30')))
    f['26c']=min(150,whole(D(f['26b'])*D('.30')));f['27']=sum(f[k] for k in ('18b','19h','20d','22d','23d','24d','25e','26c'));f['28']=min(1200,f['27'])
    for kind,first,rest in (('central_ac','22a','22b'),('furnace_boiler','24a','24b'),('heat_pump','29a','29b'),('heat_pump_water_heater','29c','29d'),('biomass','29e','29f')):
        costs=[money(row['cost'],'energy.cost') for row in rows if row['kind']==kind];most=max(costs,default=D(0));f[first]=whole(most);f[rest]=whole(sum(costs,D(0))-most)
    for kind,first,rest,count in (('door','19d','19e',2),('window','20a','20b',4),('gas_water_heater','23a','23b',2)):
        costs=sorted([money(row['cost'],'energy.cost') for row in rows if row['kind']==kind],reverse=True)
        if kind=='door':costs=costs[1:]
        f[first]=[whole(value) for value in costs[:count]];f[rest]=whole(sum(costs[count:],D(0)))
    f['25b']=sorted({row['enabled_property_code'] for row in rows if row['kind']=='electric_panel' and money(row['cost'],'cost')})
    f['29g']=sum(f[key] for key in ('29a','29b','29c','29d','29e','29f'));f['29h']=min(2000,whole(D(f['29g'])*D('.30')));f['30']=f['28']+f['29h'];f['31']=max(0,context['improvement_tax_liability_limit']);f['32']=min(f['30'],f['31'])
    r.update(nonrefundable_credit=f['15']+f['32'],clean_credit=f['15'],improvement_credit=f['32'],clean_carryforward=f['16'],unused_home_improvement_not_carried=f['30']-f['32'],form_lines=f,items=rows)
    r['trace']=[{'label':'Form5695 cleanenergy credit','amount':f['15'],'source':SOURCES['f5695']},{'label':'Form5695 homeimprovement credit','amount':f['32'],'source':SOURCES['i5695']}]
    return r


def calculate_foreign(data,context):
    data=schema(data,default_inputs()['foreign_credit'],'foreign_credit');r=output('foreign_credit')
    if inactive(data,r):return r
    for key in ('all_foreign_income_passive_confirmed','income_in_return_confirmed','creditability_and_source_confirmed','no_excluded_income_or_treaty_resourcing','no_redeterminations_losses_or_carryovers'):require(r,data[key],'Foreigncredit: confirm '+key+'; foreignsource/category/taxeligibility cannot be assumed from a withheld amount.')
    require(r,not money(data['carry_in'],'carry_in') and not money(data['taxes_deducted_elsewhere'],'taxes_deducted_elsewhere'),'Foreigncarryovers, redeterminations or taxes deducted elsewhere require separate1116/ScheduleB reconciliation; not implemented.')
    rows=[];total_tax=D(0);foreign_income=D(0);interest=D(0);dividends=D(0);qualified=D(0)
    for item in data['countries']:
        row=schema(item,row_templates()['foreign_credit.countries'],'foreign.country');require(r,bool(row['country'].strip()),'Foreigntax needs actualcountry orRIC source record.')
        amounts={key:money(row[key],'foreign.'+key) for key in ('ordinary_interest','ordinary_dividends','qualified_dividends','tax_paid','tax_reduction')}
        if amounts['qualified_dividends']>amounts['ordinary_dividends'] or amounts['tax_reduction']>amounts['tax_paid']:raise ValueError('Foreignqualifieddividend/reduction exceeds its actualgross/taxamount.')
        dt=parse_date(row['date'],'foreigntax.date');require(r,dt.year==2025,'Cash-basisFTC requires actual2025paiddate; accrual/redetermination elections not implemented.')
        interest+=amounts['ordinary_interest'];dividends+=amounts['ordinary_dividends'];qualified+=amounts['qualified_dividends'];gross=amounts['ordinary_interest']+amounts['ordinary_dividends'];tax=amounts['tax_paid']-amounts['tax_reduction'];foreign_income+=gross;total_tax+=tax;rows.append(dict(row,gross=whole(gross),eligible_tax=whole(tax)))
    require(r,whole(interest)<=context['interest'] and whole(dividends)<=context['ordinary_dividends'] and whole(qualified)<=context['qualified_dividends'],'Foreignincome allocations must be included once in corresponding1099INT/DIV totalgross income, not inserted as extracredit income.')
    total=whole(total_tax);gross=whole(foreign_income);regular=max(0,context['regular_tax']);method=data['method']
    if method=='simplified_election':
        require(r,data['qualified_payee_statements_confirmed'],'SimplifiedFTC election requires allforeign income andtax on actualqualifiedpayee statements.')
        require(r,total<=(600 if context['filing_status']=='mfj' else 300),'SimplifiedFTC election exceeds300/600 creditabletax threshold; use1116 with requiredincome allocation.')
        credit=min(total,regular);r.update(nonrefundable_credit=credit,method=method,form_lines={'schedule3_line1':credit,'eligible_foreign_tax':total,'regular_tax_limit':regular},countries=rows)
    else:
        require(r,method=='ordinary_passive_1116','Unsupported foreigncredit method.')
        require(r,context['ordinary_standard_income_only'] and not qualified and not context['preferred_income'] and not context['amt_tax'],'Ordinarypassive1116 supports standarddeduction, ordinary1099interest/dividends only; qualified/capital-rate adjustments, AMTFTC, itemized/interest/SE/rental/loss/treaty allocation need separate worksheets.')
        denominator=context['gross_income'];standard=context['standard_deduction'];adjustments=context['adjustments'];columns=[];net=0
        countries=set()
        for row in rows:
            country=row['country'].strip().casefold()
            if country in countries:raise ValueError('Ordinary1116 requires one combined allocation record per country/RIC, not repeatedcountry columns.')
            countries.add(country)
            ratio=min(D(1),D(row['gross'])/D(denominator)) if denominator>0 else D(0)
            allocation=whole(D(standard+adjustments)*ratio);income=max(0,row['gross']-allocation);net+=income
            require(r,D(row['eligible_tax'])<=D(income)*D('.37'),'High-taxed passive income must be reclassified usingHTKO countrybasket rules; it cannot remainordinarypassive1116.')
            columns.append(dict(row,**{'1a':row['gross'],'2':0,'3a':standard,'3b':adjustments,'3c':standard+adjustments,'3d':row['gross'],'3e':denominator,'3f':str(ratio),'3g':allocation,'4a':0,'4b':0,'5':0,'6':allocation,'7':income}))
        taxable=max(0,context['taxable_before_senior']);ratio=min(D(1),D(net)/D(taxable)) if taxable else D(0);maximum=whole(D(regular)*ratio);credit=min(total,maximum)
        r.update(nonrefundable_credit=credit,method=method,unused_tax_requires_carryback_review=total-credit,form_lines={'countries':columns,'7':net,'8':total,'9':total,'10':0,'11':total,'12':0,'13':0,'14':total,'15':net,'16':0,'17':net,'18':taxable,'19':str(ratio),'20':regular,'21':maximum,'22':0,'23':maximum,'24':credit,'27':credit,'32':credit,'33':credit,'34':0,'35':credit})
    r['trace']=[{'label':'Passive foreigntaxcredit','amount':r['nonrefundable_credit'],'source':SOURCES['i1116']}]
    return r


def capital_carryout(short,long,loss_deduction,taxable_unfloored):
    """Pub550/IRS ScheduleD loss worksheet retaining ordinary-income absorption."""
    used=min(loss_deduction,max(0,taxable_unfloored+loss_deduction));short_loss=max(0,-short);long_loss=max(0,-long)
    short_out=max(0,short_loss-used-max(0,long));long_out=max(0,long_loss-max(0,short)-max(0,used-short_loss))
    return {'short_loss_carry_to_2026':short_out,'long_loss_carry_to_2026':long_out,'ordinary_income_loss_absorbed':used,'taxable_income_before_zero_floor':taxable_unfloored,'source':SOURCES['p550']}


def calculate_penalty(data,context):
    data=schema(data,default_inputs()['estimated_penalty'],'estimated_penalty');r=output('estimated_penalty');r.update(penalty=0,computed=False)
    if inactive(data,r):return r
    for key in ('actual_payment_records_confirmed','prior_year_tax_verified'):require(r,data[key],'Form2210: confirm '+key+'; actualdates and prior taxworksheet are required.')
    for key in ('annualized_income_requested','waiver_disaster_farmer_or_special_rule','early_filing_exception_requested'):require(r,not data[key],'Form2210 '+key+' requires separateScheduleAI/waiver/2210F/earlyfiling method; regularinstallment preview cannot represent it.')
    current=max(0,context['tax_for_2210']-context['refundable_credits']);held=context['withholding']+context['excess_ss'];ninety=whole(D(current)*D('.90'));prior=whole(money(data['prior_year_tax'],'prior_year_tax'));prioragi=whole(money(data['prior_year_agi'],'prior_year_agi'))
    priorlimit=whole(D(prior)*(D('1.1') if prioragi>(75000 if context['filing_status']=='mfs' else 150000) else D(1))) if data['prior_year_full_12_months'] else ninety
    required=min(ninety,priorlimit);exception=current-held<1000 or held>=required or data['no_prior_year_tax_full_year_resident_confirmed'] and data['prior_year_full_12_months'] and prior==0
    require(r,not data['no_prior_year_tax_full_year_resident_confirmed'] or data['prior_year_full_12_months'] and prior==0,'No-priortax exception requires zero2024tax/full12monthsyear andfull-yearcitizen/resident facts.')
    nominal=[date(2025,4,15),date(2025,6,15),date(2025,9,15),date(2026,1,15)];deadline_adjust={date(2025,6,16):date(2025,6,15)}
    events=[];raw_est=D(0);period_pay=[D(0)]*4;records=[]
    def add_payment(day,amount,kind):
        effective=deadline_adjust.get(day,day);events.append((effective,amount,kind));records.append({'actual_date':day.isoformat(),'effective_date':effective.isoformat(),'amount':str(amount),'kind':kind})
        for i,cutoff in enumerate(nominal):
            if effective<=cutoff:period_pay[i]+=amount;break
    for item in data['payments']:
        row=schema(item,row_templates()['estimated_penalty.payments'],'penalty.payment');day=parse_date(row['date'],'penalty.payment.date');amount=money(row['amount'],'penalty.payment.amount');raw_est+=amount
        if not date(2025,1,1)<=day<=date(2026,4,15):raise ValueError('2025estimated payments must have actualdates2025-01-01 through2026-04-15.')
        add_payment(day,amount,'estimated')
    require(r,whole(raw_est)==context['estimated'],'Datedestimated payments must reconcile payments.estimated; no undocumentedquarter allocation is assumed.')
    if context['prior_year_credit']:
        credit_date=parse_date(data['prior_year_credit_date'],'prior_year_credit_date')
        if not date(2025,4,15)<=credit_date<=date(2026,4,15):raise ValueError('Prioroverpayment credit is ordinarilyApril15,2025 or actuallaterpayment date throughApril15,2026.')
        add_payment(credit_date,D(context['prior_year_credit']),'prior_year_credit')
    if data['withholding_method']=='equal_installments':
        require(r,not data['withholding_records'],'Equal-installment withholding cannot also enteractualwithholding records; chooseone method.')
        for day in nominal:add_payment(day,D(held)/4,'deemed_withholding')
    elif data['withholding_method']=='actual_dates':
        total=D(0)
        for item in data['withholding_records']:
            row=schema(item,row_templates()['estimated_penalty.withholding_records'],'penalty.withholding');day=parse_date(row['date'],'penalty.withholding.date');amount=money(row['amount'],'penalty.withholding.amount');total+=amount
            if day.year!=2025:raise ValueError('Actual2025 withholding date must occurin2025.')
            add_payment(day,amount,'actual_withholding')
        require(r,whole(total)==held,'Actualwithholding records must reconcile Form1040line25d +Schedule3excessSS.')
    else:raise ValueError('Invalid withholdingmethod.')
    balance=money(data['balance_due_payment'],'balance_due_payment');payment_date=parse_date(data['payment_date'],'payment_date')
    if balance:
        if not date(2025,1,1)<=payment_date<=date(2026,4,15):raise ValueError('Balancepaymentdate must be within2025-01-01 through2026-04-15; penaltyends April15.')
        add_payment(payment_date,balance,'balance_due')
    periods=[(date(2025,4,15),date(2025,6,30),D('.07')),(date(2025,6,30),date(2025,9,30),D('.07')),(date(2025,9,30),date(2025,12,31),D('.07')),(date(2025,12,31),date(2026,4,15),D('.07'))]
    debt=[];credit=D(0);segments=[];due=D(required)/4
    def interest(start,end,amount,column):
        for p,(lo,hi,rate) in enumerate(periods,1):
            a=max(start,lo);b=min(end,hi);days=(b-a).days
            if days>0 and amount>0:segments.append({'column':column+1,'rate_period':p,'start_exclusive':a.isoformat(),'end_inclusive':b.isoformat(),'days':days,'principal':str(amount),'annual_rate':str(rate),'penalty':str(amount*D(days)/D(365)*rate)})
    actions=[(day,1,amount,kind) for day,amount,kind in events]+[(day,0,due,i) for i,day in enumerate(nominal)]
    for day,kind,amount,metadata in sorted(actions,key=lambda x:(x[0],x[1])):
        if kind==0:
            consumed=min(credit,amount);credit-=consumed
            if amount>consumed:debt.append({'column':metadata,'principal':amount-consumed,'last':day})
        else:
            remaining=amount
            for entry in debt:
                if remaining<=0:break
                paid=min(remaining,entry['principal']);interest(entry['last'],day,entry['principal'],entry['column']);entry['last']=day;entry['principal']-=paid;remaining-=paid
            debt=[entry for entry in debt if entry['principal']>0];credit+=remaining
    for entry in debt:interest(entry['last'],date(2026,4,15),entry['principal'],entry['column'])
    penalty=0 if exception else whole(sum((D(x['penalty']) for x in segments),D(0)))
    section_a={str(key):[] for key in range(12,19)};previous={key:D(0) for key in range(12,19)}
    for i,paid in enumerate(period_pay):
        line12=previous[18] if i else D(0);line13=paid+line12;line14=previous[16]+previous[17] if i else D(0)
        line15=max(D(0),line13-line14);line16=max(D(0),line14-line13) if line15==0 else D(0);line17=max(D(0),due-line15);line18=max(D(0),line15-due)
        previous=dict(zip(range(12,19),(line12,line13,line14,line15,line16,line17,line18)))
        for key,value in previous.items():section_a[str(key)].append(str(value))
    r.update(penalty=penalty,computed=r['can_compute'],exception_applies=exception,required_annual_payment=required,actual_payment_records=records,interest_segments=[] if exception else segments,
             form_lines={'1':context['income_tax_after_credits'],'2':context['additional_tax_for_2210'],'3':context['refundable_credits'],'4':current,'5':ninety,'6':held,'7':max(0,current-held),'8':priorlimit,'9':required,'10':[str(due)]*4,'11':[str(v) for v in period_pay],**section_a,'19':penalty})
    r['trace']=[{'label':'Form2210 regularinstallment estimated-tax penalty','amount':penalty,'source':SOURCES['i2210']}]
    return r
