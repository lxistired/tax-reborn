"""Independent, explicit Form 1040 identifier masking for a review copy.

Build from the blank IRS template. Never reuse a filled PDF or return backup.
This is a scoped review export, not a general PII scrubber or filing packet.
"""
import io
import re
from pypdf import PdfReader, PdfWriter, PageObject
from pypdf.generic import IndirectObject, DictionaryObject, NameObject, DecodedStreamObject


def identifier_fields():
    p1 = 'topmostSubform[0].Page1[0].'
    p2 = 'topmostSubform[0].Page2[0].'
    return {p1+'f1_16[0]', p1+'f1_19[0]',
            *(p1+f'Table_Dependents[0].Row3[0].f1_{39+i}[0]' for i in range(4)),
            p2+'RoutingNo[0].f2_32[0]', p2+'AccountNo[0].f2_33[0]'}


def tokens(values):
    found = set()
    for key in identifier_fields():
        value = str(values.get(key, ''))
        if value:
            found.add(value)
            if len(value) == 9 and value.isdigit():
                found.add(value[:3]+'-'+value[3:5]+'-'+value[5:])
    return found


def verify_no_identifiers(raw, forbidden):
    """Fail closed if a selected identifier survives in another output surface."""
    reader = PdfReader(io.BytesIO(raw))
    surfaces = [str(reader.metadata or {}), *(page.extract_text() or '' for page in reader.pages)]
    surfaces.extend(str(field.get('/V', '')) for field in (reader.get_fields() or {}).values())
    objects = {(number, generation) for generation, table in reader.xref.items()
               for number in table if number}
    objects.update((number, 0) for number in reader.xref_objStm)
    streams = []
    for number, generation in objects:
        obj = reader.get_object(IndirectObject(number, generation, reader))
        if hasattr(obj, 'get_data'):
            streams.append(obj.get_data())
    for token in forbidden:
        # Numeric word boundaries avoid treating an unrelated larger value as
        # this identifier. Any exact occurrence outside the mask is refused.
        pattern = re.compile(r'(?<!\d)'+re.escape(token)+r'(?!\d)')
        if any(pattern.search(text) for text in surfaces):
            raise ValueError('A selected identifier also appears outside its masked fields; review-copy export refused')
        encodings = (token.encode(), token.encode('utf-16-be'))
        if any(encoded in stream or encoded.hex().encode() in stream.lower()
               for stream in streams for encoded in encodings):
            raise ValueError('A selected identifier remains in a PDF stream; review-copy export refused')
    return {'selected_identifiers_absent': True, 'decoded_streams_checked': len(streams),
            'fields_checked': len(reader.get_fields() or {}), 'pages': len(reader.pages)}


def form1040_review(record):
    import forms
    values = {**forms.field_values(record['result']), **forms.identity_values(record),
              **forms.filing_values(record)}
    forbidden = tokens(values)
    masked = dict(values)
    for key in identifier_fields():
        if key in masked:
            # Equivalent to the observed default ALL character replacement.
            # Existing source validation rejects malformed identifiers first.
            masked[key] = re.sub('.', '*', str(masked[key]))
    template = PdfReader(forms.TEMPLATE)
    if len(template.pages) != 2 or '2025' not in template.pages[0].extract_text():
        raise ValueError('Verified IRS 2025 Form 1040 template required')
    writer = PdfWriter(); writer.clone_document_from_reader(template)
    if set(masked) - set(writer.get_fields() or {}):
        raise ValueError('Official identifier field layout differs')
    writer.update_page_form_field_values(None, masked, auto_regenerate=False)
    for page in writer.pages:
        width = float(page.mediabox.right); height = float(page.mediabox.top)
        page.mediabox.upper_right = (width, height+18)
        page.cropbox.upper_right = (width, height+18)
        banner = PageObject.create_blank_page(width=width, height=height+18)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        banner[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        stream = DecodedStreamObject()
        stream.set_data(f'q 0.6 0.12 0.05 rg BT /F1 8 Tf 0 Tr 0 Tc 0 Tw 100 Tz 1 0 0 1 36 {height+6} Tm (MASKED IDENTIFIERS - REVIEW COPY - NOT FOR FILING) Tj ET Q'.encode())
        banner[NameObject('/Contents')] = stream
        page.merge_page(banner)
    writer.insert_page(forms._text_page([
        'Tax Reborn - IRS 2025 Form 1040 review copy. Currency: USD.',
        'Taxpayer, spouse and dependent SSN/ITIN fields and refund routing/account numbers are masked.',
        'Names, addresses, contact details and financial amounts remain visible.',
        'This is an identifier-masked review copy. It is not a filing packet.',
        'The saved return and its ordinary exports are unchanged.',
    ], title='MASKED IDENTIFIERS - REVIEW COPY'), 0)
    writer.add_metadata({'/Title': 'Tax Reborn 2025 masked-identifier review copy',
                         '/Subject': 'Review only; Form 1040 identifiers masked; not filed'})
    target = io.BytesIO(); writer.write(target); raw = target.getvalue()
    forms.verify_fields(raw, masked)
    verify_no_identifiers(raw, forbidden)
    return raw
