"""TY2025 paper-filing facts, separate from tax arithmetic and transmission."""
from __future__ import annotations
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
import math
from pathlib import Path
import re
import sys

BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
DEPENDENT_FIELDS = {'form_first_name':'', 'form_last_name':'', 'form_ssn':'',
                    'relationship':'', 'us_home_more_than_half_year':False,
                    'lived_with_taxpayer_more_than_half_year':False, 'permanently_disabled':False}
DEFAULTS = {'digital_asset_answer':'unanswered', 'main_home_us_answer':'unanswered',
            'refund_delivery':'check', 'bank_routing':'', 'bank_account':'', 'bank_type':'unanswered',
            'designee_yes':False, 'designee_name':'', 'designee_phone':'', 'designee_pin':'',
            'presidential_taxpayer':False, 'presidential_spouse':False,
            'signature_date':'', 'hoh_qss_non_dependent_child_name':'',
            'balance_due_payment_method':'unanswered', 'paper_payment_amount_source':'balance_due',
            'paper_payment_amount':'', 'paper_payment_confirmed':False,
            'mailing_address_type':'domestic', 'official_form_facts':{}}

def fact_schema():
    path = BASE / 'forms' / 'paper-fact-schema-2025.json'
    if not path.is_file():
        return {'defaults':{'other_income_description':''}, 'row_templates':{}, 'ui_fields':{}}
    raw=json.loads(path.read_text())
    return {'defaults':raw.get('FORM_FACT_DEFAULTS',raw.get('defaults',{})),
            'row_templates':raw.get('FORM_FACT_ROW_TEMPLATES',raw.get('row_templates',{})),
            'ui_fields':raw.get('FORM_FACT_UI_FIELDS',raw.get('ui_fields',{}))}

def default_inputs():
    values = deepcopy(DEFAULTS)
    values['official_form_facts'] = deepcopy(fact_schema()['defaults'])
    return {'filing_details':values}

def field_metadata():
    choices = [['unanswered','Choose an answer'],['yes','Yes'],['no','No']]
    meta = {
        'filing_details.digital_asset_answer':{'type':'enum','label':'Digital asset question for Form1040','options':choices,'help':'Answer the IRS receipt/disposal question even if no tax is due.'},
        'filing_details.main_home_us_answer':{'type':'enum','label':'Main home in the US for more than half of 2025','options':choices,'help':'For a joint return, this statement covers both spouses. Residency eligibility and this form question are separate.'},
        'filing_details.refund_delivery':{'type':'enum','label':'Refund delivery','options':[['check','Paper check'],['direct_deposit','Direct deposit']]},
        'filing_details.bank_type':{'type':'enum','label':'Bank account type','options':[['unanswered','Choose an account type'],['checking','Checking'],['savings','Savings']]},
        'filing_details.bank_routing':{'type':'text','label':'Nine-digit routing number'},
        'filing_details.bank_account':{'type':'text','label':'Refund account number','help':'Form1040 allows at most17 account characters. This application prepares the form; it does not initiate a transfer.'},
        'filing_details.designee_yes':{'type':'boolean','label':'Allow a named third party to discuss this return with the IRS'},
        'filing_details.designee_name':{'type':'text','label':'Third-party designee name'},
        'filing_details.designee_phone':{'type':'text','label':'Designee phone number'},
        'filing_details.designee_pin':{'type':'text','label':'Designee five-digit PIN'},
        'filing_details.presidential_taxpayer':{'type':'boolean','label':'Taxpayer elects the $3 Presidential Election Campaign designation'},
        'filing_details.presidential_spouse':{'type':'boolean','label':'Spouse elects the $3 Presidential Election Campaign designation'},
        'filing_details.signature_date':{'type':'text','label':'Planned signing date','help':'YYYY-MM-DD. Print the completed draft and sign it yourself; the app does not sign on your behalf.'},
        'filing_details.hoh_qss_non_dependent_child_name':{'type':'text','label':'HOH/QSS qualifying child who is not a listed dependent'},
        'filing_details.balance_due_payment_method':{'type':'enum','label':'Balance-due payment method','options':[['unanswered','Choose a payment method'],['check_money_order','Check or money order'],['electronic','Electronic payment arranged separately']],'help':'Form1040-V accompanies a check or money order. Electronic payments use separate IRS payment options.'},
        'filing_details.paper_payment_amount_source':{'type':'enum','label':'Paper voucher amount','options':[['balance_due','Form1040 line37 amount owed'],['custom','Enter the amount of this check or money order']],'help':'Line37 excludes any separate line38 estimated-tax penalty. Enter a custom amount if your check or money order differs.'},
        'filing_details.paper_payment_amount':{'type':'money','label':'Entered check or money-order amount','help':'USD, up to two decimal places. Used only for a custom paper amount; a single check must be less than100million dollars.'},
        'filing_details.paper_payment_confirmed':{'type':'boolean','label':'I verified the paper payment amount and method','help':'Confirm the amount you will actually send with this voucher. Preparing the voucher is separate from making the payment.'},
        'filing_details.mailing_address_type':{'type':'enum','label':'Mailing address format','options':[['domestic','US mailing address'],['foreign','Foreign mailing address']],'help':'Use your current mailing address. Tax eligibility comes from the household and income interviews.'},
        'identity.city':{'type':'text','label':'City or town','help':'For a foreign address, enter the city only; put province and postal code in their separate fields.'},
        'identity.state':{'type':'text','label':'US state','help':'Printed for a US mailing address. Your entered value is retained when you select a foreign address.'},
        'identity.zip':{'type':'text','label':'US ZIP code','help':'Printed for a US mailing address.'},
        'identity.foreign_country':{'type':'text','label':'Foreign country name','help':'For a foreign mailing address, enter the full country name.'},
        'identity.foreign_province':{'type':'text','label':'Foreign province, state or county','help':'Complete when applicable to your foreign address.'},
        'identity.foreign_postal_code':{'type':'text','label':'Foreign postal code','help':'Complete when applicable to your foreign address; letters and digits are retained.'},
        'dependents.*.form_first_name':{'type':'text','label':'Dependent legal first name'},
        'dependents.*.form_last_name':{'type':'text','label':'Dependent legal last name'},
        'dependents.*.form_ssn':{'type':'text','label':'Dependent SSN or ITIN'},
        'dependents.*.relationship':{'type':'text','label':'Relationship to taxpayer'},
        'dependents.*.us_home_more_than_half_year':{'type':'boolean','label':'Dependent lived with taxpayer in the US for more than half of 2025'},
        'dependents.*.lived_with_taxpayer_more_than_half_year':{'type':'boolean','label':'Dependent lived with taxpayer for more than half of 2025'},
        'dependents.*.permanently_disabled':{'type':'boolean','label':'Dependent permanently and totally disabled'},
    }
    meta.update(fact_schema().get('ui_fields',{}))
    return meta

def validate_facts(data):
    values = data['filing_details']
    for key, default in DEFAULTS.items():
        value = values[key]
        if isinstance(default, bool):
            if type(value) is not bool: raise ValueError('filing_details.'+key+' must be true or false')
        elif key != 'official_form_facts':
            if not isinstance(value,str) or len(value)>200: raise ValueError('filing_details.'+key+' must be text of at most200 characters')
            values[key]=''.join(' ' if ord(c)<32 or ord(c)==127 else c for c in value).strip()
    for key in ('digital_asset_answer','main_home_us_answer'):
        if values[key] not in ('unanswered','yes','no'):raise ValueError(key+' must be unanswered, yes or no')
    if values['refund_delivery'] not in ('check','direct_deposit'):raise ValueError('Invalid refund delivery')
    if values['bank_type'] not in ('unanswered','checking','savings'):raise ValueError('Invalid refund account type')
    if values['balance_due_payment_method'] not in ('unanswered','check_money_order','electronic'):raise ValueError('Invalid balance-due payment method')
    if values['paper_payment_amount_source'] not in ('balance_due','custom'):raise ValueError('Invalid paper payment amount source')
    if values['mailing_address_type'] not in ('domestic','foreign'):raise ValueError('Invalid mailing address format')
    if values['paper_payment_amount']:
        payment_decimal(values['paper_payment_amount'])
    if not re.fullmatch(r'\d{0,9}',values['bank_routing']):raise ValueError('Routing number contains only up to9digits')
    if not re.fullmatch(r'[A-Za-z0-9-]{0,17}',values['bank_account']):raise ValueError('Account number contains at most17letters, digits or hyphens')
    if not re.fullmatch(r'\d{0,5}',values['designee_pin']):raise ValueError('Designee PIN contains only up to5digits')
    # Draft facts may be unfinished. Format errors fail validation; absent facts
    # belong in the packet checklist and do not erase an otherwise valid tax calculation.
    count=0
    def walk(node,depth=0):
        nonlocal count
        count+=1
        if count>3000 or depth>12:raise ValueError('Supporting form facts exceed the local document limit')
        if isinstance(node,dict):
            for k,v in node.items():
                if not isinstance(k,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',k) or k in ('__proto__','constructor','prototype'):raise ValueError('Invalid supporting form fact name')
                walk(v,depth+1)
        elif isinstance(node,list):
            if len(node)>500:raise ValueError('Too many supporting form rows')
            for child in node:walk(child,depth+1)
        elif isinstance(node,str):
            if len(node)>2000 or any(ord(c)<32 and c not in '\n\t' for c in node):raise ValueError('Invalid supporting form text')
        elif node is not None and not isinstance(node,(bool,int,float)):raise ValueError('Invalid supporting form value')
        elif isinstance(node,(int,float)) and not math.isfinite(node):raise ValueError('Supporting form numbers must be finite')
    walk(values['official_form_facts'])
    for row in data.get('dependents',[]):
        for key,default in DEPENDENT_FIELDS.items():
            value=row.get(key,default)
            if isinstance(default,str) and (not isinstance(value,str) or len(value)>200):raise ValueError('Dependent '+key+' must be short text')
            if key=='form_ssn' and not re.fullmatch(r'[0-9-]*',value):raise ValueError('Dependent SSN only permits digits or hyphens')
    return values


def payment_decimal(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{1,9}(?:\.\d{1,2})?',value):
        raise ValueError('Paper payment amount must be a nonnegative USD string with at most two decimal places')
    amount=Decimal(value)
    if amount>=100000000:raise ValueError('A single paper payment must be less than100million USD')
    return amount


def payment_voucher_plan(data,result):
    """Explicit TY2025 paper payment choice; never a payment transaction."""
    facts={**DEFAULTS,**data.get('filing_details',{})};method=facts['balance_due_payment_method']
    owed=result['lines'].get('37',0);missing=[];amount=None
    requested=method=='check_money_order' and owed>0
    if owed>0 and method=='unanswered':missing.append('Choose a balance-due payment method before completing paper preparation')
    if method=='check_money_order':
        if owed<=0:missing.append('Review paper payment selection: this return no longer has a balance due')
        elif facts['paper_payment_amount_source']=='balance_due':
            if owed>=100000000:missing.append('A single check or money order must be less than100million USD; enter an individual payment amount')
            else:amount=Decimal(owed)
        elif not facts['paper_payment_amount']:missing.append('Enter the amount of this check or money order')
        else:amount=payment_decimal(facts['paper_payment_amount'])
        if amount is not None and amount<=0:missing.append('Paper payment amount must be positive');amount=None
        if requested and not facts['paper_payment_confirmed']:missing.append('Confirm the paper payment amount and method')
    return {'requested':requested,'method':method,'amount_source':facts['paper_payment_amount_source'],
        'amount':format(amount,'.2f') if amount is not None else None,'form1040_line37':owed,
        'missing_facts':missing,'tax_year':2025,'currency':'USD','payment_initiated':False,
        'source':'https://www.irs.gov/pub/irs-prior/f1040v--2025.pdf'}


def mailing_address(data):
    """TY2025 printed address selection; retained inputs and tax facts are unchanged."""
    identity=deepcopy(data.get('identity',{}))
    facts=data.get('filing_details',{})
    mode=facts.get('mailing_address_type')
    if mode is None:mode='foreign' if identity.get('foreign_country','').strip() else 'domestic'
    if mode not in ('domestic','foreign'):raise ValueError('Invalid mailing address format')
    required=[('address','Street address'),('city','City')]
    missing=[]
    if mode=='foreign':
        identity.update(state='',zip='')
        required.append(('foreign_country','Foreign country name'))
        country=identity.get('foreign_country','').strip()
        if country and len(country)<=2:missing.append('Full foreign country name, rather than a country code')
    else:
        identity.update(foreign_country='',foreign_province='',foreign_postal_code='')
        required.extend([('state','State'),('zip','ZIP code')])
    missing.extend(label for key,label in required if not identity.get(key,'').strip())
    return {'mode':mode,'values':identity,'missing_facts':missing}

def routing_valid(number):
    return bool(re.fullmatch(r'\d{9}',number)) and number!='000000000' and sum(int(c)*w for c,w in zip(number,[3,7,1,3,7,1,3,7,1]))%10==0

def paper_facts_readiness(data):
    values=data.get('filing_details',default_inputs()['filing_details']);missing=[]
    for key,label in [('digital_asset_answer','Form1040 digital asset yes/no answer'),('main_home_us_answer','Form1040 main home in US yes/no answer')]:
        if values[key]=='unanswered':missing.append(label)
    if values['refund_delivery']=='direct_deposit':
        if not routing_valid(values['bank_routing']):missing.append('Valid nine-digit refund routing number')
        if not values['bank_account']:missing.append('Refund account number')
        if values['bank_type']=='unanswered':missing.append('Refund account type')
    if values['designee_yes']:
        if not values['designee_name']:missing.append('Third-party designee name')
        if not values['designee_phone']:missing.append('Third-party designee phone')
        if not re.fullmatch(r'\d{5}',values['designee_pin']):missing.append('Third-party designee five-digit PIN')
    if values['signature_date']:
        try:date.fromisoformat(values['signature_date'])
        except ValueError:missing.append('Valid signing date in YYYY-MM-DD format')
    identity=data.get('identity',{})
    for key,label in [('ssn','Taxpayer SSN/ITIN')]+([('spouse_ssn','Spouse SSN/ITIN')] if data.get('filing_status') in ('mfj','mfs') else []):
        if not re.fullmatch(r'\d{9}',str(identity.get(key,'')).replace('-','')):missing.append(label+' containing exactly nine digits')
    for i,row in enumerate(data.get('dependents',[])):
        for key,label in [('form_first_name','first name'),('form_last_name','last name'),('form_ssn','SSN/ITIN'),('relationship','relationship')]:
            if not row.get(key):missing.append('Dependent '+str(i+1)+' '+label)
        if row.get('form_ssn') and not re.fullmatch(r'\d{9}',row['form_ssn'].replace('-','')):missing.append('Dependent '+str(i+1)+' valid nine-digit SSN/ITIN')
    return {'missing_paper_facts':list(dict.fromkeys(missing)), 'paper_facts_present':not missing,
            'requires_taxpayer_signature':True, 'electronic_filing':False, 'transmitted':False}

def official_facts(data):
    """Preserve the form builder's explicit-answer/confirmation schema."""
    return deepcopy(data.get('filing_details',{}).get('official_form_facts',{}))
