"""Local preparation state, deliberately outside the frozen federal input schema.

Reviewed means the user checked this W-2, not that a return was filed or certified.
The fingerprint covers normalized cents and ownership; it never changes tax math.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import hashlib
import json
import re
import uuid
import investment_metadata
import income_preparation

ID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
HASH = re.compile(r'^[0-9a-f]{64}$')
AMOUNT = re.compile(r'^-?\d+(?:\.\d{1,2})?$')
MONEY_FIELDS = frozenset(('wages', 'federal_withholding', 'social_security_wages',
    'social_security_withholding', 'medicare_wages', 'medicare_withholding',
    'social_security_tips', 'dependent_care_benefits'))


def canonical_w2(row, defaults):
    if not isinstance(row, dict):
        raise ValueError('Expected a W-2 record')
    value = {**defaults, **row}
    for key in MONEY_FIELDS:
        text = str(value.get(key, '0')).strip() or '0'
        if not AMOUNT.fullmatch(text):
            raise ValueError('W-2 review requires valid USD amounts with at most two decimal places')
        amount = Decimal(text)
        value[key] = '0.00' if amount == 0 else format(amount, '.2f')
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(row, defaults):
    return hashlib.sha256(canonical_w2(row, defaults).encode('utf-8')).hexdigest()


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
    if not isinstance(value['form_path'], str) or not re.fullmatch(r'\d{1,6}/\d{1,6}', value['form_path']):
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


def normalize(data, provided, defaults, previous=None):
    """Validate explicit aligned metadata, or migrate a legacy record conservatively.

    Explicit record IDs let callers reorder/delete identical W-2s correctly.
    Legacy clients without metadata only retain identity for unique exact matches.
    They cannot assert that an ambiguous duplicate is already reviewed.
    """
    rows = data.get('w2', [])
    if not isinstance(rows, list) or len(rows) > 1000:
        raise ValueError('Invalid W-2 preparation record collection')
    explicit = provided is not None
    if explicit:
        if not isinstance(provided, dict) or set(provided) - {'version', 'w2_records', 'investment_records', 'income_document_records', 'income_import_events'} or provided.get('version') != 1:
            raise ValueError('Unsupported local preparation metadata')
        entries = provided.get('w2_records')
        if not isinstance(entries, list) or len(entries) != len(rows):
            raise ValueError('W-2 preparation records must match the W-2 collection')
    else:
        old = previous.get('w2_records', []) if isinstance(previous, dict) else []
        by_hash = {}
        for item in old:
            by_hash.setdefault(item.get('row_fingerprint'), []).append(item)
        current_hashes = [fingerprint(row, defaults) for row in rows]
        entries = []
        for current_hash in current_hashes:
            matches = by_hash.get(current_hash, [])
            entries.append(matches[0] if len(matches) == 1 and current_hashes.count(current_hash) == 1 else {})
    output, seen = [], set()
    previous_sources = {entry.get('record_id'): entry.get('source_document')
        for entry in (previous or {}).get('w2_records', [])}
    for row, item in zip(rows, entries):
        if not isinstance(item, dict) or set(item) - {'record_id', 'row_fingerprint', 'reviewed',
                'reviewed_at', 'reviewed_fingerprint', 'source_document'}:
            raise ValueError('Invalid W-2 preparation record')
        ident = item.get('record_id') or str(uuid.uuid4())
        if not isinstance(ident, str) or not ID.fullmatch(ident) or ident in seen:
            raise ValueError('W-2 preparation record identifiers must be unique UUIDv4 values')
        seen.add(ident)
        current = fingerprint(row, defaults)
        reviewed = item.get('reviewed', False)
        if not isinstance(reviewed, bool):
            raise ValueError('W-2 reviewed status must be true or false')
        reviewed_hash = item.get('reviewed_fingerprint')
        stamp = item.get('reviewed_at')
        if reviewed:
            if not isinstance(reviewed_hash, str) or not HASH.fullmatch(reviewed_hash):
                raise ValueError('Reviewed W-2 requires its checked-value fingerprint')
            if not isinstance(stamp, str) or len(stamp) > 40:
                raise ValueError('Reviewed W-2 requires its review time')
            try:
                parsed = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
                if parsed.tzinfo is None:
                    raise ValueError()
            except ValueError:
                raise ValueError('Invalid W-2 review time')
            reviewed = reviewed_hash == current
        source = source_document(item.get('source_document'))
        old_source = previous_sources.get(ident)
        if isinstance(old_source, dict) and old_source.get('method') == 'taxml' and source != old_source:
            raise ValueError('Saved TaxML source receipts cannot be removed or changed')
        output.append({'record_id': ident, 'row_fingerprint': current,
                       'reviewed': reviewed, 'reviewed_at': stamp if reviewed else None,
                       'reviewed_fingerprint': current if reviewed else None,
                       'source_document': source})
    investments = investment_metadata.normalize(data.get('capital_gains', []),
        provided.get('investment_records') if explicit else None,
        previous.get('investment_records', []) if isinstance(previous, dict) else None)
    previous = previous if isinstance(previous, dict) else {}
    income = income_preparation.normalize(data,
        provided.get('income_document_records') if explicit else None,
        previous.get('income_document_records'))
    events = provided.get('income_import_events', previous.get('income_import_events', [])) if explicit else previous.get('income_import_events', [])
    checked = income_preparation.normalize_state({'data': data, 'preparation_metadata': {
        'income_document_records': income, 'income_import_events': events}})
    # Once saved, an import event is an immutable audit receipt. An older client
    # cannot silently erase it, and a retry cannot reuse its identity for a new
    # replacement. Data rows may still be edited normally outside that history.
    old_events = previous.get('income_import_events', [])
    current_events = {item['event_id']: item for item in checked['preparation_metadata']['income_import_events']}
    for event in old_events:
        if current_events.get(event['event_id']) != event:
            raise ValueError('Saved income-import history cannot be removed or changed')
    return {'version': 1, 'w2_records': output, 'investment_records': investments,
            'income_document_records': checked['preparation_metadata']['income_document_records'],
            'income_import_events': checked['preparation_metadata']['income_import_events']}
