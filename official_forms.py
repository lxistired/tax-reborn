"""Public IRS TY2025 supporting forms filled from actual Tax Reborn outputs.

This module never invents identity, dates, classifications or expense detail.
All missing filing facts are returned explicitly. No transmission/filing occurs.
Original IRS templates and their fixed field map are hash pinned in forms/.
"""
from __future__ import annotations
import hashlib
import io
import json
import re
import sys
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from datetime import date
from pathlib import Path
import tax_extended
import tax_filing
from pypdf import PdfReader, PdfWriter, PageObject
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject, TextStringObject, NumberObject

BASE=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
FORMS=BASE/'forms'
MAP=json.loads((FORMS/'official-field-map-2025.json').read_text())
SOURCES={r['id']:r for r in json.loads((FORMS/'official-sources-2025.json').read_text())['forms'] if 'sha256' in r}
D=Decimal

_PAGE_ID_KEYS=('/TaxRebornForm','/TaxRebornOwner','/TaxRebornCopy','/TaxRebornTemplatePage')

def packet_instance(form_id,owner,copy_index,page_count,template_sha256=None):
    """Plan one output copy before rendering; this is not filing applicability.

    All physical pages of our pinned public IRS templates are currently selected.
    Distinct owners and copies must remain distinct even for the same form ID.
    """
    if not isinstance(form_id,str) or form_id not in SOURCES and form_id not in ('f1040','preparation_checklist'):
        raise ValueError('Unsupported packet form identity: '+str(form_id))
    if owner not in ('taxpayer','spouse') and not (form_id=='preparation_checklist' and owner=='packet'):
        raise ValueError('Unsupported packet owner: '+str(owner))
    if type(copy_index) is not int or copy_index<1:
        raise ValueError('Packet copy index must be a positive integer')
    if type(page_count) is not int or page_count<1:
        raise ValueError('Packet page count must be a positive integer')
    if template_sha256 is not None and (not isinstance(template_sha256,str) or not re.fullmatch(r'[0-9a-f]{64}',template_sha256)):
        raise ValueError('Packet template identity requires a SHA256 digest')
    return {'form_id':form_id,'owner':owner,'copy_index':copy_index,
            'required_pages':list(range(1,page_count+1)),
            'template_sha256':template_sha256}

def packet_manifest(instances):
    """Validate planned composite identities and refuse unsupported page gaps."""
    plan=[];seen=set()
    for instance in instances:
        pages=instance.get('required_pages')
        if not isinstance(pages,list) or not pages or any(type(page) is not int for page in pages):
            raise ValueError('Packet requires an explicit nonempty page list')
        checked=packet_instance(instance.get('form_id'),instance.get('owner'),
                                instance.get('copy_index'),len(pages),instance.get('template_sha256'))
        if pages!=checked['required_pages']:
            raise ValueError('Packet page selection has an unsupported gap or duplicate')
        identity=(checked['form_id'],checked['owner'],checked['copy_index'])
        if identity in seen:raise ValueError('Duplicate packet copy identity: '+str(identity))
        seen.add(identity);plan.append(checked)
    return {'version':1,'tax_year':2025,'instances':plan,
            'expected_pdf_pages':sum(len(item['required_pages']) for item in plan),
            'scope':'current_supported_paper_preparation','filing_packet_ready':False}

def stamp_packet_pages(pages,instance):
    """Bind required page identity to each actual page before serialization."""
    plan=packet_manifest([instance])['instances'][0]
    if len(pages)!=len(plan['required_pages']):
        raise ValueError('Packet renderer omitted or added pages: '+str((plan['form_id'],plan['owner'],plan['copy_index'])))
    for page,number in zip(pages,plan['required_pages']):
        page[NameObject(_PAGE_ID_KEYS[0])]=TextStringObject(plan['form_id'])
        page[NameObject(_PAGE_ID_KEYS[1])]=TextStringObject(plan['owner'])
        page[NameObject(_PAGE_ID_KEYS[2])]=NumberObject(plan['copy_index'])
        page[NameObject(_PAGE_ID_KEYS[3])]=NumberObject(number)

def verify_packet_pages(raw,manifest):
    """Reconcile actual serialized pages, not a renderer's Success/count flag."""
    if (manifest.get('version')!=1 or type(manifest.get('version')) is not int or
            manifest.get('tax_year')!=2025 or manifest.get('filing_packet_ready') is not False or
            manifest.get('scope')!='current_supported_paper_preparation'):
        raise ValueError('Packet manifest has an unsupported version/year/readiness scope')
    checked=packet_manifest(manifest['instances'])
    if type(manifest.get('expected_pdf_pages')) is not int or manifest.get('expected_pdf_pages')!=checked['expected_pdf_pages']:
        raise ValueError('Packet manifest count differs from its required copies/pages')
    if not raw:
        if checked['expected_pdf_pages']:raise ValueError('Required packet output is empty')
        return {'expected_pages':0,'actual_pages':0,'page_identities_verified':True,'missing_pages':[]}
    reader=PdfReader(io.BytesIO(raw))
    expected=[(item['form_id'],item['owner'],item['copy_index'],number)
              for item in checked['instances'] for number in item['required_pages']]
    if len(reader.pages)!=len(expected):
        raise ValueError('Packet PDF page count differs: expected '+str(len(expected))+', received '+str(len(reader.pages)))
    for position,(page,identity) in enumerate(zip(reader.pages,expected),1):
        actual=tuple(page.get(key) for key in _PAGE_ID_KEYS)
        if actual!=identity or any(type(actual[index]) is not NumberObject for index in (2,3)):
            raise ValueError('Packet page identity differs at output page '+str(position)+': expected '+str(identity))
    return {'expected_pages':len(expected),'actual_pages':len(reader.pages),
            'page_identities_verified':True,'missing_pages':[]}

def whole(v):return int(D(str(v)).quantize(D('1'),rounding=ROUND_HALF_UP))
def total(rows,key):return whole(sum((D(str(r.get(key,'0'))) for r in rows),D(0)))
def _short(id,page,n):
    candidates=[key for key in MAP[id]['fields'] if re.search(r'\.f'+str(page)+r'[_-]0?'+str(n)+r'\[0\]$',key) and MAP[id]['fields'][key]['page']==page]
    if len(candidates)!=1:raise ValueError('Ambiguous official field '+str((id,page,n)))
    return candidates[0]
def _field_at(id,page,n,x):
    choices=[key for key,meta in MAP[id]['fields'].items() if meta['page']==page and re.search(r'\.f'+str(page)+r'[_-]0?'+str(n)+r'\[0\]$',key) and abs(meta['rect'][0]-x)<2]
    if len(choices)!=1:raise ValueError('Ambiguous official cell '+str((id,page,n,x)))
    return choices[0]

def _identity(data,owner='taxpayer'):
    i=data.get('identity',{});prefix='spouse_' if owner=='spouse' else ''
    name=' '.join(str(i.get(prefix+k,'')) for k in ('first_name','middle_initial','last_name')).strip()
    ssn=str(i.get(prefix+'ssn','')).replace('-','').replace(' ','')
    missing=[]
    if not name:missing.append(owner+' legal name')
    if not re.fullmatch(r'\d{9}',ssn):
        if ssn:raise ValueError(owner+' SSN/ITIN must contain exactly9digits')
        missing.append(owner+' SSN/ITIN');ssn=''
    return name,ssn,missing

def _draft_footer():
    p=PageObject.create_blank_page(width=612,height=792)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    p[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
    s=DecodedStreamObject();s.set_data(b'q 0.6 0.12 0.05 rg BT /F1 6 Tf 36 5 Td (TAX REBORN DRAFT - NOT FILED - REVIEW REQUIRED FACTS AND SUPPORTING RECORDS) Tj ET Q')
    p[NameObject('/Contents')]=s;return p

def _field_name(obj):
    names=[str(obj.get('/T',''))];cursor=obj
    while cursor.get('/Parent'):
        cursor=cursor['/Parent'].get_object();names.insert(0,str(cursor.get('/T','')))
    return '.'.join(n for n in names if n)

def verify_official_pdf(raw,expected):
    reader=PdfReader(io.BytesIO(raw));fields=reader.get_fields() or {};seen=set()
    for key,value in expected.items():
        if key not in fields or str(fields[key].get('/V',''))!=str(value):raise ValueError('Canonical official field failed readback: '+key)
    for page in reader.pages:
        for ref in page.get('/Annots',[]):
            widget=ref.get_object()
            if widget.get('/Subtype')!='/Widget':continue
            key=_field_name(widget)
            if key not in expected:continue
            cursor=widget;value=cursor.get('/V')
            while value is None and cursor.get('/Parent'):
                cursor=cursor['/Parent'].get_object();value=cursor.get('/V')
            if str(value)!=str(expected[key]):raise ValueError('Widget value differs: '+key)
            appearance=widget.get('/AP',{}).get('/N')
            if not appearance:raise ValueError('Widget has no appearance: '+key)
            if widget.get('/FT')=='/Btn':
                state=widget.get('/AS')
                if str(state)!=str(expected[key]) or state not in appearance:raise ValueError('Checkbox appearance differs: '+key)
            elif not appearance.get_object().get_data():raise ValueError('Empty field appearance: '+key)
            seen.add(key)
    if seen!=set(expected):raise ValueError('Missing widget for official fields: '+str(set(expected)-seen))
    return {'pages':len(reader.pages),'verified_fields':len(expected),'interactive':True,'canonical_values_verified':True,'widget_values_and_appearances_verified':True}

def render_official_form(form_id,line_values=None,field_values=None,identity=None,missing_facts=None,owner='taxpayer',copy_index=1,printed_annotations=None):
    """Fill one public IRS form; unsupported logical lines become explicit gaps."""
    if form_id not in SOURCES or form_id not in MAP:raise ValueError('Unsupported official form '+form_id)
    source=SOURCES[form_id];raw=(FORMS/source['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=source['sha256']:raise ValueError('IRS template hash changed: '+form_id)
    reader=PdfReader(io.BytesIO(raw))
    if '2025' not in reader.pages[0].extract_text():raise ValueError('IRS template tax year differs: '+form_id)
    instance=packet_instance(form_id,owner,copy_index,len(reader.pages),source['sha256'])
    values={};missing=list(missing_facts or []);unmapped=[]
    for key,value in (line_values or {}).items():
        if value is None:continue
        fixed=MAP[form_id].get('fixed_lines',{})
        if str(key) in fixed:
            if value!=fixed[str(key)]:raise ValueError('PrintedIRS constant differs: '+form_id+' line'+str(key))
            continue
        split=MAP[form_id].get('split_decimal_fields',{}).get(str(key))
        if split:
            if not isinstance(value,str) or not re.fullmatch(r'\d+\.\d{3}',value):raise ValueError('Official ratio requires3fractiondigits: '+str(key))
            integer,fraction=value.split('.');values[split[0]]=integer;values[split[1]]=fraction
            continue
        field=MAP[form_id]['line_fields'].get(str(key))
        if field is None:unmapped.append(str(key));continue
        if isinstance(value,(list,dict,bool,float)):raise ValueError('Official scalar field requires integer/string: '+str(key))
        values[field]=str(value)
    values.update({k:str(v) for k,v in (field_values or {}).items() if v is not None})
    if identity:
        name,ssn,identity_missing=identity;missing+=identity_missing
        if name:values[MAP[form_id]['identity_fields']['name']]=name
        if ssn:values[MAP[form_id]['identity_fields']['ssn']]=ssn
    if unmapped:missing.append(form_id+' unmapped computed line(s): '+', '.join(unmapped))
    writer=PdfWriter();writer.clone_document_from_reader(reader)
    fields=writer.get_fields() or {}
    if set(values)-set(fields):raise ValueError('IRS AcroForm layout differs: '+str(set(values)-set(fields)))
    for key,value in values.items():
        field=fields[key]
        # Respect IRS split digits/rates rather than silently clipping strings.
        maximum=field.get('/MaxLen')
        if maximum and field.get('/FT')=='/Tx' and len(value)>maximum:raise ValueError('Official field exceeds MaxLen: '+key)
        if field.get('/FT')=='/Btn':values[key]=NameObject(value)
    writer.update_page_form_field_values(None,values,auto_regenerate=False)
    for note in printed_annotations or []:
        if set(note)!={'page','x','y','text'} or note['page'] not in range(1,len(writer.pages)+1):raise ValueError('UnsupportedIRS source annotation')
        page=PageObject.create_blank_page(width=612,height=792)
        font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):font})})
        literal=str(note['text']).replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
        stream=DecodedStreamObject();stream.set_data(('q 0 0 0 rg BT /F1 7 Tf '+str(note['x'])+' '+str(note['y'])+' Td ('+literal+') Tj ET Q').encode('ascii'))
        page[NameObject('/Contents')]=stream;writer.pages[note['page']-1].merge_page(page)
    for page in writer.pages:page.merge_page(_draft_footer())
    stamp_packet_pages(writer.pages,instance)
    writer.add_metadata({'/Title':form_id+' IRS2025 Tax Reborn draft','/Subject':'Supporting form draft; not transmitted or ready to sign'})
    target=io.BytesIO();writer.write(target);pdf=target.getvalue()
    proof=verify_official_pdf(pdf,values)
    proof['packet_preflight']=verify_packet_pages(pdf,packet_manifest([instance]))
    return {'id':form_id,'owner':owner,'copy_index':copy_index,'packet_instance':instance,'tax_year':2025,'source':source['url'],'template_sha256':source['sha256'],'status':'draft_incomplete' if missing else 'draft_facts_present','line_values':line_values or {},'values':{k:str(v) for k,v in values.items()},'unmapped_lines':unmapped,'missing_facts':list(dict.fromkeys(missing)),'verification':proof,'pdf_bytes':pdf}

def _checkbox(id,short,state=None,page=None):
    if page is None:page=int(re.match(r'c(\d+)_',short)[1])
    found=[k for k,v in MAP[id]['fields'].items() if v['page']==page and k.endswith('.'+short) and (state is None or state in v['states'])]
    if len(found)!=1:raise ValueError('Ambiguous official checkbox '+str((id,short,state)))
    key=found[0];return {key:state or MAP[id]['fields'][key]['states'][0]}

def _input_with_defaults(submitted):
    import tax_engine, tax_credits, tax_additional
    clean=deepcopy(submitted);clean.pop('form_facts',None)
    data=tax_engine.normalized(clean)
    for module in (tax_credits,tax_additional):
        for group,defaults in module.default_inputs().items():data[group]={**defaults,**data.get(group,{})}
        for path,defaults in module.row_templates().items():
            group,key=path.split('.')
            data[group][key]=[{**deepcopy(defaults),**row} for row in data[group][key]]
    return data

def _paper_facts(submitted):
    facts=deepcopy(submitted)
    def walk(obj):
        if isinstance(obj,list):
            for row in obj:walk(row)
        elif isinstance(obj,dict):
            for key,value in list(obj.items()):
                if key.endswith('_answer'):
                    if value in ('yes','no'):obj[key.removesuffix('_answer')]=value=='yes'
                    elif value=='unanswered':obj.pop(key.removesuffix('_answer'),None)
                else:walk(value)
    walk(facts)
    a=facts.get('schedule_a',{})
    for key,line in (('salt_income_tax','5a'),('salt_real_estate_tax','5b'),('salt_personal_property_tax','5c'),('mortgage_form1098','8a'),('mortgage_non1098','8b'),('mortgage_points','8c')):
        if key in a:a[line]=a[key]
    expense_map={'advertising':'8','car_truck':'9','commissions_fees':'10','contract_labor':'11','insurance':'15','mortgage_interest':'16a','other_interest':'16b','legal_professional':'17','office':'18','rent_equipment':'20a','rent_property':'20b','repairs':'21','supplies':'22','taxes_licenses':'23','travel':'24a','deductible_meals':'24b','utilities':'25','other_expenses':'27b'}
    for row in facts.get('businesses',[]):
        if isinstance(row.get('expense_lines'),dict):row['expense_lines']={expense_map.get(k,k):v for k,v in row['expense_lines'].items()}
    return facts

def _matched(rows,index,key,value):
    matches=[row for row in rows if row.get(key)==value and value]
    if len(matches)==1:return matches[0]
    if matches:return {}
    if index<len(rows) and not rows[index].get(key):return rows[index]
    return {}

def official_form_specs(record):
    """The plan contains only amounts backed by current inputs/results."""
    facts=_paper_facts(record.get('form_facts',record['data'].get('form_facts',record['data'].get('filing_details',{}).get('official_form_facts',{}))))
    data=_input_with_defaults(record['data']);r=record['result'];s=r.get('schedules',{});l=r['lines'];status=r['filing_status'];specs=[]
    def add(id,lines,fields=None,gaps=None,owner='taxpayer',annotations=None):
        identity=_identity(data,owner)
        if status=='mfj' and id not in ('f1040sc','f1040sse','f8889','f8606','f5329'):
            spouse=_identity(data,'spouse');identity=(identity[0]+(' & '+spouse[0] if spouse[0] else ''),identity[1],identity[2]+[x for x in spouse[2] if 'legal name' in x])
        specs.append({'form_id':id,'line_values':{str(k):v for k,v in lines.items() if v is not None},'field_values':fields or {},'missing_facts':gaps or [],'owner':owner,'identity':identity,'printed_annotations':annotations or []})
    voucher=tax_filing.payment_voucher_plan(data,r)
    if voucher['requested']:
        ident=tax_filing.mailing_address(data)['values'];fields={};gaps=list(voucher['missing_facts'])
        # Form1040-V has separate name/address rows and two SSN boxes. Its
        # printed payment amount is line3, not a generic tax subtotal.
        identity_map={'ssn':1,'first_name':5,'last_name':6,'address':9,'apt':10,
            'city':11,'state':12,'zip':13,'foreign_country':14,
            'foreign_province':15,'foreign_postal_code':16}
        for key,number in identity_map.items():
            value=str(ident.get(key,''))
            if key=='ssn':value=value.replace('-','').replace(' ','')
            if key=='first_name':value=' '.join(x for x in [value,ident.get('middle_initial','')] if x)
            if value:fields[_short('f1040v',1,number)]=value
            elif key in ('ssn','first_name','last_name','address','city'):gaps.append('Form1040-V '+key)
        if status=='mfj':
            for key,number in [('spouse_ssn',2),('spouse_first_name',7),('spouse_last_name',8)]:
                value=str(ident.get(key,''));value=value.replace('-','').replace(' ','') if key.endswith('ssn') else value
                if key=='spouse_first_name':value=' '.join(x for x in [value,ident.get('spouse_middle_initial','')]if x)
                if value:fields[_short('f1040v',1,number)]=value
                else:gaps.append('Form1040-V '+key)
        specs.append({'form_id':'f1040v','line_values':{'3':voucher['amount']} if voucher['amount'] is not None else {},
            'field_values':fields,'missing_facts':gaps,'owner':'taxpayer','identity':None,'printed_annotations':[]})
    child=s.get('form_8814',{})
    child_other=child.get('parent_ordinary_other_income',0);child_qdiv=child.get('parent_qualified_dividends',0);child_capital=child.get('parent_capital_gain',0)
    for index,row in enumerate(child.get('form_lines',{}).get('children',[])):
        fields={_short('f8814',1,3):row['name'],_short('f8814',1,4):row['ssn'].replace('-','')}
        if row['multiple_children']:fields.update(_checkbox('f8814','c1_1[0]'))
        fields.update(_checkbox('f8814','c1_2[0]' if row['14']>=1350 else 'c1_2[1]'))
        vals={k:v for k,v in row.items() if k in set(MAP['f8814']['line_fields'])|{'5','7','8','13'}}
        add('f8814',vals,fields,[] if row['eligibility_confirmed'] else ['Form8814 child'+str(index+1)+' eligibility/income facts unresolved'])
    sc1=s.get('schedule_1',{})
    if l.get('8') or l.get('10'):
        own_other=total([data.get('other_income',{})],'other');other=own_other+child_other
        other_description=facts.get('other_income_description','')
        if child_other:other_description=(other_description+'; ' if other_description else '')+'Form 8814 - $'+str(child_other)
        add('f1040s1',{'3':sc1.get('business_income',0),'5':sc1.get('rental_income_loss',0),'7':whole(data.get('other_income',{}).get('unemployment','0')),'8f':sc1.get('hsa_other_income',0),'8z':other,'9':other+sc1.get('hsa_other_income',0),'10':l['8'],'13':sc1.get('hsa_deduction',0),'15':sc1.get('half_se_tax',0),'17':sc1.get('self_employed_health_insurance',0),'20':sc1.get('ira_deduction',0),'21':sc1.get('student_loan_interest',0),'26':l['10']}, {_short('f1040s1',1,35):other_description} if other else {},['Schedule1 line8z income type/description'] if own_other and not facts.get('other_income_description') else [])
    if l.get('17') or l.get('23'):
        hsa=s.get('form_8889',{}).get('form_lines',{});excise=sum(row.get('form5329_current_excess_tax',0) for row in hsa.values());dist=sum(row.get('line17b_additional_tax',0) for row in hsa.values())
        add('f1040s2',{'1a':s.get('form_8962',{}).get('repayment',0),'1z':s.get('form_8962',{}).get('repayment',0),'2':s.get('form_6251',{}).get('tax',0),'3':l['17'],'4':sum(row.get('line_12_tax',0) for row in s.get('schedule_se',{}).values()),'8':excise,'11':s.get('form_8959',{}).get('tax',0),'12':s.get('form_8960',{}).get('tax',0),'17c':dist,'18':dist,'21':l['23']})
    if l.get('20') or l.get('31'):
        ptc=s.get('form_8962',{}).get('refundable_credit',0);adoption=s.get('form_8839',{});energy=s.get('form_5695',{});ftc=s.get('form_1116',{})
        adoption_refund=0  #2025Form8839 refund is1040line30, notSchedule3
        add('f1040s3',{'1':ftc.get('nonrefundable_credit',0),'2':s.get('form_2441',{}).get('nonrefundable_credit',0),'3':s.get('form_8863',{}).get('nonrefundable_credit',0),'4':s.get('form_8880',{}).get('nonrefundable_credit',0),'5a':energy.get('form_lines',{}).get('15',0),'5b':energy.get('form_lines',{}).get('32',0),'6c':adoption.get('nonrefundable_credit',0),'6d':s.get('schedule_r',{}).get('nonrefundable_credit',0),'7':s.get('schedule_r',{}).get('nonrefundable_credit',0)+adoption.get('nonrefundable_credit',0),'8':l['20'],'9':ptc,'11':l['31']-ptc-adoption_refund,'15':l['31']-adoption_refund})
    a=s.get('schedule_a',{})
    if a.get('chosen')=='itemized':
        i=data.get('itemized',{});f=facts.get('schedule_a',{});gaps=[]
        lines={'1':whole(i.get('medical','0')),'2':l['11b'],'3':whole(D(l['11b'])*D('.075')),'4':a['medical_after_7_5_percent'],'5d':whole(i.get('state_local_tax','0')),'5e':a['salt_deduction'],'7':a['salt_deduction'],'8e':a['mortgage_interest'],'9':a['investment_interest'],'10':a['mortgage_interest']+a['investment_interest'],'11':a['cash_charity'],'14':a['cash_charity'],'17':a['itemized_total']}
        if whole(i.get('state_local_tax','0')):
            if f.get('salt_split_confirmed',False) and all(k in f for k in ('5a','5b','5c')) and sum(whole(f[k]) for k in ('5a','5b','5c'))==lines['5d']:lines.update({k:whole(f[k]) for k in ('5a','5b','5c')})
            else:gaps.append('ScheduleA SALT line5a/5b/5c verified split')
        if a['mortgage_interest']:
            if f.get('mortgage_split_confirmed',False) and all(k in f for k in ('8a','8b','8c')) and sum(whole(f[k]) for k in ('8a','8b','8c'))==a['mortgage_interest']:lines.update({k:whole(f[k]) for k in ('8a','8b','8c')})
            else:gaps.append('ScheduleA mortgage Form1098/non1098/points verified split')
        add('f1040sa',lines,gaps=gaps)
    if data.get('interest') or data.get('dividends') or child_qdiv:
        fields={};gaps=[]
        for kind,start,capacity,key in (('interest',3,14,'taxable'),('dividends',34,15,'ordinary')):
            rows=[row for row in data.get(kind,[]) if D(row.get(key,'0'))]
            if kind=='dividends' and child_qdiv:rows.append({'payer':'Form 8814','ordinary':str(child_qdiv)})
            if len(rows)>capacity:gaps.append('ScheduleB '+kind+' continuation list required')
            for index,row in enumerate(rows[:capacity]):
                fields[_short('f1040sb',1,start+index*2)]=row.get('payer','');fields[_short('f1040sb',1,start+index*2+1)]=str(whole(row[key]))
                if not row.get('payer'):gaps.append('ScheduleB '+kind+' payer '+str(index+1))
        b=facts.get('schedule_b',{})
        if not b.get('facts_confirmed',False):gaps.append('ScheduleB foreign-account/trust facts not yet confirmed')
        for key,short in (('foreign_account','c1_1'),('fbar_required','c1_2'),('foreign_trust','c1_3')):
            if key in b and type(b[key]) is bool:fields.update(_checkbox('f1040sb',short+('[0]' if b[key] else '[1]')))
            else:gaps.append('ScheduleB PartIII '+key+' yes/no fact')
        if b.get('foreign_account'):gaps.append('ScheduleB country names/FBAR review')
        add('f1040sb',{'2':l['2b'],'3':0,'4':l['2b'],'6':l['3b']},fields,gaps)
    for index,row in enumerate(s.get('schedule_c',[])):
        id='f1040sc';details=facts.get('businesses',[]);f=_matched(details,index,'business_name',row.get('name'));gaps=[]
        if not f.get('facts_confirmed',False):gaps.append('ScheduleC '+str(index+1)+' source facts not yet confirmed')
        fields={_short(id,1,5):row.get('name','')};lines={'1':row['gross_revenue'],'2':0,'3':row['gross_revenue'],'4':0,'5':row['gross_revenue'],'6':0,'7':row['gross_revenue'],'28':row['total_expenses'],'29':row['profit'],'30':0,'31':row['profit']}
        for key,n in (('profession',3),('business_code',4),('ein',6),('address',7),('city_state_zip',8)):
            if f.get(key):fields[_short(id,1,n)]=f[key]
            elif key in ('profession','business_code','address','city_state_zip'):gaps.append('ScheduleC '+str(index+1)+' '+key)
        expenses=f.get('expense_lines')
        if isinstance(expenses,dict) and sum(whole(v) for v in expenses.values())==row['total_expenses']:
            lines.update({k:whole(v) for k,v in expenses.items() if k in MAP[id]['line_fields']})
        elif row['total_expenses']:gaps.append('ScheduleC '+str(index+1)+' expense category breakdown reconciled to line28')
        fields.update(_checkbox(id,'c1_1[0]'));fields.update(_checkbox(id,'c1_2[0]'))
        if f.get('started_2025'):fields.update(_checkbox(id,'c1_3[0]'))
        if f.get('requires_1099'):
            if type(f.get('filed_1099')) is bool:fields.update(_checkbox(id,'c1_5[0]' if f['filed_1099'] else 'c1_5[1]'))
            else:gaps.append('ScheduleC '+str(index+1)+' required Forms1099 filed/will-file answer')
        if row['profit']<0:fields.update(_checkbox(id,'c1_7[0]'))
        if isinstance(expenses,dict) and whole(expenses.get('9','0')):gaps.append('ScheduleC vehicle PartIV use and mileage records')
        if isinstance(expenses,dict) and whole(expenses.get('27b','0')):
            if f.get('other_expenses_description'):
                fields[_short(id,2,15)]=f['other_expenses_description'];fields[_short(id,2,16)]=str(whole(expenses['27b']));lines['48']=whole(expenses['27b'])
            else:gaps.append('ScheduleC other expenses description')
        if 'requires_1099' in f and type(f['requires_1099']) is bool:fields.update(_checkbox(id,'c1_4[0]' if f['requires_1099'] else 'c1_4[1]'))
        else:gaps.append('ScheduleC '+str(index+1)+' Form1099 reporting question')
        add(id,lines,fields,gaps,row['owner'])
    for owner,row in s.get('schedule_se',{}).items():
        if not row.get('line_4a_net_earnings'):continue
        add('f1040sse',{'1a':0,'1b':0,'2':row['net_profit'],'3':row['net_profit'],'4a':row['line_4a_net_earnings'],'4b':0,'4c':row['line_4a_net_earnings'],'5a':0,'5b':0,'6':row['line_4a_net_earnings'],'8a':row['w2_ss_wages_tips'],'8b':0,'8c':0,'8d':row['w2_ss_wages_tips'],'9':max(0,176100-row['w2_ss_wages_tips']),'10':row['line_10_ss_tax'],'11':row['line_11_medicare_tax'],'12':row['line_12_tax'],'13':row['line_13_deduction']},owner=owner)
    if data.get('capital_gains') or total(data.get('dividends',[]),'capital_gain_distributions') or child_capital or any(D(data.get('carryovers',{}).get(k,'0')) for k in ('capital_short','capital_long')):
        d=s['schedule_d'];lines={'6':whole(data['carryovers']['capital_short']),'7':d['net_short_term'],'13':total(data.get('dividends',[]),'capital_gain_distributions')+child_capital,'14':whole(data['carryovers']['capital_long']),'15':d['net_long_term'],'16':d['net_gain_loss'],'18':d.get('collectibles_28_gain',0),'19':d.get('unrecaptured_1250_gain',0)};dfields={};gaps=[];groups={}
        if d.get('special_distribution_only') and lines['15']>0 and lines['16']>0:
            # Official TY2025 ScheduleD PartIII: both gains -> line17Yes;
            # nonzero18/19 -> line20No, ScheduleDTaxWorksheet, skip21/22.
            dfields.update(_checkbox('f1040sd','c2_1[0]',page=2))
            dfields.update(_checkbox('f1040sd','c2_2[1]' if lines['18'] or lines['19'] else 'c2_2[0]',page=2))
        if d['net_gain_loss']<0:lines['21']=abs(d['income_line_7a'])
        details=facts.get('capital_gains',[])
        for index,transaction in enumerate(data.get('capital_gains',[])):
            f=_matched(details,index,'transaction_description',transaction['description']);category=f.get('category');allowed=('A','B','C') if transaction['term']=='short' else ('D','E','F')
            if category not in allowed:category=None
            groups.setdefault((transaction['term'],category),[]).append((index,transaction,f))
        for (term,category),entries in groups.items():
            page=1 if term=='short' else 2;category_gap=[]
            if not category:category_gap.append('Form8949 brokerage category A/B/C orD/E/F requires actual source statement')
            totals=[0,0,0,0];all_integers=True
            for offset in range(0,len(entries),11):
                chunk=entries[offset:offset+11];fields={};missing=list(category_gap);subtotals=[0,0,0,0]
                if category:fields.update(_checkbox('f8949','c'+str(page)+'_1['+str(('ABC' if page==1 else 'DEF').index(category))+']'))
                for row_index,(index,transaction,f) in enumerate(chunk):
                    base=3+row_index*8;adjust=D(transaction.get('adjustment','0'))+D(transaction.get('wash_sale_disallowed','0'));proceeds=D(transaction['proceeds']);basis=D(transaction['cost_basis']);gain=proceeds-basis+adjust
                    amounts=(proceeds,basis,adjust,gain);integer=all(value==value.to_integral_value() for value in amounts)
                    if not integer:all_integers=False;missing.append('Form8949 transaction '+str(index+1)+' cents/category totals require full8949-to-ScheduleD rounding reconciliation')
                    values=[transaction['description'],f.get('date_acquired',''),f.get('date_sold',''),str(whole(proceeds)) if integer else format(proceeds,'f'),str(whole(basis)) if integer else format(basis,'f'),'W' if adjust else '',str(whole(adjust)) if integer else format(adjust,'f'),str(whole(gain)) if integer else format(gain,'f')]
                    for col,value in enumerate(values):
                        if value:fields[_short('f8949',page,base+col)]=value
                    if not f.get('facts_confirmed'):missing.append('Form8949 transaction '+str(index+1)+' source facts not yet confirmed')
                    for key in ('date_acquired','date_sold'):
                        value=f.get(key,'')
                        if key=='date_acquired' and value.upper()=='VARIOUS':continue
                        try:
                            parsed=date.fromisoformat(value)
                            if key=='date_sold' and parsed.year!=2025:raise ValueError('wrongyear')
                        except (ValueError,TypeError):missing.append('Form8949 transaction '+str(index+1)+' actual '+key)
                    for i,amount in enumerate(amounts):subtotals[i]+=whole(amount);totals[i]+=whole(amount)
                if all_integers:
                    for n,value in zip((91,92,94,95),subtotals):fields[_short('f8949',page,n)]=str(value)
                else:missing.append('Form8949 aggregate cents totals remain blank until reconciled')
                add('f8949',{},fields,missing)
                gaps+=missing
            if category and all_integers:
                start={'A':7,'B':11,'C':15,'D':27,'E':31,'F':35}[category]
                for i,value in enumerate(totals):dfields[_short('f1040sd',1,start+i)]=str(value)
        if data.get('capital_gains') and not all(category for term,category in groups):gaps.append('ScheduleD source-category totals are incomplete')
        add('f1040sd',lines,dfields,gaps,annotations=[{'page':1,'x':300,'y':99,'text':'Form 8814 - $'+str(child_capital)}] if child_capital else [])
    q=s.get('form_8995',{})
    if data.get('businesses'):
        carry=whole(data.get('carryovers',{}).get('qbi_loss','0'));qbi=q.get('qbi',0);component=whole(D(max(0,qbi-carry))*D('.20'))
        fields={};gaps=[];business=data['businesses']
        if len(business)==1 and not data.get('rentals'):
            fields[_short('f8995',1,3)]=business[0]['name'];fields[_short('f8995',1,4)]=_identity(data,business[0]['owner'])[1];fields[_short('f8995',1,5)]=str(qbi)
            if not business[0]['name']:gaps.append('Form8995 business name')
        else:
            alloc=facts.get('qbi_businesses',[])
            if alloc and sum(whole(x.get('qbi','0')) for x in alloc)==qbi and len(alloc)<=5:
                for index,row in enumerate(alloc):
                    for offset,k in enumerate(('name','tin','qbi')):fields[_short('f8995',1,3+index*3+offset)]=str(row.get(k,''))
                    if not row.get('name') or not re.fullmatch(r'\d{9}',str(row.get('tin',''))):gaps.append('Form8995 business '+str(index+1)+' name/TIN')
            else:gaps.append('Form8995 per-business QBI allocation reconciled to actual total')
        add('f8995',{'2':qbi,'3':carry,'4':max(0,qbi-carry),'5':component,'6':0,'7':0,'8':0,'9':0,'10':component,'11':q['taxable_before_qbi'],'12':q['net_capital_gain_plus_qualified_dividends'],'13':max(0,q['taxable_before_qbi']-q['net_capital_gain_plus_qualified_dividends']),'14':q['income_limit'],'15':q['deduction'],'16':q.get('current_qbi_loss_for_future_review',0),'17':0},fields,gaps)
    child=s.get('schedule_8812',{})
    if data.get('dependents'):
        gross=child['credit_before_phaseout'];available=child['credit_after_phaseout'];phase=child['phaseout'];cap=child['qualifying_children']*1700;remain=max(0,available-child['nonrefundable_credit']);limit=child.get('credit_limit_worksheet_amount',max(0,l['18']-l['20']))
        vals={'1':l['11a'],'2a':0,'2b':0,'2c':0,'2d':0,'3':l['11a'],'4':child['qualifying_children'],'5':child['qualifying_children']*2200,'6':child['other_dependents'],'7':child['other_dependents']*500,'8':gross,'9':400000 if status=='mfj' else 200000,'10':phase*20,'11':phase,'12':available,'13':limit,'14':child['nonrefundable_credit'],'16a':remain,'16b':cap,'17':min(remain,cap),'18a':child['earned_income'],'18b':0,'19':max(0,child['earned_income']-2500),'20':child['actc_earned_income_amount'],'27':child['actc']}
        fields={_short('f1040s8',2,3):str(child['qualifying_children'])};gaps=[]
        if child['qualifying_children']>=3:gaps.append('Schedule8812 three-child payroll alternative intermediate lines21-26 review')
        add('f1040s8',vals,fields,gaps)
    med=s.get('form_8959')
    if med:
        wages=med['medicare_wages'];threshold=med['threshold'];se=med['se_earnings'];held=total(data.get('w2',[]),'medicare_withholding');line7=whole(D(max(0,wages-threshold))*D('.009'));line13=whole(D(max(0,se-max(0,threshold-wages)))*D('.009'))
        add('f8959',{'1':wages,'2':0,'3':0,'4':wages,'5':threshold,'6':max(0,wages-threshold),'7':line7,'8':se,'9':threshold,'10':wages,'11':max(0,threshold-wages),'12':max(0,se-max(0,threshold-wages)),'13':line13,'14':0,'15':threshold,'16':0,'17':0,'18':med['tax'],'19':held,'20':wages,'21':whole(D(wages)*D('.0145')),'22':med['additional_medicare_withheld'],'23':0,'24':med['additional_medicare_withheld']})
    for module,id in (('form_8960','f8960'),('form_6251','f6251'),('form_4952','f4952')):
        row=s.get(module,{})
        if row.get('tax',row.get('deduction',0)) or row.get('special_distribution_full_partIII') or row.get('form_lines') and (module=='form_6251' and any(D(str(data.get('amt',{}).get(k,'0'))) for k in ('iso_adjustment','private_activity_bond_interest','other_adjustments','capital_gain_adjustment')) or module=='form_4952' and whole(data.get('itemized',{}).get('investment_interest','0'))):add(id,row.get('form_lines',{}),gaps=row.get('blocking_issues',[]))
    if data.get('hsa',{}).get('enabled'):
        for owner,row in s.get('form_8889',{}).get('form_lines',{}).items():
            inp=next(account for account in data['hsa']['accounts'] if account['owner']==owner);vals={'2':whole(inp['personal_contributions']),'3':row['base_limit'],'4':whole(inp['archer_msa_contributions']),'5':max(0,row['base_limit']-whole(inp['archer_msa_contributions'])),'6':row['contribution_limit']-row['catchup'],'7':row['catchup'],'8':row['contribution_limit'],'9':row['employer_contributions'],'10':0,'11':row['employer_contributions'],'12':max(0,row['contribution_limit']-row['employer_contributions']),'13':row['line13_deduction'],'14a':whole(inp['distributions']),'14b':whole(inp['rollover_distributions'])+whole(inp['excess_withdrawal_distributions']),'14c':row['line14c_distributions'],'15':row['line15_qualified_medical'],'16':row['line16_taxable_distributions'],'17b':row['line17b_additional_tax']}
            coverage=inp.get('coverage',[]);hfields={}
            if 'family' in coverage:hfields.update(_checkbox('f8889','c1_1[1]'))
            elif 'self' in coverage or 'self_only' in coverage:hfields.update(_checkbox('f8889','c1_1[0]'))
            if row.get('exception_taxable_distributions'):hfields.update(_checkbox('f8889','c1_2[0]'))
            add('f8889',vals,hfields,owner=owner)
            if row['excess_contributions']:add('f5329',{'42':0,'43':0,'44':0,'45':0,'46':0,'47':row['excess_contributions'],'48':row['excess_contributions'],'49':row['form5329_current_excess_tax']},gaps=['Form5329 HSA December31 account value confirmed tax cap'],owner=owner)
    if data.get('ira',{}).get('enabled'):
        for owner,row in s.get('ira_contributions',{}).get('form_lines',{}).items():
            if row.get('nondeductible',0) or row.get('form8606_line2',0):add('f8606',{'1':row.get('nondeductible',0),'2':row.get('form8606_line2',0),'3':row.get('form8606_line3',row.get('nondeductible',0)+row.get('form8606_line2',0)),'14':row.get('form8606_line14',row.get('nondeductible',0)+row.get('form8606_line2',0))},owner=owner)
    if data.get('education',{}).get('enabled'):
        row=s.get('form_8863',{});v=row.get('form_lines',{});high=180000 if status=='mfj' else 90000;span=20000 if status=='mfj' else 10000;magi=l['11a'];factor=v.get('phaseout_factor','0');parts=str(factor).split('.')
        fields={_short('f8863',1,10):parts[0],_short('f8863',1,11):(parts[1] if len(parts)>1 else '0')[:3],_short('f8863',1,22):parts[0],_short('f8863',1,23):(parts[1] if len(parts)>1 else '0')[:3]}
        vals={k.removeprefix('line'):value for k,value in v.items() if re.fullmatch(r'line\d+',k)};vals.pop('6',None);vals.pop('17',None);vals.update({'2':high,'3':magi,'4':max(0,high-magi),'5':span,'12':whole(D(v.get('line11',0))*D('.20')),'13':high,'14':magi,'15':max(0,high-magi),'16':span})
        if v.get('refund_restricted_under24'):fields.update(_checkbox('f8863','c1_1[0]'))
        gaps=[];students=data['education']['students'];details=facts.get('education',{}).get('students',[])
        if len(students)==1:
            student=students[0];calculated=v.get('students',[{}])[0];extra=_matched(details,0,'student_id',student['student_id']);student_identity=None
            if not extra.get('facts_confirmed',False):gaps.append('Form8863 student source facts not yet confirmed')
            if student['student_id'] in ('taxpayer','spouse'):student_identity=_identity(data,student['student_id'])
            elif extra.get('ssn'):
                student_identity=(student['name'],str(extra['ssn']).replace('-',''),[])
            else:
                matching=[dep for dep in data.get('dependents',[]) if dep.get('name')==student.get('name')]
                if len(matching)==1 and matching[0].get('form_ssn'):student_identity=(student['name'],str(matching[0]['form_ssn']).replace('-',''),[])
            fields[_short('f8863',2,5)]=student_identity[0] if student_identity else student['name']
            if student_identity and re.fullmatch(r'\d{9}',student_identity[1]):fields[_short('f8863',2,6)]=student_identity[1]
            else:gaps.append('Form8863 student SSN')
            for key,n in (('institution_name',9),('institution_address',10)):
                if extra.get(key):fields[_short('f8863',2,n)]=extra[key]
                else:gaps.append('Form8863 '+key)
            ein=student['institution_ein'].replace('-','')
            if re.fullmatch(r'\d{9}',ein):
                for i,digit in enumerate(ein):fields[_short('f8863',2,11+i)]=digit
            else:gaps.append('Form8863 institution EIN')
            for key,name in (('form_1098t_received_2025','c2_1'),('form_1098t_2024_box7','c2_2')):
                if key in extra and type(extra[key]) is bool:fields.update(_checkbox('f8863',name+('[0]' if extra[key] else '[1]')))
                else:gaps.append('Form8863 '+key+' yes/no')
            for name,boolean in (('c2_5',student['aotc_prior_years']>=4),('c2_6',student['half_time_degree_program']),('c2_7',not student['first_four_years_not_completed']),('c2_8',not student['no_felony_drug_conviction'])):fields.update(_checkbox('f8863',name+('[0]' if boolean else '[1]')))
            if student['credit']=='aotc':
                expense=min(4000,calculated.get('adjusted_qualified_expenses',0));vals.update({'27':expense,'28':max(0,expense-2000),'29':whole(D(max(0,expense-2000))*D('.25')),'30':calculated.get('line30_aotc',0)})
            else:vals['31']=calculated.get('line31_llc_expenses',0)
        elif students:gaps.append('Form8863 additional student PartIII pages required')
        # The taxpayer identification header repeats on the PartIII page.
        ident=_identity(data);fields[_short('f8863',2,1)]=ident[0];fields[_short('f8863',2,2)]=ident[1]
        add('f8863',vals,fields,gaps)
    if data.get('marketplace',{}).get('enabled'):
        row=s.get('form_8962',{});v=row.get('form_lines',{});fields={};vals={k.removeprefix('line'):val for k,val in v.items() if re.fullmatch(r'line\d+[a-z]?',k) and val is not None}
        columns=('enrollment_premium','slcsp_premium','contribution','allowed_credit','allowed_credit','advance_credit')
        def ptcrow(values,start):
            premium=values.get('enrollment_premium',0);benchmark=values.get('slcsp_premium',0);contribution=values.get('contribution',0);allowed=values.get('allowed_credit',0);advance=values.get('advance_credit',0)
            amounts=(premium,benchmark,contribution,max(0,benchmark-contribution),allowed,advance)
            for index,value in enumerate(amounts):fields[_short('f8962',1,start+index)]=str(value)
        if v.get('line10_annual'):ptcrow(v['line11_annual'],13)
        else:
            for month in v.get('months',[]):
                if month.get('coverage_eligible'):
                    ptcrow(dict(month,contribution=v.get('line8b',0)),19+(month['month']-1)*6)
        region=data['marketplace'].get('region');region_short={'alaska':'c1_2[0]','hawaii':'c1_2[1]','contiguous':'c1_2[2]'}.get(region)
        if region_short:fields.update(_checkbox('f8962',region_short))
        fields.update(_checkbox('f8962','c1_4[1]'))  #Core supports verified no shared-policy/marriage allocation only
        fields.update(_checkbox('f8962','c1_5[0]' if v.get('line10_annual') else 'c1_5[1]'))
        add('f8962',vals,fields)
    for key,id in (('care','f2441'),('saver','f8880'),('elderly_credit','f1040sr')):
        if not data.get(key,{}).get('enabled') and not (key=='care' and r.get('additional_lines',{}).get('1e')):continue
        module={'care':'form_2441','saver':'form_8880','elderly_credit':'schedule_r'}[key];row=s.get(module,{});v=row.get('form_lines',{});vals={k:val for k,val in v.items() if re.fullmatch(r'\d+[a-z]?',k)};fields={};gaps=[]
        if key=='care':
            if '8' in vals:fields[_short(id,1,32)]=str(vals.pop('8')).split('.')[-1]
            care=data['care'];people_facts=facts.get('care',{}).get('beneficiaries',[])
            if care.get('mfs_qualifying_separation'):fields.update(_checkbox(id,'c1_1[0]'))
            if care.get('deemed_income_months'):fields.update(_checkbox(id,'c1_2[0]'))
            if len(care['providers'])>3:gaps.append('Form2441 provider continuation required')
            if len(care['beneficiaries'])>3:gaps.append('Form2441 qualifying-person continuation required')
            for index,provider in enumerate(care['providers'][:3]):
                base=3+index*4
                for offset,k in enumerate(('name','address','tin')):fields[_short(id,1,base+offset)]=provider[k]
                fields[_short(id,1,base+3)]=str(whole(provider['amount_paid']))
                fields.update(_checkbox(id,'c1_'+str(4+index)+('[0]' if provider['household_employee'] else '[1]')))
            for index,person in enumerate(care['beneficiaries'][:3]):
                base=15+index*4;f=_matched(people_facts,index,'beneficiary_id',person['beneficiary_id'])
                if not f:
                    deps=[dep for dep in data.get('dependents',[]) if dep.get('name')==person.get('name')]
                    if len(deps)==1:f={k:deps[0].get('form_'+k,'') for k in ('first_name','last_name','ssn')}
                for offset,k in enumerate(('first_name','last_name','ssn')):
                    if f.get(k):fields[_short(id,1,base+offset)]=str(f[k]).replace('-','') if k=='ssn' else f[k]
                    else:gaps.append('Form2441 qualifyingperson '+str(index+1)+' '+k)
                fields[_short(id,1,base+3)]=str(whole(person['qualified_expenses']))
                if person.get('disabled_incapable_self_care'):fields.update(_checkbox(id,'c1_'+str(8+index)+'[0]'))
            vals.update({'13':whole(care['benefits_carry_in']),'14':whole(care['benefits_forfeited_or_carried_out']),'17':min(v.get('15',0),v.get('16',0)),'20':min(v.get('15',0),v.get('16',0),v.get('18',0),v.get('19',0)),'21':min(5000,whole(care['benefits_plan_limit'])),'22':0,'23':v.get('15',0),'24':0})
        if key=='saver':
            for owner,base in (('taxpayer',3),('spouse',4)):
                col=v.get('columns',{}).get(owner,{})
                for line in range(1,7):
                    if str(line) in col:fields[_short(id,1,base+(line-1)*2)]=str(col[str(line)])
            if '9' in vals:fields[_short(id,1,17)]=str(vals.pop('9')).split('.')[-1]
        if key=='elderly_credit':
            box=v.get('box')
            if box:
                for field,meta in MAP[id]['fields'].items():
                    if meta['type']=='/Btn' and field.endswith('c1_1['+str(0 if int(box) in (1,3,8) else 1 if int(box) in (2,4,9) else int(box)-3)+']') and '/'+str(box) in meta['states']:fields[field]='/'+str(box)
            if int(box or 0) in (2,4,5,6,7,9):gaps.append('ScheduleR physician statement or verified prior-year statement eligibility')
        add(id,vals,fields,gaps)
    onea=s.get('schedule_1a',{})
    if l.get('13b'):
        inp=data['schedule_1a'];magi=onea['magi'];threshold=300000 if status=='mfj' else 150000;excess=max(0,magi-threshold);steps=excess//1000;fields={};gaps=[]
        vals={'1':l['11b'],'2a':0,'2b':0,'2c':0,'2d':0,'2e':0,'3':magi,'38':onea['total']}
        tips=whole(inp['qualified_tips']);overtime=whole(inp['qualified_overtime']);car=whole(inp['qualified_car_loan_interest'])
        if tips:vals.update({'4a':tips,'4b':0,'4c':tips,'5':0,'6':tips,'7':min(25000,tips),'8':magi,'9':threshold,'10':excess,'11':steps,'12':steps*100,'13':onea['qualified_tips_deduction']})
        if overtime:vals.update({'14a':overtime,'14b':0,'14c':overtime,'15':min(overtime,25000 if status=='mfj' else 12500),'16':magi,'17':threshold,'18':excess,'19':steps,'20':steps*100,'21':onea['qualified_overtime_deduction']})
        if car:
            ceiling=200000 if status=='mfj' else 100000;extra=max(0,magi-ceiling);steps=int((D(extra)/1000).to_integral_value(rounding=ROUND_CEILING))
            vals.update({'23':car,'24':min(car,10000),'25':magi,'26':ceiling,'27':extra,'28':steps,'29':steps*200,'30':onea['car_interest_deduction']})
            loans=facts.get('car_loans',[])
            if len(loans)<=2 and sum(whole(x.get('qualified_personal_interest','0')) for x in loans)==car:
                for index,loan in enumerate(loans):
                    if loan.get('facts_confirmed') and re.fullmatch(r'[A-HJ-NPR-Z0-9]{17}',loan.get('vin','')):
                        fields[_short('f1040s1a',2,1+index*3)]=loan['vin'];fields[_short('f1040s1a',2,2+index*3)]=str(whole(loan.get('business_interest','0')));fields[_short('f1040s1a',2,3+index*3)]=str(whole(loan['qualified_personal_interest']))
                    else:gaps.append('Schedule1A loan '+str(index+1)+' verified VIN/interest')
            else:gaps.append('Schedule1A verified car VIN/interest allocation must reconcile entered personal interest')
        if onea['senior_deduction']:
            ceiling=150000 if status=='mfj' else 75000;extra=max(0,magi-ceiling)
            vals.update({'31':magi,'32':ceiling,'33':extra,'34':whole(D(extra)*D('.06')),'35':onea['senior_each'],'36a':onea['senior_each'] if tax_extended.senior_age65(data['taxpayer']) and data['taxpayer']['valid_ssn'] else 0,'36b':onea['senior_each'] if status=='mfj' and tax_extended.senior_age65(data['spouse']) and data['spouse']['valid_ssn'] else 0,'37':onea['senior_deduction']})
        add('f1040s1a',vals,fields,gaps)
    rentals=data.get('rentals',[])
    if rentals:
        rent=s.get('schedule_e',{});props=rent.get('properties',[]);fields={};gaps=[];details=facts.get('rentals',[])
        expense_keys=('advertising','auto_travel','cleaning','commissions','insurance','legal_professional','management_fees','mortgage_interest','other_interest','repairs','supplies','taxes','utilities','depreciation','other_expenses')
        if len(rentals)>3:gaps.append('ScheduleE additional property continuation pages required')
        for index,inp in enumerate(rentals[:3]):
            f=_matched(details,index,'property_name',inp['name']);prop=props[index]
            if not f.get('facts_confirmed',False):gaps.append('ScheduleE property '+str(index+1)+' source facts not yet confirmed')
            for key,n in (('address',3+index),('property_type',6+index),('fair_rental_days',9+index*2),('personal_use_days',10+index*2)):
                if key in f:fields[_short('f1040se',1,n)]=str(f[key])
                else:gaps.append('ScheduleE property '+str(index+1)+' '+key)
            fields[_short('f1040se',1,16+index)]=str(whole(inp['rent']))
            fields[_short('f1040se',1,19+index)]='0'
            for offset,key in enumerate(expense_keys):fields[_short('f1040se',1,22+offset*3+(1 if offset==14 else 0)+index)]=str(whole(inp[key]))
            fields[_short('f1040se',1,68+index)]=str(prop['expenses'])
            fields[_short('f1040se',1,71+index)]=str(prop['current_profit_loss'])
            fields[_short('f1040se',1,74+index)]=str(max(0,-prop['reported_income_loss']))
        vals={'23a':sum(p['rent'] for p in props),'23b':0,'23c':total(rentals,'mortgage_interest'),'23d':total(rentals,'depreciation'),'23e':sum(p['expenses'] for p in props),'24':sum(max(0,p['reported_income_loss']) for p in props),'25':sum(max(0,-p['reported_income_loss']) for p in props),'26':rent.get('income',0)}
        add('f1040se',vals,fields,gaps)
        active=[p for p in props if p['active_allowance_eligible']];other=[p for p in props if not p['active_allowance_eligible']]
        vals=dict(rent.get('form_lines',{}));vals.update({'1a':sum(max(0,p['current_profit_loss']) for p in active),'1b':sum(max(0,-p['current_profit_loss']) for p in active),'1c':sum(p['prior_loss'] for p in active),'2a':sum(max(0,p['current_profit_loss']) for p in other),'2b':sum(max(0,-p['current_profit_loss']) for p in other),'2c':sum(p['prior_loss'] for p in other),'2d':sum(p['overall'] for p in other),'4':min(max(0,-vals.get('1d',0)),max(0,-vals.get('3',0))),'7':max(0,vals.get('5',0)-vals.get('6',0))})
        # IRS parenthesized loss boxes accept magnitude, not a second minus sign.
        pfields={};prior_cols=('current_profit_loss','prior_loss')
        for properties,page,start in ((active,1,20),(other,2,1)):
            for index,prop in enumerate(properties[:5]):
                n=start+index*6
                for offset,value in enumerate((prop['name'],max(0,prop['current_profit_loss']),max(0,-prop['current_profit_loss']),prop['prior_loss'],max(0,prop['overall']),max(0,-prop['overall']))):pfields[_short('f8582',page,n+offset)]=str(value)
            if len(properties)>5:gaps.append('Form8582 additional property continuation required')
        add('f8582',vals,pfields,gaps=['Form8582 allocation worksheets PartsVI-IX required for suspended or mixed passive losses'] if rent.get('suspended_loss_carryout') or len(props)>1 else [])
    adoption=s.get('form_8839',{})
    if adoption.get('form_lines'):
        v=adoption['form_lines'];fields={};gaps=list(adoption.get('blocking_issues',[]));children=v.get('children',[]);details=facts.get('adoption',{}).get('children',[])
        vals={k:value for k,value in v.items() if k not in ('children','9') and re.fullmatch(r'\d+[a-z]?',k)}
        ratio=D(v.get('9','0'));integer=int(ratio);fraction=format(ratio-integer,'.6f').split('.')[1];fields[_short('f8839',1,32)]=str(integer);fields[_short('f8839',1,33)]=fraction
        for index,child in enumerate(children[:3]):
            f=_matched(details,index,'tin',child['tin']);base=3+index*4
            for offset,key in enumerate(('first_name','last_name')):
                if f.get(key):fields[_short('f8839',1,base+offset)]=f[key]
                else:gaps.append('Form8839 child '+str(index+1)+' '+key)
            fields[_short('f8839',1,base+2)]=str(child['birth_year']);fields[_short('f8839',1,base+3)]=child['tin'].replace('-','')
            if not f.get('facts_confirmed'):gaps.append('Form8839 child '+str(index+1)+' identity facts not yet confirmed')
            source_child=data['adoption']['children'][index]
            for offset,key in ((0,'disabled_over_17_confirmed'),(1,'special_needs'),(2,'foreign_child')):
                if source_child.get(key):fields.update(_checkbox('f8839','c1_'+str(1+index*4+offset)+'[0]'))
            if child.get('final_year',9999)<=2025:fields.update(_checkbox('f8839','c1_'+str(4+index*4)+'[0]'))
            for line,n in (('2',15),('3',18),('4',21),('5',24),('6',27),('10',34),('11a',37),('11b',40)):
                if line in child:fields[_short('f8839',1,n+index)]=str(child[line])
        if len(children)>3:gaps.append('Form8839 child continuation pages required')
        fields.update(_checkbox('f8839','c1_14[1]' if v.get('8',0)>0 else 'c1_14[0]'))
        add('f8839',vals,fields,gaps)
    energy=s.get('form_5695',{})
    if energy.get('form_lines'):
        v=energy['form_lines'];fields={};gaps=list(energy.get('blocking_issues',[]));vals={k:value for k,value in v.items() if re.fullmatch(r'\d+[a-z]?',k) and not isinstance(value,(list,dict,bool))};details=facts.get('energy',{});items=energy.get('items',data['energy'].get('items',[]))
        # Separate address components are explicit facts; never parse a free-text
        # address into invented city/state/ZIP values.
        for page,start in ((1,3),(2,3),(3,1)):
            for offset,key in enumerate(('street','apt','city','state','zip')):
                if details.get(key):fields[_short('f5695',page,start+offset)]=details[key]
                elif key!='apt':gaps.append('Form5695 property '+key)
        if not details.get('facts_confirmed'):gaps.append('Form5695 property address facts not yet confirmed')
        if v.get('5b'):fields.update(_checkbox('f5695','c1_1[0]'))
        if v.get('8'):
            fields.update(_checkbox('f5695','c1_2[0]'));capacity=sum(D(str(row.get('fuel_cell_capacity_kw','0'))) for row in items if row['kind']=='fuel_cell');text=format(capacity,'f').split('.')
            fields[_short('f5695',1,22)]=text[0];fields[_short('f5695',1,23)]=text[1] if len(text)>1 else '0'
        if any(v.get(k,0) for k in ('18a','19a','20c')):
            for short in ('c2_1[0]','c2_2[0]','c2_3[0]'):fields.update(_checkbox('f5695',short))
            fields.update(_checkbox('f5695','c2_4[1]'))
        if any(v.get(k,0) for k in ('22c','23c','24c','25c','29g')):
            fields.update(_checkbox('f5695','c3_1[0]'));fields.update(_checkbox('f5695','c3_2[0]'))
        if v.get('25c'):
            fields.update(_checkbox('f5695','c3_4[0]'))
            for i,code in enumerate(v.get('25b',[])[:7]):fields[_short('f5695',3,42+i)]=str(code)
        if v.get('26b'):fields.update(_checkbox('f5695','c4_1[0]'))
        # Most-expensive equipment entries require actual manufacturer QMID;
        # additional-item costs retain the precise original rows.
        for kind,page,cost_n,name_n,qmid_n in (('door',2,10,11,12),('central_ac',3,21,22,23),('furnace_boiler',3,36,37,38),('heat_pump',4,5,6,7),('heat_pump_water_heater',4,9,10,11),('biomass',4,13,14,15)):
            rows=sorted((item for item in items if item['kind']==kind),key=lambda item:D(str(item.get('cost','0'))),reverse=True)
            if rows:
                fields[_short('f5695',page,qmid_n)]=rows[0].get('qmid','')
                if not rows[0].get('qmid'):gaps.append('Form5695 '+kind+' manufacturer QMID')
        for kind,page,start,capacity in (('window',2,26,4),('gas_water_heater',3,28,2)):
            rows=sorted((item for item in items if item['kind']==kind),key=lambda item:D(str(item.get('cost','0'))),reverse=True)
            for i,row in enumerate(rows[:capacity]):
                qn=start+i*3+1;cn=start+i*3+2
                fields[_field_at('f5695',page,qn,130)]=row.get('qmid','');fields[_field_at('f5695',page,cn,346)]=str(whole(row['cost']))
        doors=sorted((item for item in items if item['kind']=='door'),key=lambda item:D(str(item.get('cost','0'))),reverse=True)[1:3]
        for i,row in enumerate(doors):fields[_short('f5695',2,16+i*3)]=row.get('qmid','');fields[_short('f5695',2,17+i*3)]=str(whole(row['cost']))
        add('f5695',vals,fields,gaps)
    penalty=s.get('form_2210',{})
    if penalty.get('form_lines'):
        v=penalty['form_lines'];fields={};vals={k:value for k,value in v.items() if k in ('1','2','3','4','5','6','7','8','9','19')};gaps=list(penalty.get('blocking_issues',[]))
        for line in range(1,10):
            if str(line) in v:fields[_short('f2210',1,line+2)]=str(v[str(line)]);vals.pop(str(line),None)
        for line in range(10,19):
            if str(line) in v:
                for i,value in enumerate(v[str(line)]):fields[_short('f2210',2,(line-10)*4+1+i)]=str(whole(value))
        fields[_short('f2210',2,37)]=str(v.get('19',0));vals.pop('19',None)
        if data['estimated_penalty'].get('withholding_method')=='actual_dates':fields.update(_checkbox('f2210','c1_5[0]'))
        # Annualized-income/waiver AI rows remain blank and blocked by engine.
        add('f2210',vals,fields,gaps)
    foreign=s.get('form_1116',{})
    if foreign.get('method')=='ordinary_passive_1116':
        v=foreign.get('form_lines',{});columns=v.get('countries',[]);fields={};gaps=list(foreign.get('blocking_issues',[]));extra=facts.get('foreign_credit',{})
        vals={k:value for k,value in v.items() if re.fullmatch(r'\d+[a-z]?',k) and not isinstance(value,(dict,list,bool))};fields[_short('f1116',1,7)]='Passive investment interest and dividends';vals['1a']=sum(col['1a'] for col in columns);vals['6']=sum(col['6'] for col in columns)
        for key,meta in MAP['f1116']['fields'].items():
            if meta['type']=='/Btn' and '/3' in meta['states']:fields[key]='/3';break
        fields.update(_checkbox('f1116','c1_3[0]'))
        if extra.get('resident_country'):fields[_short('f1116',1,3)]=extra['resident_country']
        else:gaps.append('Form1116 country of residence')
        if len(columns)>3:gaps.append('Form1116 additional country continuation required')
        for i,col in enumerate(columns[:3]):
            fields[_short('f1116',1,4+i)]=col['country']
            for line,n in (('1a',10),('2',14),('3a',17),('3b',20),('3c',23),('3d',26),('3e',29),('3f',32),('3g',35),('4a',38),('4b',41),('5',44),('6',47)):
                fields[_short('f1116',1,n+i)]=str(col[line])
            base=52+i*10;fields[_short('f1116',1,base)]=col['date'];fields[_short('f1116',1,base+9)]=str(whole(col['tax_paid']))
            details=_matched(extra.get('countries',[]),i,'country',col['country'])
            if details.get('facts_confirmed') and sum(whole(details.get(key,'0')) for key in ('usd_dividend_tax','usd_interest_tax','usd_other_tax'))==whole(col['tax_paid']):
                fields[_short('f1116',1,base+1)]=str(details.get('foreign_currency_dividend_tax','0'));fields[_short('f1116',1,base+2)]='0';fields[_short('f1116',1,base+3)]=str(details.get('foreign_currency_interest_tax','0'));fields[_short('f1116',1,base+4)]=str(details.get('foreign_currency_other_tax','0'));fields[_short('f1116',1,base+5)]=str(details.get('usd_dividend_tax','0'));fields[_short('f1116',1,base+6)]='0';fields[_short('f1116',1,base+7)]=str(details.get('usd_interest_tax','0'));fields[_short('f1116',1,base+8)]=str(details.get('usd_other_tax','0'))
            else:gaps.append('Form1116 '+col['country']+' foreign-currency andUSD tax-by-income reconciliation')
        add('f1116',vals,fields,gaps)
    return specs

def build_official_packet(record):
    """Return filled IRS supporting PDFs plus merged interactive attachment packet.

    forms[].pdf_bytes are useful for per-form download. form_facts may be supplied
    on the record separately from the tax-engine input. It never changes tax math.
    Complete signatures/1040/efile are owned by the calling application.
    """
    specs=official_form_specs(record);instances=[];copy_counts={}
    # Derive expected copies/pages from the supported tax model and pinned IRS
    # templates before asking a renderer to produce anything.
    for spec in specs:
        form_id=spec['form_id'];owner=spec['owner'];source=SOURCES.get(form_id)
        if source is None:raise ValueError('Required packet template is unavailable: '+str(form_id))
        template=(FORMS/source['path']).read_bytes()
        if hashlib.sha256(template).hexdigest()!=source['sha256']:
            raise ValueError('IRS template hash changed: '+form_id)
        pair=(form_id,owner);copy_counts[pair]=copy_counts.get(pair,0)+1
        instances.append(packet_instance(form_id,owner,copy_counts[pair],len(PdfReader(io.BytesIO(template)).pages),source['sha256']))
    manifest=packet_manifest(instances)
    forms=[]
    for spec,instance in zip(specs,instances):
        form=render_official_form(**spec,copy_index=instance['copy_index'])
        if (form.get('id'),form.get('owner'),form.get('copy_index'),form.get('tax_year'))!=(instance['form_id'],instance['owner'],instance['copy_index'],2025):
            raise ValueError('Rendered packet copy does not match required form/owner/copy/year')
        if form.get('status') not in ('draft_incomplete','draft_facts_present'):
            raise ValueError('Required packet form did not produce a draft: '+instance['form_id'])
        if form.get('packet_instance')!=instance or form.get('template_sha256')!=instance['template_sha256']:
            raise ValueError('Rendered packet copy does not match the pinned template plan')
        verify_packet_pages(form['pdf_bytes'],packet_manifest([instance]))
        forms.append(form)
    writer=PdfWriter();expected={};missing=list(record['result'].get('blocking_issues',[]))
    for index,form in enumerate(forms):
        reader=PdfReader(io.BytesIO(form['pdf_bytes']));prefix=form['id']+'_'+str(index)
        reader.add_form_topname(prefix);writer.append(reader)
        expected.update({prefix+'.'+key:value for key,value in form['values'].items()});missing+=form['missing_facts']
    raw=b'';proof={'pages':0,'verified_fields':0,'interactive':True}
    if forms:
        writer.add_metadata({'/TaxRebornPacketManifest':json.dumps(manifest,separators=(',',':'))})
        target=io.BytesIO();writer.write(target);raw=target.getvalue();proof=verify_official_pdf(raw,expected)
    proof['packet_preflight']=verify_packet_pages(raw,manifest)
    return {'status':'draft_incomplete' if missing else 'draft_facts_present','tax_year':2025,'forms':forms,'missing_facts':list(dict.fromkeys(missing)),'pdf_bytes':raw,'verification':proof,'packet_manifest':manifest,'supporting_forms_complete':not missing,'requires_taxpayer_signature':True,'filing_packet_ready':False,'electronic_filing':False}
