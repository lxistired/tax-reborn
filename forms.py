"""TY2025 official Form1040 and supporting paper-preparation packet.

Actual identity/choices and computed amounts are verified after serialization.
The taxpayer signs the printed return; this module never transmits a return.
"""
from __future__ import annotations
import io
import json
from pathlib import Path
import sys
import textwrap
import tax_filing
import tax_extended

from pypdf import PdfReader, PdfWriter, PageObject
from pypdf.generic import (ArrayObject, DictionaryObject, DecodedStreamObject,
                           NameObject, NumberObject)

BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
TEMPLATE = BASE / 'forms' / 'f1040-2025.pdf'
PAGE1 = {'1a':47,'2a':58,'2b':59,'3a':60,'3b':61,'4a':62,'4b':63,'5a':65,'5b':66,
         '6a':68,'6b':69,'7a':70,'8':72,'9':73,'10':74,'11a':75}
PAGE2 = {'11b':1,'12e':2,'13a':3,'13b':4,'14':5,'15':6,'16':8,'17':9,'18':10,'19':11,
         '20':12,'21':13,'22':14,'23':15,'24':16,'25a':17,'25b':18,'25c':19,'25d':20,
         '26':21,'27a':23,'28':24,'29':25,'30':26,'31':27,'32':28,'33':29,'34':30,
         '35a':31,'36':34,'37':35,'38':36}


def identity_values(record):
    identity = record['data'].get('identity', {})
    names = {'last_name':15,'ssn':16,'spouse_last_name':18,'spouse_ssn':19,'address':20,'apt':21,'city':22,'state':23,'zip':24,'foreign_country':25,'foreign_province':26,'foreign_postal_code':27}
    values = {}
    for key, number in names.items():
        if key.startswith('spouse_') and (record['result']['filing_status'] not in ('mfj','mfs') or record['result']['filing_status']=='mfs' and key=='spouse_last_name'):
            continue
        value = identity.get(key, '')
        if key.endswith('ssn') and value:
            value = str(value).replace('-', '').replace(' ', '')
            if not value.isdigit() or len(value) != 9: raise ValueError('Form identity SSN/ITIN must contain 9 digits')
        if value:
            prefix = 'Address_ReadOrder[0].' if number >= 20 else ''
            values[f'topmostSubform[0].Page1[0].{prefix}f1_{number:02d}[0]'] = str(value)
    for number, prefix in ((14,''),(17,'spouse_')):
        if prefix and record['result']['filing_status'] != 'mfj': continue
        value = ' '.join(str(identity.get(prefix+key,'')) for key in ('first_name','middle_initial')).strip()
        if value: values[f'topmostSubform[0].Page1[0].f1_{number:02d}[0]'] = value
    return values


def filing_values(record):
    data=record['data'];status=record['result']['filing_status']
    identity=data.get('identity',{});facts={**tax_filing.DEFAULTS,**data.get('filing_details',{})}
    p1='topmostSubform[0].Page1[0].';p2='topmostSubform[0].Page2[0].';values={}
    statuses={'single':('Checkbox_ReadOrder[0].c1_8[0]','/1'), 'mfj':('Checkbox_ReadOrder[0].c1_8[1]','/2'),
              'mfs':('Checkbox_ReadOrder[0].c1_8[2]','/3'), 'hoh':('c1_8[0]','/4'), 'qss':('c1_8[1]','/5')}
    for name,state in statuses.values():values[p1+name]=NameObject('/Off')
    name,state=statuses[status];values[p1+name]=NameObject(state)
    def checked(prefix,short,condition,state='/1'):
        values[prefix+short]=NameObject(state if condition else '/Off')
    checked(p1,'c1_5[0]',facts['main_home_us_answer']=='yes')
    checked(p1,'c1_6[0]',facts['presidential_taxpayer'])
    checked(p1,'c1_7[0]',facts['presidential_spouse'] and status=='mfj')
    for answer,index,state in [('yes',0,'/1'),('no',1,'/2')]:checked(p1,f'c1_10[{index}]',facts['digital_asset_answer']==answer,state)
    if status=='mfs':values[p1+'Checkbox_ReadOrder[0].f1_28[0]']=' '.join(identity.get('spouse_'+k,'') for k in ('first_name','middle_initial','last_name') if identity.get('spouse_'+k,''))
    if status in ('hoh','qss'):values[p1+'f1_29[0]']=facts['hoh_qss_non_dependent_child_name']
    for index,row in enumerate(data.get('dependents',[])[:4]):
        for offset,key in enumerate(('form_first_name','form_last_name','form_ssn','relationship')):
            value=str(row.get(key,''));value=value.replace('-','') if key=='form_ssn' else value
            if key=='form_ssn' and value and (not value.isdigit() or len(value)!=9):raise ValueError('Dependent SSN/ITIN must contain exactly9digits')
            # IRS Row1..4 are first-name/last-name/SSN/relationship rows;
            # each row contains four dependent columns.
            values[p1+f'Table_Dependents[0].Row{offset+1}[0].f1_{31+offset*4+index}[0]']=value
        prefix=p1+f'Table_Dependents[0].Row5[0].Dependent{index+1}[0].'
        checked(prefix,f'c1_{12+index*2}[0]',row.get('lived_with_taxpayer_more_than_half_year',False))
        checked(prefix,f'c1_{13+index*2}[0]',row.get('us_home_more_than_half_year',False))
        prefix=p1+f'Table_Dependents[0].Row6[0].Dependent{index+1}[0].'
        checked(prefix,f'c1_{20+index*2}[0]',row.get('eitc_full_time_student',False))
        checked(prefix,f'c1_{21+index*2}[0]',row.get('permanently_disabled',False))
        prefix=p1+f'Table_Dependents[0].Row7[0].Dependent{index+1}[0].'
        eligible=row.get('eligibility_confirmed',False)
        ctc=eligible and row.get('qualifying_child',False) and row.get('age',99)<17 and row.get('valid_ssn',False)
        odc=eligible and not ctc and row.get('valid_tin',False)
        checked(prefix,f'c1_{28+index}[0]',ctc,'/1');checked(prefix,f'c1_{28+index}[1]',odc,'/2')
    checked(p1,'Dependents_ReadOrder[0].c1_11[0]',len(data.get('dependents',[]))>4)
    for owner,offset in [('taxpayer',0),('spouse',2)]:
        person=data.get(owner,{})
        active=owner=='taxpayer' or status=='mfj'
        checked(p2,f'c2_{5+offset}[0]',active and tax_extended.senior_age65(person))
        checked(p2,f'c2_{6+offset}[0]',active and person.get('blind',False))
    checked(p2,'c2_9[0]',record['result'].get('schedules',{}).get('form_8814',{}).get('elected_child_count',0)>0)
    checked(p2,'c2_1[0]',data.get('taxpayer',{}).get('can_be_claimed',False))
    checked(p2,'c2_2[0]',status in ('mfj','mfs') and data.get('spouse',{}).get('can_be_claimed',False))
    checked(p2,'c2_3[0]',status=='mfs' and data.get('eligibility',{}).get('mfs_spouse_itemizes',False))
    eic=record['result'].get('schedules',{}).get('schedule_eic',{})
    checked(p2,'c2_13[0]',any('No-child EITC age25-through64 test is not met.'==reason for reason in eic.get('ineligible_reasons',[])))
    deposit=facts['refund_delivery']=='direct_deposit' and record['result']['summary']['refund']>0
    if deposit:
        if not tax_filing.routing_valid(facts['bank_routing']) or not facts['bank_account'] or facts['bank_type']=='unanswered':raise ValueError('Complete and verify the direct-deposit routing/account/type before PDF export')
        values[p2+'RoutingNo[0].f2_32[0]']=facts['bank_routing'];values[p2+'AccountNo[0].f2_33[0]']=facts['bank_account']
    checked(p2,'c2_16[0]',deposit and facts['bank_type']=='checking','/1')
    checked(p2,'c2_16[1]',deposit and facts['bank_type']=='savings','/2')
    checked(p2,'c2_17[0]',facts['designee_yes'],'/1');checked(p2,'c2_17[1]',not facts['designee_yes'],'/2')
    if facts['designee_yes']:
        for n,key in [(37,'designee_name'),(38,'designee_phone'),(39,'designee_pin')]:values[p2+f'f2_{n}[0]']=facts[key]
    for n,key in [(40,'occupation'),(42,'spouse_occupation'),(44,'phone'),(45,'email')]:
        if key.startswith('spouse_') and status!='mfj':continue
        if identity.get(key):values[p2+f'f2_{n}[0]']=identity[key]
    return values


def field_values(result):
    values = {}
    for page, mapping in ((1, PAGE1), (2, PAGE2)):
        for line, field in mapping.items():
            if line in result.get('not_computed_lines', []):
                continue
            value = result['lines'].get(line, 0)
            if type(value) is not int:
                raise ValueError('PDF Form1040 values must be whole-dollar integers')
            values[f'topmostSubform[0].Page{page}[0].f{page}_{field:02d}[0]'] = str(value)
    # Supported wage scenarios only contain box1 wages; every other wage subline
    # is outside the supported scope and would already produce a blocking issue.
    values['topmostSubform[0].Page1[0].f1_51[0]'] = str(result.get('additional_lines', {}).get('1e', 0))
    values['topmostSubform[0].Page1[0].f1_55[0]'] = str(result.get('additional_lines', {}).get('1h', 0))
    if result.get('additional_lines', {}).get('1h', 0): values['topmostSubform[0].Page1[0].f1_54[0]'] = 'Disability before retirement age'
    values['topmostSubform[0].Page1[0].f1_57[0]'] = str(result.get('additional_lines', {}).get('1z', result['lines'].get('1a', 0)))
    return values


def _text_page(lines, title='CALCULATION DRAFT', watermark=False):
    page = PageObject.create_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
    def literal(text):
        return str(text).encode('ascii','replace').decode().replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
    stream = DecodedStreamObject()
    content = ['q','0.62 0.15 0.05 rg','BT /F1 15 Tf 36 760 Td ('+literal(title)+') Tj ET','0 0 0 rg']
    y = 726
    for line in lines:
        for part in textwrap.wrap(str(line), 100) or ['']:
            content.append(f'BT /F1 9 Tf 36 {y} Td ({literal(part)}) Tj ET')
            y -= 13
    if watermark:
        content += ['0.72 0.2 0.12 rg','BT /F1 7 Tf 36 6 Td (TAX REBORN DRAFT - NOT FILED - REVIEW FACTS, SIGNATURE AND REQUIRED ORIGINAL ATTACHMENTS) Tj ET']
    content += ['Q']
    stream.set_data('\n'.join(content).encode('ascii'))
    page[NameObject('/Contents')] = stream
    return page


def verify_fields(raw, expected):
    reader = PdfReader(io.BytesIO(raw))
    fields = reader.get_fields() or {}
    for key, value in expected.items():
        if key not in fields or str(fields[key].get('/V', '')) != str(value):
            raise ValueError('Form1040 canonical field did not save: ' + key)
    seen = set()
    for page in reader.pages:
        for ref in page.get('/Annots', []):
            obj = ref.get_object()
            if obj.get('/Subtype') != '/Widget':
                continue
            names = [str(obj.get('/T', ''))]
            parent = obj.get('/Parent')
            effective = obj
            while parent:
                effective = parent.get_object()
                names.insert(0, str(effective.get('/T', '')))
                parent = effective.get('/Parent')
            key = '.'.join(n for n in names if n)
            if key not in expected:
                continue
            actual = obj.get('/V')
            cursor = obj
            while actual is None and cursor.get('/Parent'):
                cursor = cursor['/Parent'].get_object()
                actual = cursor.get('/V')
            appearance = obj.get('/AP', {}).get('/N')
            if str(actual) != str(expected[key]):
                raise ValueError('Form1040 widget appearance/value did not save: ' + key)
            field_type=obj.get('/FT',cursor.get('/FT'))
            if field_type=='/Btn':
                state=obj.get('/AS')
                if str(state)!=str(expected[key]) or (str(state)!='/Off' and (not appearance or state not in appearance.get_object() or not appearance.get_object()[state].get_object().get_data())):
                    raise ValueError('Form1040 checkbox appearance did not save: '+key)
            elif not appearance or not appearance.get_object().get_data():
                raise ValueError('Form1040 text appearance did not save: '+key)
            seen.add(key)
    if seen != set(expected):
        raise ValueError('Some Form1040 fields lack a matching page widget')
    return {'pages':len(reader.pages),'verified_fields':len(expected),'interactive':True}


def _official_1040(record):
    reader = PdfReader(TEMPLATE)
    if len(reader.pages) != 2 or '2025' not in reader.pages[0].extract_text():
        raise ValueError('IRS Form1040 template is not the verified tax year2025 form')
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    values = {**field_values(record['result']), **identity_values(record), **filing_values(record)}
    fields = writer.get_fields() or {}
    if set(values) - set(fields):
        raise ValueError('The official IRS Form1040 field layout changed')
    writer.update_page_form_field_values(None, values, auto_regenerate=False)
    for page in writer.pages:
        page.merge_page(_text_page([], title='', watermark=True))
    target=io.BytesIO();writer.write(target);raw=target.getvalue()
    verify_fields(raw,values)
    return raw,values


def form1040_pdf(record):
    raw,values=_official_1040(record)
    writer=PdfWriter();writer.clone_document_from_reader(PdfReader(io.BytesIO(raw)))
    result = record['result']
    cover = ['Tax Reborn - US resident federal tax year2025. Currency: USD.',
             'Return: '+str(record['data'].get('name','Untitled')),
             'Filing status for this calculation: '+result['filing_status'],
             'Saved: '+record.get('updated_at','Local draft'),
             'This PDF contains a cover sheet and an interactive official IRS Form1040 with computed numeric lines.',
             'Provided identity, filing-status/dependent boxes, deposit and designee choices are printed locally. Signatures are completed by the taxpayer on paper.',
             'This export includes calculation workpapers. Use the separate official paper packet for filled IRS supporting forms.',
             'Not transmitted to IRS. Review the paper-packet checklist before signing. State drafts are separate.',
             'Form1040 line38: '+('not computed; review penalty applicability' if '38' in result.get('not_computed_lines',[]) else str(result['lines'].get('38',0))),
             'Supported calculation review: '+('passed required confirmations' if result['can_prepare'] else 'blocked; resolve the items below'),
             'AGI: '+str(result['summary']['agi'])+'; taxable income: '+str(result['summary']['taxable_income'])+'; total tax: '+str(result['summary']['total_tax']),
             'Payments: '+str(result['summary']['payments'])+'; refund: '+str(result['summary']['refund'])+'; amount owed: '+str(result['summary']['amount_owed']),
             'Applicable worksheets: '+', '.join(result['summary'].get('schedules',[])),
             'Blocking issues:'] + result.get('blocking_issues', [])[:15]
    writer.insert_page(_text_page(cover),0)
    # Add printable calculation workpapers with actual schedule outputs. They are
    # explicitly not official filled supporting forms or a complete filing packet.
    schedules = result.get('schedules', {})
    if isinstance(schedules, dict):
        for name, schedule_values in schedules.items():
            text = json.dumps(schedule_values, indent=2, ensure_ascii=True).splitlines()
            for offset in range(0, len(text), 42):
                writer.add_page(_text_page(['Tax year2025. Actual engine output; not an official filed supporting form.'] + text[offset:offset+42], title='CALCULATION WORKPAPER - '+str(name)))
    writer.add_metadata({'/Title':'Tax Reborn 2025 Form1040 calculation DRAFT','/Author':'lxistired','/Subject':'Numeric calculation draft; not filed and not a complete filing packet'})
    target = io.BytesIO()
    writer.write(target)
    raw = target.getvalue()
    verify_fields(raw, values)
    return raw


def packet_status(record,support=None):
    import official_forms
    import tax_engine
    data=tax_engine.normalized(record['data']);result=record['result']
    support=support if support is not None else official_forms.build_official_packet(record)
    preflight=official_forms.verify_packet_pages(support['pdf_bytes'],support['packet_manifest'])
    readiness=tax_filing.paper_facts_readiness(data)
    missing=list(result.get('blocking_issues',[]))+list(result.get('form_readiness',{}).get('missing_identity',[]))+readiness['missing_paper_facts']+support['missing_facts']
    if result['lines'].get('27a') and any(r.get('eitc_qualifying_child') for r in data.get('dependents',[])):missing.append('Schedule EIC qualifying-child attachment is not yet generated')
    if len(data.get('dependents',[]))>4:missing.append('More-than-four-dependent continuation attachment is not yet generated')
    missing=list(dict.fromkeys(missing))
    return {'tax_year':2025,'status':'needs_facts' if missing else 'ready_to_print_and_review','missing_facts':missing,
            'calculation_ready':bool(result.get('can_prepare')),'paper_preparation_complete':not missing,
            'supporting_forms':[{'id':f['id'],'owner':f['owner'],'copy_index':f['copy_index'],'pages':len(f['packet_instance']['required_pages']),'missing_facts':f['missing_facts']} for f in support['forms']],
            'supporting_packet_preflight':preflight,'supporting_packet_manifest':support['packet_manifest'],
            'requires_taxpayer_signature':True,'requires_original_withholding_attachments':bool(data.get('w2') or result['lines'].get('25b')),
            'penalty_applicability_review_required':'38' in result.get('not_computed_lines',[]),
            'electronic_filing':False,'transmitted':False,'filing_packet_ready':False}


def paper_packet_pdf(record):
    import official_forms
    support=official_forms.build_official_packet(record);status=packet_status(record,support)
    raw,values=_official_1040(record)
    writer=PdfWriter();writer.clone_document_from_reader(PdfReader(io.BytesIO(raw)))
    main_instance=official_forms.packet_instance('f1040','taxpayer',1,2)
    official_forms.stamp_packet_pages(writer.pages,main_instance)
    expected=dict(values)
    if support['pdf_bytes']:
        reader=PdfReader(io.BytesIO(support['pdf_bytes']));writer.append(reader)
        for index,form in enumerate(support['forms']):expected.update({form['id']+'_'+str(index)+'.'+k:v for k,v in form['values'].items()})
    lines=['Tax Reborn - official IRS TY2025 paper-preparation packet. Currency: USD.',
           'Return: '+str(record['data'].get('name','Untitled')),
           'Preparation: '+status['status'], 'This packet has not been transmitted. Review each page, sign the Form1040 yourself, and attach original required withholding documents.',
           'Filled supporting forms: '+(', '.join(f['id'] for f in support['forms']) or 'None required by these entered amounts.'),
           'Penalty applicability review: '+('required; line38 was not computed.' if status['penalty_applicability_review_required'] else 'computed from entered penalty facts.'),
           'Missing facts / blocked situations:']+(status['missing_facts'] or ['None identified within the supported paper-preparation scope.'])
    special=record['result'].get('schedules',{}).get('schedule_d_tax_worksheet')
    if special:
        lines+=['', 'TY2025 SCHEDULE D TAX WORKSHEET - INDEPENDENT CALCULATION WORKPAPER',
                'Source: https://www.irs.gov/pub/irs-pdf/i1040sd.pdf, pages15-16.',
                'Retain this workpaper with the source1099-DIV statements. It supports the filled ScheduleD18/19 and Form1040line16.']
        lines+=['Worksheet line '+str(number)+': $'+format(special['form_lines'][str(number)],',') for number in range(1,48)]
        lines+=['Special-rate distribution calculation is complete only within the stated supported profile; missing facts and unsupported AMT basis differences are listed above.']
    amt=record['result'].get('schedules',{}).get('form_6251',{})
    if amt.get('special_distribution_full_partIII'):
        lines+=['', 'TY2025 FORM6251 PARTIII - SPECIAL DISTRIBUTION AMT WORKPAPER',
                'Source: https://www.irs.gov/pub/irs-pdf/f6251.pdf, page2.',
                'Same regular/AMT capital basis. This workpaper supports the filled official Form6251 and Schedule2 line2.']
        lines+=['Form6251 line '+str(number)+': $'+format(amt['form_lines'][str(number)],',') for number in range(12,41)]
        lines+=['Tentative minimum tax: $'+format(amt['form_lines']['9'],','),
                'Regular tax comparator: $'+format(amt['form_lines']['10'],','),
                'AMT liability: $'+format(amt['tax'],',')]
    cover_pages=[]
    for offset in range(len(lines)-1,-1,-42):
        start=max(0,offset-41);cover_pages.append(_text_page(lines[start:offset+1],title='PAPER PREPARATION CHECKLIST'))
    cover_pages.reverse()
    cover_instance=official_forms.packet_instance('preparation_checklist','packet',1,len(cover_pages))
    official_forms.stamp_packet_pages(cover_pages,cover_instance)
    for page in reversed(cover_pages):writer.insert_page(page,0)
    manifest=official_forms.packet_manifest([cover_instance,main_instance]+support['packet_manifest']['instances'])
    writer.add_metadata({'/Title':'Tax Reborn 2025 official paper-preparation draft','/Author':'lxistired','/Subject':'Filled official IRS forms; taxpayer review/signature required; not transmitted',
                         '/TaxRebornPacketManifest':json.dumps(manifest,separators=(',',':'))})
    target=io.BytesIO();writer.write(target);output=target.getvalue()
    verify_fields(output,expected)
    official_forms.verify_packet_pages(output,manifest)
    return output


def masked_review_pdf(record):
    from privacy_review import form1040_review
    return form1040_review(record)
