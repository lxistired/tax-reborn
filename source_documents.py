"""Strict local source references and immutable TaxML import snapshots.

No vendor code, keys or personal data are used by these validators.
"""
from decimal import Decimal
import re

ID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
HASH = re.compile(r'^[0-9a-f]{64}$')
INTEREST_BOXES = ('interest_income', 'treasury_interest', 'tax_exempt_interest', 'federal_withholding')


def taxml_receipt(value):
    keys = {'source_sha256', 'wire_profile_sha256', 'template_carrier_sha256',
            'template_resource_id', 'form_path', 'archive_member', 'candidate_sha256'}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError('Invalid TaxML source receipt')
    for key in ('source_sha256', 'wire_profile_sha256', 'template_carrier_sha256', 'candidate_sha256'):
        if not isinstance(value[key], str) or not HASH.fullmatch(value[key]):
            raise ValueError('Invalid TaxML source hash')
    if type(value['template_resource_id']) is not int or not 0 <= value['template_resource_id'] <= 65535:
        raise ValueError('Invalid TaxML template resource identifier')
    if not isinstance(value['form_path'], str) or not re.fullmatch(r'\d{1,6}(?:/\d{1,6}){1,2}', value['form_path']):
        raise ValueError('Invalid TaxML form identity')
    member = value['archive_member']
    if member is not None and (not isinstance(member, str) or not member or len(member) > 1024 or re.search(r'[\x00-\x1f\x7f]', member)):
        raise ValueError('Invalid TaxML archive member identity')
    return dict(value)


def source_document(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {'document_id', 'return_id', 'name', 'method', 'taxml_receipt'}:
        raise ValueError('Invalid local source-document reference')
    for key in ('document_id', 'return_id'):
        if not isinstance(value.get(key), str) or not ID.fullmatch(value[key]):
            raise ValueError('Invalid local source-document identifier')
    name = value.get('name', '')
    if not isinstance(name, str) or len(name) > 256 or re.search(r'[\x00-\x1f\x7f]', name):
        raise ValueError('Invalid local source-document name')
    if value.get('method') not in ('ocr', 'manual', 'taxml'):
        raise ValueError('Invalid local source-document method')
    output = {'document_id': value['document_id'], 'return_id': value['return_id'],
              'name': name, 'method': value['method']}
    if value['method'] == 'taxml':
        output['taxml_receipt'] = taxml_receipt(value.get('taxml_receipt'))
    elif 'taxml_receipt' in value:
        raise ValueError('TaxML source receipt requires the TaxML method')
    return output


def interest_boxes(value):
    if not isinstance(value, dict) or set(value) != set(INTEREST_BOXES):
        raise ValueError('TaxML interest snapshot requires exactly Boxes 1, 3, 8 and 4')
    output = {}
    for name, text in value.items():
        if not isinstance(text, str) or not re.fullmatch(r'[0-9]{1,13}(?:\.[0-9]{1,2})?', text) or Decimal(text) > 1000000000:
            raise ValueError('TaxML interest snapshot requires explicit nonnegative USD amounts')
        output[name] = format(Decimal(text), '.2f')
    return output
