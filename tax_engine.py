"""Tax Reborn: independently implemented US resident federal TY2025 worksheets.

Decimal only. Money inputs are USD decimal strings with at most two fractional
places. IRS whole-dollar rounding is applied to each form/worksheet line;
amounts contributing to the same Form1040 income line are summed before rounding.
Unsupported situations return blocking_issues, never a completed return.
No tax filing, state calculation, runtime network or proprietary code.
"""
from __future__ import annotations

from bisect import bisect_right
from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, ROUND_FLOOR, ROUND_CEILING, localcontext
import json
from pathlib import Path
import re
import tax_extended
import tax_credits
import tax_additional
import tax_longtail
import tax_filing
import tax_special_capital
import tax_child_income

RULES = json.loads(Path(__file__).with_name('rules_2025.json').read_text(encoding='utf-8'))
STATUSES = ('single','mfj','mfs','hoh','qss')
LINE_KEYS = ('1a','2a','2b','3a','3b','4a','4b','5a','5b','6a','6b','7a','8','9','10','11a','11b','12e','13a','13b','14','15','16','17','18','19','20','21','22','23','24','25a','25b','25c','25d','26','27a','28','29','30','31','32','33','34','35a','36','37','38')
TABLE_LOW = [row[0] for row in RULES['tax_table']]
D = Decimal


def dollars(value):
    return int(D(value).quantize(D('1'),rounding=ROUND_HALF_UP))


def money(value,path='amount',signed=False):
    if not isinstance(value,str) or not re.fullmatch(r'-?\d{1,12}(?:\.\d{1,2})?',value):
        raise ValueError(f'{path} must be a USD decimal string with at most two fractional digits; float inputs are not accepted.')
    try:
        number=D(value)
    except InvalidOperation:
        raise ValueError(f'{path} is not a finite USD amount.') from None
    if not signed and number<0:
        raise ValueError(f'{path} cannot be negative.')
    return number


def boolean(value,path):
    if type(value) is not bool:
        raise ValueError(f'{path} must be true or false.')
    return value


def age(value,path):
    if type(value) is not int or not 0<=value<=120:
        raise ValueError(f'{path} must be an integer age from 0 to 120 (IRS age as of December31,2025).')
    return value


def default_return():
    defaults = {
        'tax_year':2025,'name':'My 2025 Federal Return','filing_status':'single',
        'taxpayer':{'age':35,'blind':False,'can_be_claimed':False,'valid_ssn':True,'valid_tin':True},
        'spouse':{'age':35,'blind':False,'can_be_claimed':False,'valid_ssn':True,'valid_tin':True},
        'dependents':[],'w2':[],'interest':[],'dividends':[],'capital_gains':[],'businesses':[],
        'retirement':{'ira_gross':'0','ira_taxable':'0','pension_gross':'0','pension_taxable':'0','social_security':'0','federal_withholding':'0','taxable_amounts_confirmed':False,'qualified_plan_confirmed':False,'early_distribution_exception_confirmed':False,'ira_distribution_kind':'fully_taxable','ss_lump_sum_or_repayments':False},
        'other_income':{'unemployment':'0','other':'0','federal_withholding':'0','taxable_other_confirmed':False},
        'adjustments':{'student_loan_interest':'0','ira_deduction':'0','hsa_deduction':'0','self_employed_health_insurance':'0'},
        'itemized':{'medical':'0','state_local_tax':'0','mortgage_interest':'0','charity':'0','investment_interest':'0','charity_cash_only':False,'mortgage_eligible':False,'medical_eligible':False,'force_itemized':False},
        'schedule_1a':{'qualified_tips':'0','qualified_overtime':'0','qualified_car_loan_interest':'0','eligibility_confirmed':False,'tips_occupation_eligible':False,'tips_not_sstb':False,'overtime_flsa_eligible':False,'car_loan_eligible':False},
        'payments':{'estimated':'0','prior_year_credit':'0'},
        'eligibility':{'full_year_us_resident':False,'filing_status_confirmed':False,'all_income_reported':False,'eitc_not_applicable':False,'hoh_eligible':False,'qss_eligible':False,'mfs_spouse_itemizes':False,'mfs_lived_with_spouse':False,'student_loan_eligible':False,'itemized_eligible':False,'self_employed_health_insurance_eligible':False,'capital_gains_eligible':False,'qualified_dividends_eligible':False,'no_amt_preferences':False},
        'carryovers':{'capital_short':'0','capital_long':'0','qbi_loss':'0','charity':'0'},
        'unsupported':[],'notes':''}
    defaults['retirement'].update(annuity_gross='0',annuity_taxable='0',annuity_taxable_amounts_confirmed=False)
    defaults['retirement'].update(disability_taxpayer_gross='0',disability_taxpayer_taxable='0',disability_spouse_gross='0',disability_spouse_taxable='0',disability_before_minimum_retirement_age_confirmed=False,disability_amounts_confirmed=False)
    defaults['identity']={key:'' for key in ('first_name','middle_initial','last_name','ssn','spouse_first_name','spouse_middle_initial','spouse_last_name','spouse_ssn','address','apt','city','state','zip','foreign_country','foreign_province','foreign_postal_code','phone','email','occupation','spouse_occupation')}
    defaults.update(tax_extended.default_inputs())
    defaults.update(tax_credits.default_inputs())
    defaults.update(tax_additional.default_inputs())
    defaults.update(tax_longtail.default_inputs())
    defaults.update(tax_filing.default_inputs())
    defaults.update(tax_child_income.default_inputs())
    return defaults


ROW_DEFAULTS = {
 'w2':{'employer':'','owner':'taxpayer','wages':'0','dependent_care_benefits':'0','federal_withholding':'0','social_security_wages':'0','social_security_tips':'0','medicare_wages':'0','social_security_withholding':'0','medicare_withholding':'0'},
 'interest':{'payer':'','taxable':'0','tax_exempt':'0','federal_withholding':'0'},
 'dividends':{'payer':'','ordinary':'0','qualified':'0','capital_gain_distributions':'0','federal_withholding':'0'},
 'capital_gains':{'description':'','term':'long','proceeds':'0','cost_basis':'0','adjustment':'0','special_rate':False},
 'businesses':{'name':'','owner':'taxpayer','revenue':'0','expenses':'0','active_business':False,'expenses_eligible':False,'at_risk_confirmed':False,'qbi_eligible':False},
 'dependents':{'name':'','age':8,'qualifying_child':True,'valid_ssn':True,'valid_tin':True,'eligibility_confirmed':False}}
ROW_DEFAULTS['dividends'].update(unrecaptured_1250_gain='0',collectibles_gain='0',special_distribution_confirmed=False)
ROW_DEFAULTS['dependents'].update(tax_extended.DEPENDENT_FIELDS)
ROW_DEFAULTS['rentals']=deepcopy(tax_extended.RENTAL_TEMPLATE)
ROW_DEFAULTS['capital_gains'].update(wash_sale_disallowed='0',wash_sale_confirmed=False,adjustment_code='')
ROW_DEFAULTS['dependents'].update(tax_filing.DEPENDENT_FIELDS)


def capabilities():
    result = {'tax_year':2025,'currency':'USD','scope':'US full-year resident federal preparation worksheets; no filing',
            'implemented':['Form1040 income/tax/payments','official IRS tax table under100000','ordinary rate computation','qualified dividend/capital gain worksheet','basic ScheduleC and ScheduleSE per owner','Form8995 below simplified income threshold','ScheduleA cash charity/medical/eligible mortgage/SALT','Schedule8812 CTC/ACTC including three-child alternative','qualified US retirement-plan pension/IRA payer-taxable amounts and SS worksheet','student loan interest phaseout','Schedule1A eligible employee tips/FLSA overtime/car interest/seniors','ordinary Form8959 AdditionalMedicare and W2 excessSS credit'],
            'unsupported':['EITC','state/local/nonresident/part-year tax','AMT/Form6251 filing','NIIT/Form8960','IRA/HSA deductions and distributions requiring8606/5329','Marketplace/Form8962','education/adoption/dependent-care/energy/foreign credits','foreign income/exclusions','K1/rental/farm/royalties/passive income','QBI above8995 threshold/REIT/PTP/cooperatives','capital carry-in/special28%/1250 gains/wash-sale/QOF/options/crypto/business property','ScheduleC inventory/depreciation/home-office/employees/optionalSE','business tips deduction','prior-year carry-ins','estimated tax penalty Form2210'],
            'eligibility_fields':list(default_return()['eligibility']),
            'row_templates':deepcopy(ROW_DEFAULTS),'amount_input':'USD decimal strings, no floats','amount_output':'whole-dollar integers',
            'can_prepare_meaning':'Supported worksheet computation with all required affirmations and no detected blocking issue; not a filed return or complete IRS form set.'}
    result['implemented'] += ['2025 EITC exactIRS table and eligibility','NIIT Form8960 ordinary investment/rental/annuity income','AMT Form6251 PartsI-III with ordinary qualified gains and same-basis1099DIV special distributions','ScheduleE/Form8582 passive rental netting/25000 allowance/carry-out','Form4952 investment-interest limitation without preferred gain election']
    result['unsupported']=[v for v in result['unsupported'] if v not in ('EITC','AMT/Form6251 filing','NIIT/Form8960')]
    result.update(tax_extended.ui_schema())
    result['row_templates'].update(tax_credits.row_templates())
    result['row_templates'].update(tax_additional.row_templates())
    credit_capabilities=tax_credits.capabilities()
    result['implemented']+=credit_capabilities['implemented']
    result['unsupported']=['state/local/nonresident/part-year tax','adoption/energy/foreign credits','foreign income/exclusions','K1/farm/royalties/nonpassive rentals and real-estate professional/disposal/vacation-home cases','QBI above8995 threshold/REIT/PTP/cooperatives','capital carry-in/special28%/1250 gains/wash-sale/QOF/options/crypto/business property','ScheduleC inventory/depreciation/home-office/employees/optionalSE','business tips deduction','Form8801 prior AMT credit and separate AMT carryover/basis schedules','capital/QBI/charity carry-ins','estimated tax penalty Form2210','Form2441 prior-year expenses/FSA carry-in/SE assistance, ordinaryMFS exclusion/householdemployeeScheduleH/missingTIN due-diligence statement','Form8880 distribution-year nonjoint MFJ exception without per-column records']+credit_capabilities['unsupported']
    result['ui_fields'].update(tax_credits.ui_fields())
    additional_schema=tax_additional.ui_schema();result['ui_fields'].update(additional_schema['ui_fields']);result['ui_modules']+=additional_schema['ui_modules']
    result['ui_fields']['w2.*.dependent_care_benefits']={'type':'money','label':'Box10 dependent-care benefits','help':'Actual employeeBox10 benefits not already inBox1 wages; enableCare to compute excluded/taxable benefits.'}
    for owner in ('taxpayer','spouse'):
        for part in ('gross','taxable'):result['ui_fields']['retirement.disability_'+owner+'_'+part]={'type':'money','label':owner.capitalize()+' disability1099-R '+part,'help':'Separate from regularpension inputs. Employer disability pension before minimumretirementage is1040line1h; retain1099-R and eligibility/basis records.'}
    result['ui_fields']['retirement.disability_before_minimum_retirement_age_confirmed']={'type':'boolean','label':'Before employer minimumretirementage verified','help':'Only payments received before the actual employer-set minimumretirementdate. Split later pension amounts into regularpension fields.'}
    result['ui_fields']['retirement.disability_amounts_confirmed']={'type':'boolean','label':'Disability1099-R amounts and no doublecount verified'}
    result['implemented']+=['Form2441 dependent-care credit and employeeFSA exclusion/taxable benefits with monthlystudent/disability deemed income','Form8880 Saver credit with contribution/distribution and tax-liability limits','ScheduleR elderly/disabled credit with benefit andAGI reductions']
    result['ui_fields']['itemized.force_itemized']={'type':'boolean','label':'Elect itemized deductions even when smaller','help':'AMT can make a smaller ScheduleA deduction beneficial. Review both choices; automatic regular-tax deduction selection does not optimize the combined AMT liability.'}
    result['ui_modules']+=[{'id':key,'label':label,'step':'deductions','description':'Source-grounded IRS2025 worksheet with verified eligibility.'} for key,label in (('ira','IRA Contributions'),('hsa','Health Savings Accounts'),('education','Education Credits'),('marketplace','Marketplace Health Insurance'))]
    child_schema=tax_child_income.ui_schema()
    result['row_templates'].update(tax_child_income.row_templates())
    result['ui_fields'].update(child_schema['ui_fields']);result['ui_modules']+=child_schema['ui_modules']
    result['implemented'].append('Form8814 ordinarydomesticchildincome election withparentallocation,additional tax andseparateofficialchildforms')
    result['calculation_sources']=credit_capabilities['sources']
    longtail_schema=tax_longtail.ui_schema()
    result['row_templates'].update(tax_longtail.row_templates())
    result['ui_fields'].update(longtail_schema['ui_fields']);result['ui_modules']+=longtail_schema['ui_modules']
    result['ui_fields']['capital_gains.*.wash_sale_disallowed']={'type':'money','label':'Verified wash-sale disallowed loss (1099BBox1g)','help':'PositiveForm8949W adjustment; do not also enter sameamount in adjustment. Basisofreplacementlots mustbe verified separately.'}
    result['ui_fields']['capital_gains.*.wash_sale_confirmed']={'type':'boolean','label':'Wash-sale amount and replacement basis verified'}
    result['ui_fields']['capital_gains.*.adjustment_code']={'type':'enum','label':'Adjustment code','options':['','W'],'help':'Only verifiedW wash-sale loss is supported. Other8949basis/returnofcapital/corporateaction adjustments require separate evidence.'}
    result['ui_fields'].update(tax_filing.field_metadata());result['row_templates'].update(tax_filing.fact_schema()['row_templates'])
    result['ui_modules'].append({'id':'filing_details','label':'Filing details','step':'forms','description':'Actual Form1040 and supporting-form facts, directdeposit/designee choices and a paper-signature checklist. No transmission or automatic signature.'})
    result['implemented']+=['Ordinarysecurities verifiedshort/long capital loss carry-in and carryout worksheet; verified8949W wash-sale disallowedloss','2025Form8839 domestic/foreign/specialneeds adoption credit and5000-perchild refundableportion, FIFOunexpirednonrefundablecarryovers','2025Form5695 cleanenergy andhomeimprovement caps/QMID/carry-in andcarry-out with8812WorksheetB creditordering','Form2210 regularinstallment penalty usingactualdatedpayments/withholding andofficial2025-2026IRS periods','PassiveFTC qualifiedpayee300/600simplifiedelection andlimitedordinarypassive1116standarddeduction allocation']
    result['unsupported']=[v for v in result['unsupported'] if v not in ('adoption/energy/foreign credits','estimated tax penalty Form2210','capital/QBI/charity carry-ins','capital carry-in/special28%/1250 gains/wash-sale/QOF/options/crypto/business property')]
    result['unsupported']+=['Form2210 ScheduleAI/waiver/disaster/farmer/earlyfiling exception','Adoption employerbenefits8839PartIII andmissingTINstatement','ForeignFTC AMT/preferentialgain/loss/high-taxkickout/itemized/treaty/carryover/redetermination cases','Energy jointoccupant/business/condominium/multiyear enablingproperty allocations','Capital special28%/1250 trades/QOF/options/crypto/businessproperty andautomaticcrossaccountwash-sale discovery','QBI/charity carry-ins']
    result['coverage']={
      'income_and_tax':{'implemented':'W2/1099INT/1099DIV, ordinary securities gains/losses, payer-taxable retirement and SocialSecurity, exactIRS tax table and qualified-gain worksheet','sources':['i1040gi','i1040tt','i1040sd'],'limits':'No foreign/nonresident/territory returns, special capital rates, Form8615, prior capital carry-in or retirement basis conversion calculations.'},
      'service_business':{'implemented':'Active cash-service ScheduleC, per-ownerSE cap, deductiblehalfSE, eligibleSEhealth and simplified199A','sources':['i1040sc','f1040sse','f8995'],'limits':'No inventory, new depreciation4562, employees/payroll, home-office8829, farm, partnerships/K1, optionalSE or8995A above threshold.'},
      'deductions':{'implemented':'Standard and eligibleScheduleA medical/cashcharity/mortgage/SALT; Form4952 ordinary-income limit and carryout; student interest and2025Schedule1A','sources':['i1040sca','f4952','f1040s1a'],'limits':'Eligibility must be verified. No noncash charity appraisal, disaster losses or charity carry-in. force_itemized permits smaller deduction election; no automatic jointAMT optimization.'},
      'family_credits':{'implemented':'CTC/ODC/ACTC and2025 exact-table EITC; Form2441 care/FSA exclusions/monthlydeeming; Form8880 Saver; ScheduleR elderly/disabled','sources':['f1040s8','i1040gi','i1040tt','p596','f2441','i2441','f8880','f1040sr','i1040sr'],'limits':'No8862 disallowance recovery, combat-pay election or clergy/statutory-employee/inmate exceptions; noadoption credit. Careprior-year/FSAgraceperiod/SEbenefits/ordinaryMFS exclusion/householdemployeeScheduleH/missingTIN exceptions and Savernonjoint distribution-year exceptions require separate records.'},
      'investment_taxes':{'implemented':'AdditionalMedicare8959, ordinaryNIIT8960 including commercialannuity and allowedpassiverentals, deductibleinvestmentinterest/income-tax allocation, AMT6251 PartsI-III andISO adjustment','sources':['i8959','f8960','i8960','f6251','i6251'],'limits':'No foreigncredits, business/entity disposals, AMTcarry-in/basis records/8801 credit; special1250/collectiblesPartIII supports only verified1099DIV distributions with identical capitalbasis; source-derivedISO/AMTadjustments require confirmation. No automatic reconstruction of individualISOexercises.'},
      'rentals':{'implemented':'Ordinarypassive US real-estate ScheduleE, verifiedexpenses/depreciation, passive netting,25000/MFS12500 allowance, MAGIphaseout and property carryout','sources':['i1040se','f8582','i8582'],'limits':'No personal-use/vacation-home/self-rental/substantial-services/real-estate-professional/disposal/at-risk computation. Verifiedexistingdepreciation required; priorlossNIIT/QBIcharacter requires extra records.'},
      'ira_hsa_education_marketplace':{'implemented':credit_capabilities['implemented'],'sources':credit_capabilities['sources'],'limits':credit_capabilities['unsupported']},
      'filing_and_states':{'implemented':'Local identity draft, presence checklist and calculatedfederalworkpapers','sources':['i1040gi'],'limits':'No state/local returns, complete signed filing packet, electronicfiling or2210 penalty. Identity presence does not authenticate identity.'}}
    result['coverage']['income_and_tax']['limits']='No foreign/nonresident/territory returns, special-rate capital trades, Form8615 orretirementbasis/conversion calculations. Verified1099-DIV2a/2b/2d distributions andordinarysecurities carry-in/carryout/W adjustment supported. Special-rate distribution/trade/carryover netting andautomaticcrossaccountlot reconstruction are not performed.'
    result['coverage']['family_credits']['implemented']+='; Form8839domestic/foreign/specialneeds credit withnew5000-perchildrefund andunexpiredFIFOcarryovers;8812WorksheetB ordering'
    result['coverage']['family_credits']['limits']='ExistingCare/Saver/EIC exceptions remain; adoption employerbenefits/absentTIN statement andexpense-age exceptions needseparate records.'
    result['coverage']['investment_taxes']['implemented']+='; passiveFTC qualifiedpayee300/600election andordinarypassive1116 standardallocation'
    result['coverage']['investment_taxes']['limits']='No AMTFTC, foreignpreferredgain/high-taxkickout/foreignloss/category/treaty/carryover/redetermination allocation; noforeigncreditsdeductedelsewhere. ExistingAMTbasis/8801/entitydisposal/specialrates limitsremain.'
    result['coverage']['energy']={'implemented':'Form5695cleanenergy30percent/fuelcellcapacity/carry-in-out andhomeimprovementcategory/annualcaps/QMID, prioritywithadoption/CTC','sources':['f5695','i5695','i1040s8'],'limits':'Nojointoccupant/business/condominiumallocation ormultiyear enablingproperty. Actualqualification/manufacturercertification andneteligiblecosts required.'}
    result['coverage']['estimated_penalty']={'implemented':'Form2210 regular-installment safeharbor,datedestimatedpayments/withholding/priorcredit/balancepayment and365day7percent periods','sources':['f2210','i2210'],'limits':'NoScheduleAI/disasterwaiver/farmer/earlyfilingexception. Line38 isseparatefromline37;payment_summary exposes balancewithpenalty.'}
    result['coverage']['filing_and_states']['limits']='Electronicfiling/automaticpaper signature notimplemented. Detailedidentity/directdeposit/designee andactualsupportingformfacts are localdraft inputs; presencechecks donot authenticateidentity. Supportingpaperpacket completion isreportedseparately bytheformbuilder.'
    result['implemented']+=['Verified1099-DIV boxes2a/2b/2d and ScheduleD25%/28% TaxWorksheet']
    result['ui_fields']['dividends.*.capital_gain_distributions']={'type':'money','label':'1099-DIV Box2a total capital gain distributions','help':'Includes Box2b and Box2d; do not add those components to Box2a again.'}
    result['ui_fields']['dividends.*.unrecaptured_1250_gain']={'type':'money','label':'1099-DIV Box2b unrecaptured Section1250 gain'}
    result['ui_fields']['dividends.*.collectibles_gain']={'type':'money','label':'1099-DIV Box2d collectibles28% gain'}
    result['ui_fields']['dividends.*.special_distribution_confirmed']={'type':'boolean','label':'1099-DIV special distribution amounts verified','help':'Verify original2a/2b/2d and noQSBS2c, nominee/other allocation, foreign stacking or other special-gain source. This profile supports distributions only; Trades/carryovers/4952 elections, foreign stacking and Marketplace repayments are outside this profile. Special-rate AMT requires the same capital basis for regular tax and AMT.'}
    result['coverage']['income_and_tax']['special_distribution_scope']='1099-DIV2a/2b/2d distributions only, fullScheduleD25%/28% TaxWorksheet. No trades/losses/carryovers/4952 election/QSBS/foreign stacking. FullForm6251 PartIII special-rate AMT supports identical regular/AMT capital basis and confirmed quantified ISO/private-activity-bond adjustments; differentcapitalbasis remains blocked.'
    return result


def form_readiness(data):
    """Presence-only checklist; neither an identity check nor filing approval."""
    identity=data['identity']
    required=[('first_name','Taxpayer first name'),('last_name','Taxpayer last name'),('ssn','Taxpayer SSN'),('address','Street address'),('city','City'),('state','State'),('zip','ZIP code')]
    if data['filing_status'] in ('mfj','mfs'):required += [('spouse_first_name','Spouse first name'),('spouse_last_name','Spouse last name'),('spouse_ssn','Spouse SSN')]
    return {'filing_packet_ready':False,'missing_identity':[label for key,label in required if not identity[key].strip()],
        'unsupported_packet_parts':['Supporting-form completeness is evaluated by the paper-packet checklist; taxpayer signature and original withholding document attachments are required']+([] if data['estimated_penalty']['enabled'] else ['Form 2210 estimated-tax penalty not computed']),
            'electronic_filing':False,'identity_check':'Required-field presence only; names, addresses and SSNs have not been authenticated.',**tax_filing.paper_facts_readiness(data)}


def normalized(data):
    if not isinstance(data,dict):raise ValueError('Return input must be a JSON object.')
    base=default_return()
    unknown=set(data)-set(base)
    if unknown:raise ValueError('Unknown return fields: '+', '.join(sorted(unknown)))
    for key,value in data.items():
        if isinstance(base[key],dict):
            if not isinstance(value,dict):raise ValueError(key+' must be an object.')
            unknown=set(value)-set(base[key])
            if unknown:raise ValueError('Unknown '+key+' fields: '+', '.join(sorted(unknown)))
            base[key].update(value)
        else:base[key]=deepcopy(value)
    if type(base['tax_year']) is not int or base['tax_year']!=2025:raise ValueError('Only US tax year2025 is implemented.')
    if base['filing_status'] not in STATUSES:raise ValueError('Invalid filing_status.')
    for key in ('name','notes'):
        if not isinstance(base[key],str) or len(base[key])>10000:raise ValueError(key+' must be text of at most10000 characters.')
    for group,template in ROW_DEFAULTS.items():
        if not isinstance(base[group],list) or len(base[group])>500:raise ValueError(group+' must be a list of at most500 objects.')
        rows=[]
        for index,submitted in enumerate(base[group]):
            if not isinstance(submitted,dict):raise ValueError(f'{group}[{index}] must be an object.')
            unknown=set(submitted)-set(template)
            if unknown:raise ValueError(f'Unknown {group}[{index}] fields: '+', '.join(sorted(unknown)))
            row=deepcopy(template);row.update(submitted)
            for field,value in row.items():
                path=f'{group}[{index}].{field}'
                if field=='age':age(value,path)
                elif isinstance(template[field],bool):boolean(value,path)
                elif field in ('owner','term'):
                    if value not in (('taxpayer','spouse') if field=='owner' else ('short','long')):raise ValueError(path+' is invalid.')
                    if field=='owner' and value=='spouse' and base['filing_status']!='mfj':raise ValueError(path+' spouse income can only be included in MFJ.')
                elif field in ('employer','payer','name','description'):
                    if not isinstance(value,str) or len(value)>1000:raise ValueError(path+' must be text.')
                elif field=='adjustment_code':
                    if value not in ('','W'):raise ValueError(path+' only permits an emptycode or verifiedW.')
                elif field in tax_filing.DEPENDENT_FIELDS and isinstance(tax_filing.DEPENDENT_FIELDS[field],str):
                    if not isinstance(value,str) or len(value)>200:raise ValueError(path+' must be textofatmost200characters.')
                else:money(value,path,signed=field=='adjustment')
            rows.append(row)
        base[group]=rows
    for group in ('taxpayer','spouse','retirement','other_income','adjustments','itemized','schedule_1a','payments','eligibility','carryovers'):
        template=default_return()[group]
        for field,value in base[group].items():
            path=group+'.'+field
            if field=='age':age(value,path)
            elif isinstance(template[field],bool):boolean(value,path)
            elif field=='ira_distribution_kind':
                if value not in ('fully_taxable','qualified_rollover','other'):raise ValueError(path+' is invalid.')
            else:money(value,path)
    if not isinstance(base['unsupported'],list) or any(not isinstance(v,str) for v in base['unsupported']):raise ValueError('unsupported must be a list of situation names.')
    for key,value in base['identity'].items():
        if not isinstance(value,str) or len(value)>200:raise ValueError('identity.'+key+' must be text of at most200 characters.')
        if key in ('ssn','spouse_ssn') and not re.fullmatch(r'[0-9-]*',value):raise ValueError('identity.'+key+' only permits digits and hyphens, or an empty draft value.')
        base['identity'][key]=''.join(' ' if ord(character)<32 or ord(character)==127 else character for character in value).strip()
    tax_extended.normalize_extra(base,base['filing_status'])
    tax_longtail.normalize_extra(base)
    tax_child_income.normalize_extra(base)
    tax_filing.validate_facts(base)
    return base


def ordinary_tax(income,status):
    income=max(0,int(income))
    if income<100000:
        row=RULES['tax_table'][bisect_right(TABLE_LOW,income)-1]
        return row[{'single':2,'mfj':3,'qss':3,'mfs':4,'hoh':5}[status]]
    value=D('0');previous=0
    for upper,rate in RULES['brackets']['mfj' if status=='qss' else status]:
        top=income if upper is None else min(income,upper)
        value+=D(max(0,top-previous))*D(rate)
        if upper is None or income<=upper:break
        previous=upper
    return dollars(value)


def qualified_tax(taxable,preferred,status):
    ordinary=max(0,taxable-preferred)
    zero_limit,fifteen_limit=RULES['capital_rates'][status]
    at_zero=max(0,min(taxable,zero_limit)-min(ordinary,min(taxable,zero_limit)))
    preferred_taxable=min(taxable,preferred)
    remaining=max(0,preferred_taxable-at_zero)
    at_fifteen=min(remaining,max(0,min(taxable,fifteen_limit)-ordinary-at_zero))
    at_twenty=max(0,preferred_taxable-at_zero-at_fifteen)
    tax_ordinary=ordinary_tax(ordinary,status)
    combined=tax_ordinary+dollars(D(at_fifteen)*D('.15'))+dollars(D(at_twenty)*D('.20'))
    return min(combined,ordinary_tax(taxable,status)),{
        'ordinary_income':ordinary,'zero_rate_income':at_zero,'fifteen_rate_income':at_fifteen,'twenty_rate_income':at_twenty,
        'ordinary_tax':tax_ordinary,'worksheet_tax_before_regular_limit':combined,'regular_tax_limit':ordinary_tax(taxable,status)}


def calculate_return(data):
    with localcontext() as context:
        context.prec=40
        return _calculate(normalized(data))


def _calculate(data):
    status=data['filing_status'];elig=data['eligibility'];person=data['taxpayer'];spouse=data['spouse']
    lines={key:0 for key in LINE_KEYS};blocks=[];warnings=[];trace=[];schedules={}
    def module_result(name,section,context):
        function=getattr(tax_credits,name,None)
        if function is None:
            if section.get('enabled'):raise ValueError(name+' module is not ready in this source snapshot.')
            return {'deduction':0,'other_income':0,'additional_tax':0,'nonrefundable_credit':0,'refundable_credit':0,'repayment':0,'blocking_issues':[],'warnings':[],'trace':[],'form_lines':{}}
        result=function(section,context)
        blocks.extend(result.get('blocking_issues',[]));warnings.extend(result.get('warnings',[]));trace.extend(result.get('trace',[]))
        return result
    def extended_result(name,result):
        blocks.extend(result.get('blocking_issues',[]));warnings.extend(result.get('warnings',[]));trace.extend(result.get('trace',[]));schedules[name]=result
        return result
    def block(message):
        if message not in blocks:blocks.append(message)
    def log(label,amount,source='i1040gi'):
        trace.append({'label':label,'amount':int(amount),'source':RULES['sources'][source]['url']})
    def require(condition,message):
        if not condition:block(message)
    def total(group,field):return dollars(sum((money(row[field]) for row in data[group]),D('0')))
    def n(group,field):return dollars(money(data[group][field]))
    def has(group,field):return money(data[group][field])!=0
    for field in ('full_year_us_resident','filing_status_confirmed','all_income_reported'):
        require(elig[field],'Confirm eligibility.'+field+' before preparing a supported return.')
    if status=='hoh':require(elig['hoh_eligible'],'Head-of-household qualifying person, unmarried status and household cost tests must be confirmed.')
    if status=='qss':require(elig['qss_eligible'],'Qualifying-surviving-spouse eligibility must be confirmed, including death-year and child/home tests.')
    if status=='mfj' and (person['can_be_claimed'] or spouse['can_be_claimed']):block('MFJ dependent-standard-deduction exception is not implemented.')
    if person['can_be_claimed'] and data['dependents']:block('A claimed taxpayer cannot ordinarily claim another dependent; dependent/credit exception review is not implemented.')
    for situation in data['unsupported']:block('Unsupported tax situation: '+situation)
    for field in data['carryovers']:
        if has('carryovers',field):
            if field in ('capital_short','capital_long'):require(data['capital_records']['carry_in_confirmed'],'Priorcapital loss carry-in requires verified2024 short/long loss carryover worksheet and owner allocation.')
            else:block('Prior-year '+field+' carry-in is not implemented; no amount has been silently applied.')
    for index,row in enumerate(data['w2']):
        if money(row['wages'])>0 and money(row['medicare_wages'])==0:
            block(f'W2 {index+1}: positive ordinary wages require the actual Box5 Medicare wage amount. Zero/default Box5 cannot silently omit Form8959; Medicare-exempt/RRTA/special payroll requires an unsupported-wage review.')
    child_election=extended_result('form_8814',tax_child_income.calculate(data['child_income_election']))
    lines['1a']=total('w2','wages');lines['2a']=total('interest','tax_exempt');lines['2b']=total('interest','taxable')
    lines['3a']=total('dividends','qualified');lines['3b']=total('dividends','ordinary')
    if lines['3a']:require(elig['qualified_dividends_eligible'],'Qualified dividends require payer qualification, holding-period/no-related-payment tests and no investment-interest election; confirm eligibility.')
    lines['3a']+=child_election['parent_qualified_dividends'];lines['3b']+=child_election['parent_qualified_dividends']
    for row in data['dividends']:
        if money(row['qualified'])>money(row['ordinary']):raise ValueError('Qualified dividends cannot exceed ordinary dividends from the same payer.')
    special_1250=total('dividends','unrecaptured_1250_gain');special_28=total('dividends','collectibles_gain')
    special_requested=any(money(row['unrecaptured_1250_gain']) or money(row['collectibles_gain']) for row in data['dividends'])
    for row in data['dividends']:
        components=money(row['unrecaptured_1250_gain'])+money(row['collectibles_gain'])
        if components>money(row['capital_gain_distributions']):raise ValueError('1099-DIV boxes2b+2d cannot exceed Box2a total capital gain distributions.')
        if components:require(row['special_distribution_confirmed'],'Verify original1099-DIV boxes2a/2b/2d and confirm noQSBS/nominee/other special-gain allocations before preparing this distribution worksheet.')
    if special_requested:
        require(not data['capital_gains'] and not has('carryovers','capital_short') and not has('carryovers','capital_long'),'Special-rate1099-DIV distributions combined with securities trades/losses/carryovers require separate ScheduleD netting and are not supported by this profile.')
        require(not has('itemized','investment_interest') and not has('niit','investment_interest_carryover'),'Special-rate distributions with Form4952 investment-interest deductions/election/carryover require separate allocation.')
        require(not data['foreign_credit']['enabled'],'Special-rate distributions with foreign-tax credits/foreign income stacking require separate allocation.')
        require(not data['marketplace']['enabled'],'Special-rate distribution AMT with Marketplace Form8962 repayment requires the complete Form6251 line10 comparator and is outside this verified profile.')
    short=D('0');long=D('0')
    for row in data['capital_gains']:
        ordinary_adjustment=money(row['adjustment'],signed=True);wash=money(row['wash_sale_disallowed'])
        if wash and ordinary_adjustment:raise ValueError('Wash-sale adjustment entered twice; use wash_sale_disallowed OR originaladjustment withcodeW.')
        actual_wash=wash if wash else ordinary_adjustment if row['adjustment_code']=='W' else D(0)
        if actual_wash:
            if actual_wash<0 or actual_wash>max(D(0),money(row['cost_basis'])-money(row['proceeds'])):raise ValueError('Wash-sale disallowedloss must bepositive and cannot exceed actualunadjusted loss.')
            require(row['wash_sale_confirmed'] and data['capital_records']['wash_sale_all_accounts_reviewed'],'Wash-sale loss needs verified61-day allaccounts/spouse/IRA matching and replacementbasis; no missinglot search isperformed.')
        gain=money(row['proceeds'])-money(row['cost_basis'])+ordinary_adjustment+wash
        if row['special_rate']:block('Collectibles/section1250/1202 and special-rate capital gains require an unimplemented ScheduleD worksheet.')
        if row['term']=='short':short+=gain
        else:long+=gain
    if data['capital_gains'] or total('dividends','capital_gain_distributions'):
        require(elig['capital_gains_eligible'],'Confirm ordinary securities, verified holdingperiod/basis, documentedwash-saleW only, and noQOF/options/crypto/business-property/special-rate adjustments.')
        if any(money(row['adjustment'],signed=True)!=0 and row['adjustment_code']!='W' for row in data['capital_gains']):block('Form8949 nonW basis/adjustment code workflow is not implemented; nonzero adjustment requires review.')
    short=dollars(short-money(data['carryovers']['capital_short']));long=dollars(long-money(data['carryovers']['capital_long']))+total('dividends','capital_gain_distributions')+child_election['parent_capital_gain'];net=short+long
    capital_limit=1500 if status=='mfs' else 3000
    lines['7a']=max(net,-capital_limit)
    preferred_gain=max(0,min(long,net))
    schedules['schedule_d']={'net_short_term':short,'net_long_term':long,'net_gain_loss':net,'income_line_7a':lines['7a'],'unabsorbed_current_loss':max(0,-net-capital_limit),'carry_out_requires_next_year_worksheet':net<-capital_limit}
    schedules['schedule_d'].update(capital_short_carry_in=n('carryovers','capital_short'),capital_long_carry_in=n('carryovers','capital_long'),wash_sale_adjustments=[{'description':row['description'],'code':'W','disallowed_loss':dollars(money(row['wash_sale_disallowed']) or money(row['adjustment'],signed=True))} for row in data['capital_gains'] if money(row['wash_sale_disallowed']) or row['adjustment_code']=='W' and money(row['adjustment'],signed=True)])
    if net<-capital_limit:warnings.append('Current capital loss exceeds the annual deduction. Next-year short/long carryover requires the IRS carryover worksheet; no future return has been prepared.')
    profits={'taxpayer':0,'spouse':0};business_rows=[]
    for index,row in enumerate(data['businesses']):
        revenue=dollars(money(row['revenue']));expenses=dollars(money(row['expenses']))
        profit=revenue-expenses;profits[row['owner']]+=profit
        for field in ('active_business','expenses_eligible','at_risk_confirmed','qbi_eligible'):
            require(row[field],f'Business {index+1}: confirm {field}; only active cash-service ScheduleC businesses without special forms are supported.')
        business_rows.append({'name':row['name'],'owner':row['owner'],'gross_revenue':revenue,'total_expenses':expenses,'profit':profit})
    if sum(profits.values())<-(626000 if status=='mfj' else 313000):block('Excess business loss/Form461/NOL limitations are not implemented.')
    schedule_se={};se_total=0;half_se=0
    for owner,profit in profits.items():
        wages=dollars(sum((money(row['social_security_wages'])+money(row['social_security_tips']) for row in data['w2'] if row['owner']==owner),D('0')))
        earnings=dollars(D(profit)*D('.9235')) if profit>0 else 0
        if earnings<400:earnings=0
        social_tax=dollars(D(min(earnings,max(0,176100-wages)))*D('.124'))
        medicare_tax=dollars(D(earnings)*D('.029'));tax=social_tax+medicare_tax;deduction=dollars(D(tax)*D('.5'))
        schedule_se[owner]={'net_profit':profit,'w2_ss_wages_tips':wages,'line_4a_net_earnings':earnings,'line_10_ss_tax':social_tax,'line_11_medicare_tax':medicare_tax,'line_12_tax':tax,'line_13_deduction':deduction}
        se_total+=tax;half_se+=deduction
    schedules['schedule_c']=business_rows;schedules['schedule_se']=schedule_se
    disability_by_owner={owner:n('retirement','disability_'+owner+'_taxable') for owner in ('taxpayer','spouse')}
    disability_total=dollars(sum((money(data['retirement']['disability_'+owner+'_taxable']) for owner in ('taxpayer','spouse')),D(0)))
    for owner in ('taxpayer','spouse'):
        gross=money(data['retirement']['disability_'+owner+'_gross']);taxable=money(data['retirement']['disability_'+owner+'_taxable'])
        if taxable>gross:raise ValueError('Disability taxable amount cannot exceed gross1099-R amount.')
        if gross:
            if owner=='spouse' and status!='mfj':raise ValueError('Spouse disability income only belongs inMFJ.')
            require(data['retirement']['disability_before_minimum_retirement_age_confirmed'] and data['retirement']['disability_amounts_confirmed'],'Disability1099-R needs verified employer minimumretirementage, source taxable amount and exclusion from regularpension inputs.')
            require(data['retirement']['qualified_plan_confirmed'],'Disability1099-R support is limited to verified qualifiedUSemployer retirementplans; nonqualified/foreign disability contracts need separate NIIT/distribution classification.')
            if (person if owner=='taxpayer' else spouse)['age']<60:require(data['retirement']['early_distribution_exception_confirmed'],'Verify disability1099-R additional10%tax exception; no unverifiedearly-distribution exemption is assumed.')
        if data['elderly_credit']['enabled'] and data['elderly_credit'][owner+'_permanently_disabled'] and (person if owner=='taxpayer' else spouse)['age']<65:
            claimed=dollars(money(data['elderly_credit'][owner+'_taxable_disability_income']))
            if claimed>disability_by_owner[owner] and not data['elderly_credit'][owner+'_after_minimum_retirement_age_confirmed']:block('Classify ScheduleR disability pension by employer MINIMUM retirementage: beforeminimum belongs in separate1099-R line1h inputs; afterminimum remains5b with explicit age confirmation. ScheduleR preMANDATORY retirementage eligibility is a separate test.')
    care_earned={owner:disability_by_owner[owner]+dollars(sum((money(row['wages']) for row in data['w2'] if row['owner']==owner),D(0)))+profits[owner]-schedule_se[owner]['line_13_deduction'] for owner in ('taxpayer','spouse')}
    care_benefits={owner:dollars(sum((money(row['dependent_care_benefits']) for row in data['w2'] if row['owner']==owner),D(0))) for owner in ('taxpayer','spouse')}
    benefits_line12=total('w2','dependent_care_benefits');care_benefits['spouse']+=benefits_line12-sum(care_benefits.values())
    care_context={'filing_status':status,'agi':0,'earned_taxpayer':care_earned['taxpayer'],'earned_spouse':care_earned['spouse'],'benefits_received':sum(care_benefits.values()),'benefits_taxpayer':care_benefits['taxpayer'],'benefits_spouse':care_benefits['spouse'],'tax_liability_limit':0}
    care_income_result=tax_additional.calculate_care(data['care'],care_context)
    care_taxable=care_income_result['taxable_benefits'];care_by_owner=care_income_result.get('taxable_by_owner',{'taxpayer':0,'spouse':0})
    if data['businesses']:
        for row in data['w2']:
            if money(row['wages'])>0 and money(row['social_security_wages'])+money(row['social_security_tips'])==0:
                block('ScheduleSE requires actual W2 boxes3+7 by owner; zero SS wages with positive wages requires exempt-wage review.')
    log('ScheduleSE tax',se_total,'f1040sse');log('Schedule1 line15 deductible half SE tax',half_se,'f1040sse')
    retirement=data['retirement']
    for gross,taxable in (('ira_gross','ira_taxable'),('pension_gross','pension_taxable'),('annuity_gross','annuity_taxable')):
        if money(retirement[taxable])>money(retirement[gross]):raise ValueError('Retirement taxable amount cannot exceed its gross amount.')
    lines['4a']=n('retirement','ira_gross');lines['4b']=n('retirement','ira_taxable');lines['5a']=dollars(money(retirement['pension_gross'])+money(retirement['annuity_gross']));lines['5b']=dollars(money(retirement['pension_taxable'])+money(retirement['annuity_taxable']));lines['6a']=n('retirement','social_security')
    if lines['4a'] or n('retirement','pension_gross'):
        require(retirement['taxable_amounts_confirmed'],'Verify retirement taxable amounts from payer documents; Form8606/basis/conversion/QCD calculations are not implemented.')
        youngest_possible_recipient=min(person['age'],spouse['age']) if status=='mfj' else person['age']
        if youngest_possible_recipient<60 and (lines['4b'] or lines['5b']):require(retirement['early_distribution_exception_confirmed'],'A possible recipient below60 requires verified recipient age/1099R exception; spouse allocation and Form5329 early-distribution tax are not implemented.')
        if retirement['ira_distribution_kind']=='other' or (lines['4b']!=lines['4a'] and retirement['ira_distribution_kind']!='qualified_rollover'):block('Partly taxable IRA/basis/QCD/conversion requires an unimplemented retirement worksheet.')
        if retirement['ira_distribution_kind']=='qualified_rollover' and lines['4b']!=0:block('A fully qualified rollover must have zero taxable IRA amount.')
    if n('retirement','pension_gross'):
        require(retirement['qualified_plan_confirmed'],'Pension inputs support only qualified US retirement-plan distributions. Nonqualified commercial annuities/foreign pensions and mixed distributions require unimplemented NIIT/treaty worksheets; confirm qualified_plan_confirmed only for a qualified plan.')
    if n('retirement','annuity_gross'):
        require(retirement['annuity_taxable_amounts_confirmed'],'Nonqualified US annuity taxable amount must be verified from1099R/basis computation; foreign/treaty contracts are not modeled.')
        if (person['age']<60 or status=='mfj' and spouse['age']<60) and n('retirement','annuity_taxable'):
            require(retirement['early_distribution_exception_confirmed'],'Nonqualified annuity early-distribution section72(q) exceptions require verification; additional10%tax is not inferred.')
    if retirement['ss_lump_sum_or_repayments']:block('SocialSecurity lump-sum election, benefit repayments and pre-retirement injury exclusions require Pub915 worksheets not implemented here.')
    if has('other_income','other'):require(data['other_income']['taxable_other_confirmed'],'Confirm other income is ordinary fully taxable non-SE income with no special deductions/forms.')
    common_credit_context={'filing_status':status,'taxpayer_age':person['age'],'spouse_age':spouse['age']}
    hsa_result=module_result('calculate_hsa',data['hsa'],common_credit_context);schedules['form_8889']=hsa_result
    hsa_ded=hsa_result.get('deduction',0);hsa_income=hsa_result.get('other_income',0);hsa_tax=hsa_result.get('additional_tax',0)
    lines['8']=sum(profits.values())+n('other_income','unemployment')+n('other_income','other')+hsa_income+child_election['parent_ordinary_other_income']
    for field in ('ira_deduction','hsa_deduction'):
        if has('adjustments',field):block('Legacy manual '+field+' is not applied; use the IRA/HSA module with verified contribution and eligibility facts instead.')
    health=0
    if has('adjustments','self_employed_health_insurance'):
        require(elig['self_employed_health_insurance_eligible'],'Self-employed health premiums must be paid under the business, outside employer-plan eligible months, with no PTC/double deduction; confirm eligibility.')
        if len(data['businesses'])!=1:block('Health insurance owner allocation across multiple businesses is not implemented.')
        owner=data['businesses'][0]['owner'] if data['businesses'] else 'taxpayer'
        health=min(n('adjustments','self_employed_health_insurance'),max(0,profits[owner]-schedule_se[owner]['line_13_deduction']))
    preliminary_other=disability_total+care_taxable+sum(lines[key] for key in ('1a','2b','3b','4b','5b','7a','8'))
    rental=extended_result('schedule_e',tax_extended.rental_return(data['rentals'],{'filing_status':status,'magi_without_rentals':preliminary_other-health-hsa_ded,'mfs_lived_with_spouse':elig['mfs_lived_with_spouse']}))
    lines['8']+=rental['income']
    prior_adjustments=half_se+health+hsa_ded
    other_total=disability_total+care_taxable+sum(lines[key] for key in ('1a','2b','3b','4b','5b','7a','8'))
    compensation={owner:care_by_owner[owner]+dollars(sum((money(row['wages']) for row in data['w2'] if row['owner']==owner),D('0')))+max(0,profits[owner]-schedule_se[owner]['line_13_deduction']) for owner in ('taxpayer','spouse')}
    ira_context=dict(common_credit_context,compensation_taxpayer=compensation['taxpayer'],compensation_spouse=compensation['spouse'],magi_before_ira=other_total-prior_adjustments,full_year_us_resident=elig['full_year_us_resident'],taxpayer_can_be_claimed=person['can_be_claimed'],spouse_can_be_claimed=spouse['can_be_claimed'],social_security_received=lines['6a']>0,ira_distribution_received=lines['4a']>0)
    ira_result=module_result('calculate_ira',data['ira'],ira_context);schedules['ira_contributions']=ira_result
    ira_ded=ira_result.get('deduction',0);prior_adjustments+=ira_ded
    # Official SS worksheet excludes student-loan line21 from its line6.
    provisional=max(0,dollars(D(lines['6a'])*D('.5'))+other_total+lines['2a']-prior_adjustments)
    if status=='mfs' and elig['mfs_lived_with_spouse']:
        ss_taxable=min(dollars(D(provisional)*D('.85')),dollars(D(lines['6a'])*D('.85')))
    else:
        base=32000 if status=='mfj' else 25000;span=12000 if status=='mfj' else 9000
        excess=max(0,provisional-base)
        ss_taxable=min(dollars(D(lines['6a'])*D('.85')),min(dollars(D(lines['6a'])*D('.5')),dollars(D(min(excess,span))*D('.5')))+dollars(D(max(0,excess-span))*D('.85')))
    lines['6b']=ss_taxable;lines['9']=other_total+ss_taxable
    log('SocialSecurity taxable amount',ss_taxable)
    student=0;student_magi=lines['9']-prior_adjustments
    if has('adjustments','student_loan_interest'):
        require(elig['student_loan_eligible'],'Student loan interest must be qualified and legally owed, taxpayer not a claimed dependent; confirm eligibility.')
        if status=='mfs' or person['can_be_claimed'] or (status=='mfj' and spouse['can_be_claimed']):warnings.append('Student loan deduction is zero because MFS/dependent status is ineligible.')
        else:
            start=170000 if status=='mfj' else 85000;span=30000 if status=='mfj' else 15000
            amount=min(2500,n('adjustments','student_loan_interest'));ratio=min(D('1'),D(max(0,student_magi-start))/D(span))
            student=amount-dollars(D(amount)*ratio)
    lines['10']=prior_adjustments+student;lines['11a']=lines['11b']=lines['9']-lines['10'];agi=lines['11b']
    schedules['schedule_1']={'business_income':sum(profits.values()),'half_se_tax':half_se,'self_employed_health_insurance':health,'student_loan_interest':student,'hsa_deduction':hsa_ded,'hsa_other_income':hsa_income,'ira_deduction':ira_ded,'rental_income_loss':rental['income'],'legacy_manual_ira_hsa_deductions_not_applied':True}
    log('Student loan interest deduction',student);log('Adjusted gross income',agi)
    base_standard=RULES['standard'][status]
    earned=max(0,lines['1a']+sum(profits.values())-half_se)
    if person['can_be_claimed']:base_standard=min(base_standard,max(1350,earned+450))
    boxes=int(person['age']>=65)+int(person['blind'])
    if status=='mfj':boxes+=int(spouse['age']>=65)+int(spouse['blind'])
    standard=base_standard+boxes*RULES['additional_standard'][status]
    if status=='mfs' and elig['mfs_spouse_itemizes']:standard=0
    if status=='mfs' and (spouse['age']>=65 or spouse['blind']):
        block('MFS spouse senior/blind additional-standard-deduction exception requires spouse income/filing/dependency review, not implemented.')
    medical=max(0,n('itemized','medical')-dollars(D(max(0,agi))*D('.075')))
    salt_max=20000 if status=='mfs' else 40000;salt_floor=5000 if status=='mfs' else 10000;salt_start=250000 if status=='mfs' else 500000
    salt_limit=max(salt_floor,salt_max-dollars(D(max(0,agi-salt_start))*D('.30')))
    salt=min(n('itemized','state_local_tax'),salt_limit)
    mortgage=n('itemized','mortgage_interest')
    charity=min(n('itemized','charity'),dollars(D(max(0,agi))*D('.60')))
    if any(has('itemized',field) for field in ('medical','state_local_tax','mortgage_interest','charity','investment_interest')):require(elig['itemized_eligible'],'Confirm itemized expenses are qualified, paid by this household and not reimbursed or deducted elsewhere.')
    if has('itemized','medical'):require(data['itemized']['medical_eligible'],'Medical expenses must be qualifying unreimbursed expenses without duplicate health deductions.')
    if mortgage:require(data['itemized']['mortgage_eligible'],'Mortgage acquisition-debt, secured-residence, principal-limit and use tests must be verified before entering deductible interest.')
    if has('itemized','charity'):require(data['itemized']['charity_cash_only'],'Only substantiated qualified cash charity subject to60%-AGI limit is supported; noncash/different-limit gifts require additional forms.')
    interest_result=extended_result('form_4952',tax_extended.investment_interest(data['niit'],{'paid':n('itemized','investment_interest'),'interest':lines['2b'],'other_investment_income':child_election['investment_interest_other_income'],'ordinary_dividends':lines['3b'],'qualified_dividends':lines['3a'],'annuity':n('retirement','annuity_taxable'),'net_gain':net,'preferred_gain':preferred_gain}))
    investment_interest_ded=interest_result['deduction']
    itemized=medical+salt+mortgage+charity+investment_interest_ded
    deduction_type='itemized' if data['itemized']['force_itemized'] or itemized>standard or (status=='mfs' and elig['mfs_spouse_itemizes']) else 'standard'
    lines['12e']=itemized if deduction_type=='itemized' else standard
    schedules['schedule_a']={'medical_after_7_5_percent':medical,'salt_limit':salt_limit,'salt_deduction':salt,'mortgage_interest':mortgage,'investment_interest':investment_interest_ded,'cash_charity':charity,'charity_above_current_limit':max(0,n('itemized','charity')-charity),'itemized_total':itemized,'standard_deduction':standard,'chosen':deduction_type}
    if n('itemized','charity')>charity:warnings.append('Cash charity exceeds the current60%-AGI limit; future carryover preparation is not implemented.')
    schedule1a=data['schedule_1a'];tips=n('schedule_1a','qualified_tips');overtime=n('schedule_1a','qualified_overtime');car=n('schedule_1a','qualified_car_loan_interest')
    senior_count=(int(person['age']>=65 and person['valid_ssn'])+(int(spouse['age']>=65 and spouse['valid_ssn']) if status=='mfj' else 0)) if status!='mfs' else 0
    if tips or overtime or car or senior_count:require(schedule1a['eligibility_confirmed'],'Schedule1A eligibility, valid SSNs and documented included compensation/qualified loan must be confirmed.')
    if tips:
        require(schedule1a['tips_occupation_eligible'] and schedule1a['tips_not_sstb'],'Qualified tips require listed occupation, voluntary reported cash tips and no specified-service-business exclusion.')
        if data['businesses']:block('Self-employed/mixed employee-business tips and QBI interaction are not implemented.')
        if tips>lines['1a']:raise ValueError('Qualified employee tips must be included in reported W2 wages.')
    if overtime:
        require(schedule1a['overtime_flsa_eligible'],'Overtime deduction requires only the FLSA premium portion already included in income, not all overtime wages.')
        if overtime>lines['1a']:raise ValueError('Supported qualified overtime must be included in reported W2 wages.')
    if tips+overtime>lines['1a']:raise ValueError('Distinct qualified employee tips and overtime cannot exceed their included W2 compensation.')
    if car:require(schedule1a['car_loan_eligible'],'Car loan must be qualifying new2025 personal vehicle, original-use, final-US-assembly and secured loan; taxpayer must retain VIN/documentation.')
    if status=='mfs' and (tips or overtime):block('Married filing separately cannot claim qualified tips/overtime deductions.')
    if (tips or overtime) and not(person['valid_ssn'] and (status!='mfj' or spouse['valid_ssn'])):block('Tips/overtime recipient SSN must be valid; per-recipient invalid-SSN allocation is not implemented.')
    threshold=300000 if status=='mfj' else 150000
    reduction=int((D(max(0,agi-threshold))/D(1000)).to_integral_value(rounding=ROUND_FLOOR))*100
    tip_ded=max(0,min(tips,25000)-reduction) if tips and status!='mfs' else 0
    overtime_ded=max(0,min(overtime,25000 if status=='mfj' else 12500)-reduction) if overtime and status!='mfs' else 0
    car_reduction=int((D(max(0,agi-(200000 if status=='mfj' else 100000)))/D(1000)).to_integral_value(rounding=ROUND_CEILING))*200
    car_ded=max(0,min(car,10000)-car_reduction) if car else 0
    senior_each=max(0,6000-dollars(D(max(0,agi-(150000 if status=='mfj' else 75000)))*D('.06')))
    senior_ded=senior_count*senior_each
    lines['13b']=tip_ded+overtime_ded+car_ded+senior_ded
    schedules['schedule_1a']={'magi':agi,'qualified_tips_deduction':tip_ded,'qualified_overtime_deduction':overtime_ded,'car_interest_deduction':car_ded,'senior_deduction':senior_ded,'senior_each':senior_each,'total':lines['13b']}
    log('Schedule1A additional deductions',lines['13b'],'f1040s1a')
    before_qbi=max(0,agi-lines['12e']-lines['13b']);preferred=lines['3a']+preferred_gain
    qbi=sum(profits.values())-half_se-health+rental['qbi']
    qbi_threshold=394600 if status=='mfj' else 197300
    if (data['businesses'] or any(row['qbi_eligible'] for row in data['rentals'])) and before_qbi>qbi_threshold:block('Taxable income before QBI exceeds Form8995 simplified threshold; Form8995A wage/property/SSTB limitations are not implemented.')
    qbi_ded=min(dollars(D(max(0,qbi))*D('.20')),dollars(D(max(0,before_qbi-preferred))*D('.20'))) if (data['businesses'] or any(row['qbi_eligible'] for row in data['rentals'])) and before_qbi<=qbi_threshold else 0
    lines['13a']=qbi_ded;schedules['form_8995']={'qbi':qbi,'taxable_before_qbi':before_qbi,'net_capital_gain_plus_qualified_dividends':preferred,'income_limit':dollars(D(max(0,before_qbi-preferred))*D('.20')),'deduction':qbi_ded,'current_qbi_loss_for_future_review':max(0,-qbi)}
    lines['14']=lines['12e']+lines['13a']+lines['13b'];lines['15']=max(0,agi-lines['14'])
    lines['16'],qualified_worksheet=qualified_tax(lines['15'],preferred,status)
    if special_requested and not data['capital_gains'] and not has('carryovers','capital_short') and not has('carryovers','capital_long'):
        lines['16'],special_worksheet=tax_special_capital.tax(lines['15'],lines['3a'],total('dividends','capital_gain_distributions')+child_election['parent_capital_gain'],special_28,special_1250,status,ordinary_tax)
        schedules['schedule_d_tax_worksheet']=special_worksheet
        schedules['schedule_d'].update(collectibles_28_gain=special_28,unrecaptured_1250_gain=special_1250,special_distribution_only=True)
    if 'schedule_d_tax_worksheet' not in schedules:schedules['qualified_dividends_capital_gain_worksheet']=qualified_worksheet
    else:qualified_worksheet={'ordinary_income':schedules['schedule_d_tax_worksheet']['ordinary_income']}
    lines['16']+=child_election['additional_tax']
    log('Form1040 line16 income tax',lines['16'],'i1040sd' if 'schedule_d_tax_worksheet' in schedules else 'i1040gi' if preferred else 'i1040tt')
    amt=extended_result('form_6251',tax_extended.alternative_minimum_tax(data['amt'],{'filing_status':status,'taxpayer_age':person['age'],'agi':agi,'total_deductions':lines['14'],'senior_deduction':senior_ded,'deduction_addback':salt if deduction_type=='itemized' else lines['12e'],'preferred_income':preferred,'regular_ordinary_income':qualified_worksheet['ordinary_income'],'regular_tax':lines['16'],'no_amt_preferences':elig['no_amt_preferences'],'special_distribution_worksheet':schedules.get('schedule_d_tax_worksheet')},RULES))
    lines['17']=amt['tax']
    marketplace_context=dict(common_credit_context,household_agi=agi,household_ss_nontaxable=lines['6a']-lines['6b'],household_tax_exempt_interest=lines['2a'],tax_family_size=(2 if status=='mfj' else 1)+len(data['dependents']),self_employed_health_insurance=health)
    marketplace_result=module_result('calculate_marketplace',data['marketplace'],marketplace_context);schedules['form_8962']=marketplace_result
    lines['17']+=marketplace_result.get('repayment',0)
    foreign_result=extended_result('form_1116',tax_longtail.calculate_foreign(data['foreign_credit'],{'filing_status':status,'interest':lines['2b'],'ordinary_dividends':lines['3b'],'qualified_dividends':lines['3a'],'regular_tax':lines['16']+marketplace_result.get('repayment',0),'amt_tax':amt['tax'],'preferred_income':preferred,'gross_income':lines['9'],'standard_deduction':lines['12e'],'adjustments':lines['10'],'taxable_before_senior':max(0,agi-lines['14']+senior_ded),'ordinary_standard_income_only':deduction_type=='standard' and not data['businesses'] and not data['rentals'] and not data['capital_gains'] and not lines['10'] and not lines['13a'] and not tips and not overtime and not car and not lines['7a']}))
    care_context.update(agi=agi,tax_liability_limit=max(0,lines['16']+lines['17']-foreign_result['nonrefundable_credit']))
    care_result=extended_result('form_2441',tax_additional.calculate_care(data['care'],care_context))
    r_after_minimum=any(data['elderly_credit'][owner+'_after_minimum_retirement_age_confirmed'] for owner in ('taxpayer','spouse'))
    elderly_result=extended_result('schedule_r',tax_additional.calculate_elderly(data['elderly_credit'],dict(common_credit_context,agi=agi,ss_nontaxable=lines['6a']-lines['6b'],disability_income_available=disability_total+(n('retirement','pension_taxable') if r_after_minimum else 0),tax_liability_limit=max(0,lines['16']+lines['17']-foreign_result['nonrefundable_credit']-care_result['nonrefundable_credit']))))
    before_education=foreign_result['nonrefundable_credit']+care_result['nonrefundable_credit']+elderly_result['nonrefundable_credit']
    education_context=dict(common_credit_context,magi=agi,tax_liability_limit=max(0,lines['16']+lines['17']-before_education),taxpayer_can_be_claimed=person['can_be_claimed'],spouse_can_be_claimed=spouse['can_be_claimed'])
    education_result=module_result('calculate_education',data['education'],education_context);schedules['form_8863']=education_result
    before_saver=before_education+education_result.get('nonrefundable_credit',0)
    saver_context=dict(common_credit_context,agi=agi,taxpayer_can_be_claimed=person['can_be_claimed'],spouse_can_be_claimed=spouse['can_be_claimed'],ira_taxpayer=dollars(money(data['ira']['traditional_taxpayer'])+money(data['ira']['roth_taxpayer'])),ira_spouse=dollars(money(data['ira']['traditional_spouse'])+money(data['ira']['roth_spouse'])),ira_taxpayer_raw=str(money(data['ira']['traditional_taxpayer'])+money(data['ira']['roth_taxpayer'])),ira_spouse_raw=str(money(data['ira']['traditional_spouse'])+money(data['ira']['roth_spouse'])),known_2025_distributions=(lines['4a'] if retirement['ira_distribution_kind']=='fully_taxable' else 0)+n('retirement','pension_gross')+dollars(money(retirement['disability_taxpayer_gross'])+money(retirement['disability_spouse_gross'])),tax_liability_limit=max(0,lines['16']+lines['17']-before_saver))
    saver_result=extended_result('form_8880',tax_additional.calculate_saver(data['saver'],saver_context))
    saver_agi_limit=79000 if status=='mfj' else 59250 if status=='hoh' else 39500
    saver_possible=agi<=saver_agi_limit and saver_context['tax_liability_limit']>0 and any(saver_context['ira_'+owner]>0 and (person if owner=='taxpayer' else spouse)['age']>=18 and not (person if owner=='taxpayer' else spouse)['can_be_claimed'] and not data['saver'][owner+'_full_time_student'] for owner in (('taxpayer','spouse') if status=='mfj' else ('taxpayer',)))
    if saver_possible and not data['saver']['enabled']:block('ReportedIRA contributions may qualify for the Saver credit. Complete Form8880 actual contribution/distribution/eligibility inputs; do not silently omit an available credit.')
    lines['20']=before_saver+saver_result['nonrefundable_credit'];lines['29']=education_result.get('refundable_credit',0)
    ctc_children=0;other_dependents=0
    for index,dependent in enumerate(data['dependents']):
        require(dependent['eligibility_confirmed'],f'Dependent {index+1}: confirm residency/support/relationship/citizenship/claim/TIN tests; age alone does not establish a credit.')
        if dependent['qualifying_child'] and dependent['age']<17 and dependent['valid_ssn']:ctc_children+=1
        elif dependent['valid_tin']:other_dependents+=1
        else:block(f'Dependent {index+1}: no valid TIN by filing due date; other-dependent credit is unavailable.')
    parent_ctc_ssn=person['valid_ssn'] or (status=='mfj' and spouse['valid_ssn'])
    if not person['valid_tin'] or (status=='mfj' and not spouse['valid_tin']):
        block('Taxpayer/spouse valid taxpayer identification number by the filing due date is required.')
        parent_ctc_ssn=False
    gross_credit=ctc_children*2200+other_dependents*500
    if ctc_children and not parent_ctc_ssn:
        block('CTC/ACTC taxpayer SSN requirements not satisfied; invalid-child/taxpayer TIN allocation requires review.');gross_credit=other_dependents*500
    credit_phase=200000 if status!='mfj' else 400000
    phaseout=int((D(max(0,agi-credit_phase))/D(1000)).to_integral_value(rounding=ROUND_CEILING))*50
    available=max(0,gross_credit-phaseout);lines['18']=lines['16']+lines['17'];lines['19']=min(available,max(0,lines['18']-lines['20']))
    # The improvementcredit precedesCTC; adoption/cleanenergy use8812WorksheetB
    # to reserve only the CTCportion that cannot be refunded asACTC.
    energy_context={'improvement_tax_liability_limit':max(0,lines['18']-lines['20']),'clean_tax_liability_limit':0}
    preliminary_energy=tax_longtail.calculate_energy(data['energy'],energy_context)
    lines['20']+=preliminary_energy['improvement_credit']
    reservation=min(available,max(0,lines['18']-lines['20']))
    if ctc_children and (data['adoption']['enabled'] or data['energy']['enabled'] and preliminary_energy['form_lines'].get('13',0)):
        b_earned=max(0,lines['1a']+care_taxable+disability_total+sum(profits.values())-half_se)
        b_eic=tax_extended.earned_income_credit(data['eitc'],{'filing_status':status,'taxpayer':person,'spouse':spouse,'dependents':data['dependents'],'earned_income':b_earned,'agi':agi,'investment_income':lines['2a']+lines['2b']+lines['3b']+max(0,net)+child_election['eitc_other_investment_income']+max(0,rental['income'])},RULES)['credit']
        b_excess=0
        for owner in ('taxpayer','spouse'):
            records=[row for row in data['w2'] if row['owner']==owner];employers={row['employer'].strip().lower() for row in records}
            if len(employers)>=2 and '' not in employers:b_excess+=max(D(0),sum((money(row['social_security_withholding']) for row in records),D(0))-D('10918.20'))
        b_med_wages=total('w2','medicare_wages');b_med_threshold=250000 if status=='mfj' else 125000 if status=='mfs' else 200000
        b_additional_wage=dollars(D(max(0,b_med_wages-b_med_threshold))*D('.009'));b_additional_withheld=max(0,total('w2','medicare_withholding')-dollars(D(b_med_wages)*D('.0145')))
        b_additional_se=dollars(D(max(0,sum(row['line_4a_net_earnings'] for row in schedule_se.values())-max(0,b_med_threshold-b_med_wages)))*D('.009'))
        b_payroll=total('w2','social_security_withholding')+total('w2','medicare_withholding')+b_additional_wage-b_additional_withheld+dollars(D(b_additional_se)*D('.5'))
        b_alt=max(0,b_payroll+half_se-dollars(b_excess)-b_eic) if ctc_children>=3 else 0
        b_potential=min(ctc_children*1700,max(dollars(D(max(0,b_earned-2500))*D('.15')),b_alt));reservation=max(0,available-b_potential)
        schedules['schedule_8812_credit_limit_b']={'1':available,'2':ctc_children*1700,'3':b_earned,'5':dollars(D(max(0,b_earned-2500))*D('.15')),'11':b_alt,'12':max(dollars(D(max(0,b_earned-2500))*D('.15')),b_alt),'13':b_potential,'14':reservation}
    adoption_result=extended_result('form_8839',tax_longtail.calculate_adoption(data['adoption'],{'filing_status':status,'agi':agi,'tax_liability_limit':max(0,lines['18']-lines['20']-reservation)}))
    lines['20']+=adoption_result['nonrefundable_credit'];lines['30']=adoption_result['refundable_credit']
    energy_context['clean_tax_liability_limit']=max(0,lines['18']-lines['20']-reservation)
    energy_result=extended_result('form_5695',tax_longtail.calculate_energy(data['energy'],energy_context));lines['20']+=energy_result['clean_credit']
    if 'schedule_8812_credit_limit_b' in schedules:schedules['schedule_8812_credit_limit_b']['15']=adoption_result['nonrefundable_credit']+energy_result['clean_credit']
    lines['19']=min(available,max(0,lines['18']-lines['20']))
    lines['21']=lines['19']+lines['20'];lines['22']=max(0,lines['18']-lines['21'])
    earned_income=max(0,lines['1a']+care_taxable+disability_total+sum(profits.values())-half_se)
    actc_limit=min(max(0,available-lines['19']),ctc_children*1700)
    actc_earned=dollars(D(max(0,earned_income-2500))*D('.15'))
    payroll_withheld=total('w2','social_security_withholding')+total('w2','medicare_withholding')
    actc_alternative=max(0,payroll_withheld+half_se) if ctc_children>=3 else 0
    lines['28']=min(actc_limit,max(actc_earned,actc_alternative)) if parent_ctc_ssn else 0
    schedules['schedule_8812']={'qualifying_children':ctc_children,'other_dependents':other_dependents,'credit_before_phaseout':gross_credit,'phaseout':phaseout,'credit_after_phaseout':available,'nonrefundable_credit':lines['19'],'earned_income':earned_income,'actc_earned_income_amount':actc_earned,'actc_three_child_alternative':actc_alternative,'actc':lines['28']}
    schedules['schedule_8812'].update(credit_limit_worksheet_amount=max(0,lines['18']-lines['20']),credit_limit_worksheet_type='B' if 'schedule_8812_credit_limit_b' in schedules else 'A')
    log('CTC and other-dependent credit',lines['19'],'f1040s8');log('Additional child tax credit',lines['28'],'f1040s8')
    # Require review of plausible EITC eligibility instead of silently omitting
    # a credit when the EITC module has not been completed.
    nchild=sum(1 for child in data['dependents'] if child['qualifying_child'])
    eitc_limits=([19104,50434,57310,61555] if status!='mfj' else [26214,57554,64430,68675])
    investment=lines['2a']+lines['2b']+lines['3b']+max(0,net)+child_election['eitc_other_investment_income']
    age_eligible=nchild>0 or (25<=person['age']<65) or (status=='mfj' and 25<=spouse['age']<65)
    eitc_possible=0<earned_income<eitc_limits[min(nchild,3)] and age_eligible and not person['can_be_claimed'] and not(status=='mfj' and spouse['can_be_claimed']) and agi<eitc_limits[min(nchild,3)] and investment<=11950
    eic_investment=investment+max(0,rental['income'])
    eic=extended_result('schedule_eic',tax_extended.earned_income_credit(data['eitc'],{'filing_status':status,'taxpayer':person,'spouse':spouse,'dependents':data['dependents'],'earned_income':earned_income,'agi':agi,'investment_income':eic_investment},RULES))
    lines['27a']=eic['credit']
    if eitc_possible and not data['eitc']['claim'] and not elig['eitc_not_applicable']:block('Possible EITC eligibility detected. Complete the EITC module or confirm reviewed ineligibility; do not silently omit an available credit.')
    if person['age']<24 and lines['2b']+lines['3b']+max(0,net)>2700:block('Possible kiddie-tax/Form8615 situation; parental income and support/student tests are not implemented.')
    qualified_seniors=int(person['age']>=65)+(int(spouse['age']>=65) if status=='mfj' else 0)
    r_agi_limit=(25000 if qualified_seniors==2 else 20000) if status=='mfj' else (12500 if status=='mfs' else 17500)
    r_base=(7500 if qualified_seniors==2 else 5000) if status=='mfj' else (3750 if status=='mfs' else 5000)
    if qualified_seniors and not data['elderly_credit']['enabled'] and not(status=='mfs' and elig['mfs_lived_with_spouse']) and agi<r_agi_limit and lines['6a']-lines['6b']<r_base:
        block('Potential elderly ScheduleR credit requires completing the elderly-credit module and benefit qualifications.')
    # Additional Medicare: ordinary wages and ScheduleSE, no railroad/unreported
    # tips/deferred compensation. Threshold is for the household, not each W2.
    med_wages=total('w2','medicare_wages');med_threshold=250000 if status=='mfj' else (125000 if status=='mfs' else 200000)
    se_earnings=sum(row['line_4a_net_earnings'] for row in schedule_se.values())
    add_med=dollars(D(max(0,med_wages-med_threshold))*D('.009'))+dollars(D(max(0,se_earnings-max(0,med_threshold-med_wages)))*D('.009'))
    add_med_withheld=max(0,total('w2','medicare_withholding')-dollars(D(med_wages)*D('.0145')))
    if med_wages>200000:
        require(all(money(row['medicare_withholding'])>0 for row in data['w2'] if money(row['medicare_wages'])>200000),'Form8959 requires actual W2 box6 Medicare withholding, not a missing/default amount.')
    if add_med or add_med_withheld:schedules['form_8959']={'medicare_wages':med_wages,'se_earnings':se_earnings,'threshold':med_threshold,'tax':add_med,'additional_medicare_withheld':add_med_withheld}
    niit=extended_result('form_8960',tax_extended.net_investment_tax(data['niit'],{'filing_status':status,'agi':agi,'interest':lines['2b'],'ordinary_dividends':lines['3b'],'annuity':n('retirement','annuity_taxable'),'rental_income':rental['niit_income'],'other_investment_income':child_election['niit_other_investment_income'],'capital_gain_loss':lines['7a'],'itemized_salt':salt if deduction_type=='itemized' else 0,'deducted_investment_interest':investment_interest_ded if deduction_type=='itemized' else 0,'rental_prior_loss_unverified':any(row['prior_loss'] and not row['niit_carryover_eligible'] for row in rental['properties'])}))
    lines['23']=se_total+add_med+niit['tax']+hsa_tax;lines['24']=lines['22']+lines['23'];lines['25a']=total('w2','federal_withholding')
    lines['25b']=dollars(sum((money(row['federal_withholding']) for row in data['interest']+data['dividends']),D('0'))+money(retirement['federal_withholding'])+money(data['other_income']['federal_withholding']))
    lines['25c']=add_med_withheld;lines['25d']=lines['25a']+lines['25b']+lines['25c']
    excess_ss=D('0')
    for owner in ('taxpayer','spouse'):
        owner_w2=[row for row in data['w2'] if row['owner']==owner]
        held=sum((money(row['social_security_withholding']) for row in owner_w2),D('0'))
        excess=max(D('0'),held-D('10918.20'))
        distinct_employers={row['employer'].strip().lower() for row in owner_w2}
        if excess and (len(distinct_employers)<2 or '' in distinct_employers):block('One/undocumented employer over-withheld SocialSecurity; obtain employer refund/corrected W2 instead of claiming multiple-employer excessSS credit.')
        elif excess:excess_ss+=excess
    lines['31']=dollars(excess_ss)+marketplace_result.get('refundable_credit',0)
    if ctc_children>=3:
        actc_alternative=max(0,payroll_withheld+half_se-dollars(excess_ss)-lines['27a'])
        lines['28']=min(actc_limit,max(actc_earned,actc_alternative)) if parent_ctc_ssn else 0
        schedules['schedule_8812']['actc_three_child_alternative']=actc_alternative
        schedules['schedule_8812']['actc']=lines['28']
        for record in trace:
            if record['label']=='Additional child tax credit':record['amount']=lines['28']
    lines['26']=dollars(money(data['payments']['estimated'])+money(data['payments']['prior_year_credit']))
    lines['32']=lines['27a']+lines['28']+lines['29']+lines['30']+lines['31'];lines['33']=lines['25d']+lines['26']+lines['32']
    lines['34']=max(0,lines['33']-lines['24']);lines['35a']=lines['34'];lines['37']=max(0,lines['24']-lines['33'])
    hsa_distribution_tax=sum(row.get('line17b_additional_tax',0) for row in hsa_result.get('form_lines',{}).values() if isinstance(row,dict))
    additional_2210=se_total+add_med+niit['tax']+hsa_distribution_tax
    penalty_result=extended_result('form_2210',tax_longtail.calculate_penalty(data['estimated_penalty'],{'filing_status':status,'income_tax_after_credits':lines['22'],'additional_tax_for_2210':additional_2210,'tax_for_2210':lines['22']+additional_2210,'refundable_credits':lines['27a']+lines['28']+lines['29']+lines['30']+marketplace_result.get('refundable_credit',0),'withholding':lines['25d'],'excess_ss':dollars(excess_ss),'estimated':n('payments','estimated'),'prior_year_credit':n('payments','prior_year_credit')}))
    if penalty_result['computed']:lines['38']=penalty_result['penalty']
    if lines['37']>=1000 and not penalty_result['computed']:warnings.append('An amount owed of1000 or more may require Form2210 estimated-tax penalty review. Complete actualdatedpayments andsafeharborfacts; line38 is notcomputed.')
    schedules['schedule_d']['carryout_worksheet']=tax_longtail.capital_carryout(short,long,max(0,-lines['7a']),agi-lines['14'])
    warnings.append('IRS age is as of December31,2025; a January1 birthday reaches the relevant age on December31. User ages must reflect that rule.')
    if blocks:warnings.append('Blocking issues remain. Displayed amounts cover only implemented worksheets; they are not a completed return and must not be submitted as final tax liability/refund.')
    forms=['Form1040']
    if lines['8'] or lines['10']:forms.append('Schedule1')
    if lines['13b']:forms.append('Schedule1A')
    if deduction_type=='itemized':forms.append('ScheduleA')
    if lines['2b']>1500 or lines['3b']>1500 or child_election['parent_qualified_dividends']:forms.append('ScheduleB')
    if data['capital_gains'] or net:forms.append('ScheduleD/Form8949 worksheet')
    if data['businesses']:forms+=['ScheduleC','ScheduleSE','Form8995']
    if data['dependents']:forms.append('Schedule8812')
    if lines['23']:forms.append('Schedule2')
    if add_med or add_med_withheld:forms.append('Form8959')
    if lines['31'] or lines['20']:forms.append('Schedule3')
    if data['rentals']:forms+=['ScheduleE','Form8582']
    if data['child_income_election']['enabled']:forms.append('Form8814')
    if data['eitc']['claim'] and any(row['eitc_qualifying_child'] for row in data['dependents']):forms.append('ScheduleEIC')
    if special_requested or amt['tax'] or any(money(data['amt'][key],signed=key in ('other_adjustments','capital_gain_adjustment')) for key in ('iso_adjustment','private_activity_bond_interest','other_adjustments','capital_gain_adjustment')):forms.append('Form6251')
    if niit['tax']:forms.append('Form8960')
    if n('itemized','investment_interest') or has('niit','investment_interest_carryover'):forms.append('Form4952')
    if data['ira']['enabled'] and any(row.get('nondeductible',0) or row.get('form8606_line2',0) for row in ira_result.get('form_lines',{}).values()):forms.append('Form8606 contribution worksheet')
    if data['hsa']['enabled']:forms.append('Form8889')
    if any(row.get('excess_contributions',0) for row in hsa_result.get('form_lines',{}).values()):forms.append('Form5329 current HSA excess worksheet')
    if data['education']['enabled']:forms.append('Form8863')
    if data['marketplace']['enabled']:forms.append('Form8962')
    if data['care']['enabled'] or sum(care_benefits.values()):forms.append('Form2441')
    if data['saver']['enabled']:forms.append('Form8880')
    if data['elderly_credit']['enabled']:forms.append('ScheduleR')
    if data['adoption']['enabled']:forms.append('Form8839')
    if data['energy']['enabled']:forms.append('Form5695')
    if data['foreign_credit']['enabled'] and data['foreign_credit']['method']=='ordinary_passive_1116':forms.append('Form1116')
    if data['estimated_penalty']['enabled']:forms.append('Form2210')
    return {'tax_year':2025,'currency':'USD','filing_status':status,'name':data['name'],'lines':lines,
            'identity':deepcopy(data['identity']),
            'filing_details':deepcopy(data['filing_details']),
            'additional_lines':{'1e':care_taxable,'1h':disability_total,'1z':lines['1a']+care_taxable+disability_total},
            'form_readiness':form_readiness(data),
            'summary':{'agi':agi,'taxable_income':lines['15'],'total_tax':lines['24'],'payments':lines['33'],'refund':lines['35a'],'amount_owed':lines['37'],'deduction_type':deduction_type,'effective_rate':str((D(lines['24'])/D(agi)*100).quantize(D('.01'),rounding=ROUND_HALF_UP)) if agi>0 else '0.00','schedules':forms},
            'schedules':schedules,'trace':trace,'warnings':warnings,'blocking_issues':blocks,'can_prepare':not blocks,
            'not_computed_lines':[] if penalty_result['computed'] else ['38'],
            'payment_summary':{'tax_before_penalty':lines['24'],'estimated_tax_penalty':lines['38'],'balance_including_penalty':max(0,lines['24']+lines['38']-lines['33']),'refund_after_penalty_if_offset':max(0,lines['33']-lines['24']-lines['38']),'separate_1040_line38':True},
            'scope':'2025 supported federal calculation worksheets, not an e-file or signed IRS return','sources':deepcopy(RULES['sources']),
            'additional_calculation_sources':dict(deepcopy(tax_credits.capabilities()['sources']),**{key:{'url':url,'tax_year':2025} for key,url in tax_longtail.SOURCES.items()})}


def demo_returns():
    result=[]
    def base(name,status='single',ages=(35,35)):
        data=default_return();data['name']=name;data['filing_status']=status;data['taxpayer']['age']=ages[0];data['spouse']['age']=ages[1]
        for field in ('full_year_us_resident','filing_status_confirmed','all_income_reported','no_amt_preferences'):data['eligibility'][field]=True
        return data
    wage=base('Synthetic single W2 household')
    wage['w2']=[dict(ROW_DEFAULTS['w2'],employer='Example employer',wages='60000',social_security_wages='60000',medicare_wages='60000',social_security_withholding='3720',medicare_withholding='870',federal_withholding='6500')]
    wage['interest']=[dict(ROW_DEFAULTS['interest'],payer='Example bank',taxable='100')];result.append(wage)
    family=base('Synthetic MFJ two-child household','mfj')
    family['w2']=[dict(ROW_DEFAULTS['w2'],employer='Example employer',wages='100000',social_security_wages='100000',medicare_wages='100000',social_security_withholding='6200',medicare_withholding='1450',federal_withholding='10000')]
    family['dependents']=[dict(ROW_DEFAULTS['dependents'],name='Synthetic childA',age=8,eligibility_confirmed=True),dict(ROW_DEFAULTS['dependents'],name='Synthetic childB',age=12,eligibility_confirmed=True)];result.append(family)
    business=base('Synthetic sole proprietor')
    business['businesses']=[dict(ROW_DEFAULTS['businesses'],name='Example consulting',revenue='65000',expenses='15000',active_business=True,expenses_eligible=True,at_risk_confirmed=True,qbi_eligible=True)]
    business['payments']['estimated']='10000';result.append(business)
    senior=base('Synthetic senior pension household',ages=(70,70));senior['retirement'].update(pension_gross='30000',pension_taxable='30000',social_security='24000',taxable_amounts_confirmed=True,qualified_plan_confirmed=True,federal_withholding='3000');senior['schedule_1a']['eligibility_confirmed']=True;result.append(senior)
    gain=base('Synthetic securities household');gain['w2']=[dict(ROW_DEFAULTS['w2'],employer='Example employer',wages='70000',social_security_wages='70000',medicare_wages='70000',social_security_withholding='4340',medicare_withholding='1015',federal_withholding='8000')]
    gain['dividends']=[dict(ROW_DEFAULTS['dividends'],payer='Example broker',ordinary='2000',qualified='1500')];gain['capital_gains']=[dict(ROW_DEFAULTS['capital_gains'],description='Ordinary stock long-term sale',proceeds='15000',cost_basis='10000')];gain['eligibility']['capital_gains_eligible']=True;gain['eligibility']['qualified_dividends_eligible']=True;result.append(gain)
    for filing_status,name in (('hoh','Synthetic eligible head-of-household'),('qss','Synthetic eligible surviving spouse'),('mfs','Synthetic married separate household')):
        example=base(name,filing_status)
        example['w2']=[dict(ROW_DEFAULTS['w2'],employer='Example employer',wages='90000',social_security_wages='90000',medicare_wages='90000',social_security_withholding='5580',medicare_withholding='1305',federal_withholding='10000')]
        if filing_status in ('hoh','qss'):
            example['eligibility'][filing_status+'_eligible']=True
            example['dependents']=[dict(ROW_DEFAULTS['dependents'],name='Synthetic qualifying child',age=8,eligibility_confirmed=True)]
        result.append(example)
    distribution=base('Synthetic 1099-DIV special distributions')
    distribution['eligibility'].update(capital_gains_eligible=True,qualified_dividends_eligible=True,eitc_not_applicable=True)
    distribution['niit']['eligibility_confirmed']=True
    distribution['amt']['special_distribution_same_basis_confirmed']=True
    distribution['w2']=[dict(ROW_DEFAULTS['w2'],employer='Synthetic W2 payer',wages='85750',federal_withholding='30000',social_security_wages='85750',social_security_withholding='5316.50',medicare_wages='85750',medicare_withholding='1243.38')]
    distribution['dividends']=[dict(ROW_DEFAULTS['dividends'],payer='Synthetic payer 1',ordinary='5000',qualified='5000',capital_gain_distributions='25000',unrecaptured_1250_gain='10000',collectibles_gain='10000',special_distribution_confirmed=True)]
    distribution['identity'].update(first_name='Synthetic',last_name='Taxpayer',ssn='123456789',address='100 Example Street',city='Example City',state='IL',zip='60000',phone='5550100100',occupation='Accountant')
    distribution['filing_details'].update(digital_asset_answer='no',main_home_us_answer='yes')
    distribution['filing_details']['official_form_facts']['schedule_b'].update(foreign_account_answer='no',fbar_required_answer='no',foreign_trust_answer='no',facts_confirmed=True)
    distribution['notes']='Synthetic example only. Source1099-DIV2a includes2b/2d. Not an actual taxpayer return.'
    result.append(distribution)
    special_amt=deepcopy(distribution)
    special_amt['name']='Synthetic 1099-DIV special AMT'
    special_amt['eligibility']['no_amt_preferences']=False
    special_amt['w2']=[dict(ROW_DEFAULTS['w2'],employer='Synthetic W2 payer',wages='50750',federal_withholding='30000',social_security_wages='50750',social_security_withholding='3146.50',medicare_wages='50750',medicare_withholding='735.88')]
    special_amt['dividends']=[dict(ROW_DEFAULTS['dividends'],payer='Synthetic 1099-DIV payer',ordinary='5000',qualified='5000',capital_gain_distributions='10000',unrecaptured_1250_gain='10000',special_distribution_confirmed=True)]
    special_amt['amt'].update(iso_adjustment='100000',eligibility_confirmed=True,special_distribution_same_basis_confirmed=True)
    special_amt['notes']='Synthetic IRS2025-AMT-special-005 only. Includes a confirmed100000USD ISO adjustment with unchanged capital basis; not an actual taxpayer return.'
    result.append(special_amt)
    child=base('Synthetic parent and child income')
    child['eligibility']['eitc_not_applicable']=True
    child['niit']['eligibility_confirmed']=True
    child['w2']=[dict(ROW_DEFAULTS['w2'],employer='Synthetic W2 payer',wages='200000',federal_withholding='50000',social_security_wages='176100',social_security_withholding='10918.20',medicare_wages='200000',medicare_withholding='2900')]
    elected=tax_child_income.row_templates()['child_income_election.children']
    elected.update(name='Synthetic Child',ssn='111111111',birth_date='2015-07-01',taxable_interest='2000',ordinary_dividends='1000',qualified_dividends='600',capital_gain_distributions='1000',qualified_eligibility_confirmed=True,ordinary_capital_distribution_confirmed=True)
    for fact in tax_child_income.CONFIRMATIONS:elected[fact]=True
    child['child_income_election']={'enabled':True,'children':[elected]}
    child['identity'].update(first_name='Synthetic',last_name='Parent',ssn='123456789',address='100 Example Street',city='Example City',state='IL',zip='60000',phone='5550100100',occupation='Accountant')
    child['filing_details'].update(digital_asset_answer='no',main_home_us_answer='yes')
    child['filing_details']['official_form_facts']['schedule_b'].update(foreign_account_answer='no',fbar_required_answer='no',foreign_trust_answer='no',facts_confirmed=True)
    child['notes']='Synthetic IRS TY2025 Form 8814 election only. Child full income is 4000 USD; parent allocated income is 1300 USD and additional child tax is 135 USD. Not an actual taxpayer return.'
    result.append(child)
    return [{'id':'synthetic-'+str(index+1),'name':data['name'],'data':data} for index,data in enumerate(result)]
