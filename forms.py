"""Interactive IRS 2025 Form1040 calculation draft, with field readback checks.

Provided identity text is printed; signatures and bank details remain blank. Supporting schedules are represented
in the calculation trail, not fabricated as a complete paper-filing package.
"""
from __future__ import annotations
import io
import json
from pathlib import Path
import sys
import textwrap

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
        if key.startswith('spouse_') and record['result']['filing_status'] not in ('mfj','mfs'):
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
        content += ['0.72 0.2 0.12 rg','BT /F1 7 Tf 36 6 Td (DRAFT - NOT FILED - SUPPORTING FORM SET AND SIGNATURE INCOMPLETE) Tj ET']
    content += ['Q']
    stream.set_data('\n'.join(content).encode('ascii'))
    page[NameObject('/Contents')] = stream
    return page


def verify_fields(raw, expected):
    reader = PdfReader(io.BytesIO(raw))
    fields = reader.get_fields() or {}
    for key, value in expected.items():
        if key not in fields or str(fields[key].get('/V', '')) != value:
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
            if str(actual) != expected[key] or not appearance or not appearance.get_object().get_data():
                raise ValueError('Form1040 widget appearance/value did not save: ' + key)
            seen.add(key)
    if seen != set(expected):
        raise ValueError('Some numeric fields lack a matching page widget')
    return {'pages':len(reader.pages),'verified_fields':len(expected),'interactive':True}


def form1040_pdf(record):
    reader = PdfReader(TEMPLATE)
    if len(reader.pages) != 2 or '2025' not in reader.pages[0].extract_text():
        raise ValueError('IRS Form1040 template is not the verified tax year2025 form')
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    values = {**field_values(record['result']), **identity_values(record)}
    fields = writer.get_fields() or {}
    if set(values) - set(fields):
        raise ValueError('The official IRS Form1040 field layout changed')
    # Only unique numeric fields are edited. We don't reattach or mutate the
    # template's repeated checkbox fields with ambiguous canonical identities.
    writer.update_page_form_field_values(None, values, auto_regenerate=False)
    for page in writer.pages:
        page.merge_page(_text_page([], title='', watermark=True))
    result = record['result']
    cover = ['Tax Reborn - US resident federal tax year2025. Currency: USD.',
             'Return: '+str(record['data'].get('name','Untitled')),
             'Filing status for this calculation: '+result['filing_status'],
             'Saved: '+record['updated_at'],
             'This PDF contains a cover sheet and an interactive official IRS Form1040 with computed numeric lines.',
             'Provided taxpayer identity text is printed locally. Filing-status checkbox, direct-deposit details and signatures remain blank.',
             'Supporting schedules/form attachments are NOT included as a complete filing packet. Use the detailed calculation worksheet.',
             'This is not submitted to IRS and is not ready to sign or mail. State calculation drafts are prepared separately. Electronic filing is not implemented.',
             'Form1040 line38 (estimated-tax penalty) has not been calculated and remains blank.',
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
