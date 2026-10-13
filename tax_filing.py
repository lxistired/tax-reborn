"""TY2025 paper-filing facts, separate from tax arithmetic and transmission."""
from __future__ import annotations
from copy import deepcopy
from datetime import date
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
            'signature_date':'', 'hoh_qss_non_dependent_child_name':'', 'official_form_facts':{}}

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
