"""Independent local INT/DIV preparation contract, not vendor execution.

Original observations: instance-ID review map replacement and selected-shell
replacement after successful import. Fingerprints, immutable event receipts,
explicit placeholder IDs and atomic persistence are independent design choices.
No tax rule, amount formula, remote importer or App runtime is implemented here.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import re
import uuid

COLLECTIONS = {
    'interest': {'payer': '', 'taxable': '0', 'tax_exempt': '0', 'federal_withholding': '0'},
    'dividends': {'payer': '', 'ordinary': '0', 'qualified': '0',
                  'capital_gain_distributions': '0', 'federal_withholding': '0'},
}
MONEY = re.compile(r'^-?\d+(?:\.\d{1,2})?$')
UID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
ENTRY_FIELDS = {'record_id', 'is_placeholder', 'unresolved_fields',
                'reviewed', 'reviewed_at', 'reviewed_fingerprint', 'row_fingerprint'}


def ident(value):
    if not isinstance(value, str) or not UID.fullmatch(value):
        raise ValueError('Expected a UUIDv4 local record identifier')
    return value


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(packed(value).encode()).hexdigest()


def canonical_row(collection, row):
    defaults = COLLECTIONS.get(collection)
    if defaults is None or not isinstance(row, dict) or set(row) - set(defaults):
        raise ValueError('Unsupported INT/DIV row or field')
    value = {**defaults, **row}
    if not isinstance(value['payer'], str) or len(value['payer']) > 256:
        raise ValueError('Invalid payer label')
    for field in defaults.keys() - {'payer'}:
        text = str(value[field]).strip()
        if isinstance(value[field], bool) or len(text) > 64 or not MONEY.fullmatch(text):
            raise ValueError('Expected an explicit USD amount with at most two decimal places')
        amount = Decimal(text)
        if abs(amount) > Decimal('999999999999.99'):
            raise ValueError('USD amount exceeds preparation limit')
        value[field] = '0.00' if amount == 0 else format(amount, '.2f')
    return value


def normalize_entry(collection, row, item=None, draft=False):
    item = deepcopy({} if item is None else item)
    if not isinstance(item, dict) or set(item) - ENTRY_FIELDS:
        raise ValueError('Unsupported preparation metadata field')
    try:
        fingerprint = digest(canonical_row(collection, row))
    except ValueError:
        if not draft:
            raise
        fingerprint = None
    uid = ident(item.get('record_id') or str(uuid.uuid4()))
    fields = item.get('unresolved_fields', [])
    if not isinstance(fields, list) or any(
            not isinstance(x, str) or x not in set(COLLECTIONS[collection]) | {'current_year_confirmation'} for x in fields) or len(fields) != len(set(fields)):
        raise ValueError('Invalid unresolved-field collection')
    if not isinstance(item.get('reviewed', False), bool):
        raise ValueError('Reviewed status must be Boolean')
    placeholder = item.get('is_placeholder', False)
    if not isinstance(placeholder, bool):
        raise ValueError('Placeholder status must be Boolean')
    # Current-row math facts determine review freshness. Missing-fact state is
    # maintained independently and is never erased by checking a review box.
    changed = item.get('row_fingerprint') not in (None, fingerprint)
    checked = item.get('reviewed', False)
    if checked:
        if not isinstance(item.get('reviewed_fingerprint'), str) or not re.fullmatch(r'[0-9a-f]{64}', item['reviewed_fingerprint']):
            raise ValueError('Reviewed record requires its checked-value fingerprint')
        stamp = item.get('reviewed_at')
        if not isinstance(stamp, str) or len(stamp) > 40:
            raise ValueError('Reviewed record requires its review timestamp')
        try:
            if datetime.fromisoformat(stamp.replace('Z', '+00:00')).tzinfo is None:
                raise ValueError()
        except ValueError:
            raise ValueError('Reviewed record requires a timezone-aware timestamp')
    reviewed = checked and fingerprint is not None and item.get('reviewed_fingerprint') == fingerprint and not changed
    return {'record_id': uid, 'is_placeholder': placeholder,
            'unresolved_fields': sorted(fields),
            'row_fingerprint': fingerprint, 'reviewed': reviewed,
            'reviewed_at': item.get('reviewed_at') if reviewed else None,
            'reviewed_fingerprint': fingerprint if reviewed else None}


def canonical(collection, row):
    return packed(canonical_row(collection, row))


def fingerprint(collection, row):
    return digest(canonical_row(collection, row))


def new_record(is_placeholder=False, unresolved_fields=None):
    return {'record_id': str(uuid.uuid4()), 'row_fingerprint': None, 'reviewed': False,
            'reviewed_fingerprint': None, 'reviewed_at': None,
            'is_placeholder': is_placeholder, 'unresolved_fields': list(unresolved_fields or [])}


def normalize(rows_by_type, provided=None, previous=None, options=None):
    """Return the optional income_document_records map for the v1 envelope.

    Legacy unique exact matches retain IDs. Ambiguous identical rows get fresh
    identities and are never silently considered previously reviewed. Draft
    invalid amounts yield null fingerprints and clear review; strict host
    persistence rejects malformed USD rather than inventing zero amounts.
    """
    if not isinstance(rows_by_type, dict):
        raise ValueError('Expected current income rows')
    for value in (provided, previous):
        if value is not None and (not isinstance(value, dict) or set(value) - set(COLLECTIONS)):
            raise ValueError('Unsupported income preparation collection')
    prepared, all_ids = {}, set()
    for collection in COLLECTIONS:
        rows = rows_by_type.get(collection, [])
        if not isinstance(rows, list) or len(rows) > 1000:
            raise ValueError('Invalid income row collection')
        hashes = []
        for row in rows:
            try:
                hashes.append(fingerprint(collection, row))
            except ValueError:
                if not (options or {}).get('draft'):
                    raise
                hashes.append(None)
        entries = provided.get(collection) if provided is not None else None
        if entries is None:
            old = previous.get(collection, []) if previous else []
            if not isinstance(old, list) or any(not isinstance(x, dict) for x in old):
                raise ValueError('Invalid previous income preparation collection')
            entries = []
            for current in hashes:
                matches = [x for x in old if x.get('row_fingerprint') == current]
                entries.append(matches[0] if current is not None and len(matches) == 1 and hashes.count(current) == 1 else {})
        if not isinstance(entries, list) or len(entries) != len(rows):
            raise ValueError('Preparation metadata must match current income rows')
        prepared[collection] = []
        for row, entry in zip(rows, entries):
            if not isinstance(entry, dict):
                raise ValueError('Invalid explicit income preparation entry')
            value = normalize_entry(collection, row, entry, draft=(options or {}).get('draft', False))
            if value['record_id'] in all_ids:
                raise ValueError('Source-record identifiers must be unique across INT/DIV')
            all_ids.add(value['record_id']); prepared[collection].append(value)
    return prepared


def validate_receipt(receipt):
    expected = {'collection', 'removed_record_ids', 'result_record_ids', 'archived_replaced_records'}
    if not isinstance(receipt, dict) or set(receipt) != expected or not isinstance(receipt['collection'], str) or receipt['collection'] not in COLLECTIONS:
        raise ValueError('Invalid local replacement receipt fields')
    for field in ('removed_record_ids', 'result_record_ids'):
        values = receipt[field]
        if not isinstance(values, list) or not values or len(values) > 1000:
            raise ValueError('Invalid replacement receipt ID collection')
        for uid in values:
            ident(uid)
        if len(values) != len(set(values)):
            raise ValueError('Duplicate replacement receipt ID')
    if set(receipt['removed_record_ids']) & set(receipt['result_record_ids']):
        raise ValueError('Replacement result and removed-record IDs must differ')
    archived = receipt['archived_replaced_records']
    if not isinstance(archived, list) or len(archived) != len(receipt['removed_record_ids']):
        raise ValueError('Replacement receipt requires each removed source row')
    archived_ids = []
    for item in archived:
        if not isinstance(item, dict) or set(item) != {'row', 'metadata'}:
            raise ValueError('Invalid archived replacement source fields')
        canonical_row(receipt['collection'], item['row'])
        normalized = normalize_entry(receipt['collection'], item['row'], item['metadata'])
        if normalized != item['metadata'] or not normalized['is_placeholder']:
            raise ValueError('Archived placeholder metadata must match its saved source facts')
        archived_ids.append(normalized['record_id'])
    if len(set(archived_ids)) != len(archived_ids) or set(archived_ids) != set(receipt['removed_record_ids']):
        raise ValueError('Archived source IDs do not match removed targets')
    return deepcopy(receipt)


def normalize_state(state):
    if not isinstance(state, dict):
        raise ValueError('Expected an income preparation state')
    result = deepcopy(state)
    data = result.setdefault('data', {})
    meta = result.setdefault('preparation_metadata', {})
    if not isinstance(data, dict) or not isinstance(meta, dict):
        raise ValueError('Expected data and preparation metadata objects')
    income = meta.setdefault('income_document_records', {})
    if not isinstance(income, dict) or set(income) - set(COLLECTIONS):
        raise ValueError('Unsupported income preparation collection')
    seen = set()
    for collection in COLLECTIONS:
        rows = data.get(collection, [])
        if not isinstance(rows, list) or len(rows) > 1000:
            raise ValueError('Invalid source-record collection')
        entries = income.get(collection)
        # Deliberately no index-based matching of legacy duplicates.
        if entries is None:
            entries = [{} for _ in rows]
        if not isinstance(entries, list) or len(entries) != len(rows):
            raise ValueError('Aligned preparation metadata is required')
        normalized = []
        for row, item in zip(rows, entries):
            if not isinstance(item, dict):
                raise ValueError('Invalid explicit income preparation entry')
            entry = normalize_entry(collection, row, item)
            if entry['record_id'] in seen:
                raise ValueError('Source-record IDs must be unique across INT and DIV')
            seen.add(entry['record_id']); normalized.append(entry)
        income[collection] = normalized
    events = meta.setdefault('income_import_events', [])
    if not isinstance(events, list) or len(events) > 1000:
        raise ValueError('Invalid local import-event history')
    event_ids = set()
    for event in events:
        if not isinstance(event, dict) or set(event) != {'event_id', 'payload_hash', 'receipt'}:
            raise ValueError('Invalid local import-event receipt')
        ident(event['event_id'])
        if event['event_id'] in event_ids or not isinstance(event['payload_hash'], str) or not re.fullmatch(r'[0-9a-f]{64}', event['payload_hash']):
            raise ValueError('Duplicate or invalid local import-event identity')
        validate_receipt(event['receipt'])
        event_ids.add(event['event_id'])
    return result


def current_summary(state):
    state = normalize_state(state)
    output = {'reviewed_by_id': {}, 'missing_facts_by_id': {}, 'reviewed': 0, 'total': 0}
    for collection, entries in state['preparation_metadata']['income_document_records'].items():
        if collection not in COLLECTIONS:
            continue
        for item in entries:
            uid = item['record_id']
            missing = list(item['unresolved_fields'])
            if item['is_placeholder'] and 'current_year_confirmation' not in missing:
                missing.append('current_year_confirmation')
            output['reviewed_by_id'][uid] = item['reviewed']
            output['missing_facts_by_id'][uid] = missing
            output['reviewed'] += item['reviewed']; output['total'] += 1
    return output


def mark_reviewed(state, collection, record_id, timestamp):
    state = normalize_state(state)
    entries = state['preparation_metadata']['income_document_records'][collection]
    entry = next((x for x in entries if x['record_id'] == ident(record_id)), None)
    if entry is None:
        raise ValueError('Selected record no longer exists')
    entry.update(reviewed=True, reviewed_at=timestamp,
                 reviewed_fingerprint=entry['row_fingerprint'])
    state = normalize_state(state)
    return state


def replacement_plan(state, event_id, collection, target_ids, replacements, successful=True):
    """Plan one successful local replacement, never infer identity from payer text.

    replacements is a list of core INT/DIV rows; result IDs are locally
    generated in the proposal. The immutable payload excludes generated result IDs.
    """
    state = normalize_state(state); ident(event_id)
    if not isinstance(collection, str) or collection not in COLLECTIONS or not isinstance(successful, bool):
        raise ValueError('Invalid local import operation')
    if not successful:
        return {'status': 'not_applied', 'reason': 'Import has not succeeded'}
    if not isinstance(target_ids, list) or not target_ids:
        raise ValueError('Explicit unique replacement target IDs are required')
    target_ids = [ident(x) for x in target_ids]
    if len(target_ids) != len(set(target_ids)):
        raise ValueError('Explicit unique replacement target IDs are required')
    if not isinstance(replacements, list) or not replacements or len(replacements) > 1000:
        raise ValueError('Replacement must contain actual imported rows')
    event = next((x for x in state['preparation_metadata']['income_import_events'] if x['event_id'] == event_id), None)
    entries = state['preparation_metadata']['income_document_records'][collection]
    paired = {item['record_id']: (row, item) for row, item in zip(state['data'].get(collection, []), entries)}
    replay_before = {x['metadata']['record_id']: x['metadata']['row_fingerprint']
        for x in event['receipt']['archived_replaced_records']} if event else {}
    targets = []
    for uid in target_ids:
        if event:
            if uid not in replay_before:
                raise ValueError('Conflicting import-event replacement targets')
            targets.append({'record_id': uid, 'before_fingerprint': replay_before[uid]})
            continue
        if uid not in paired:
            raise ValueError('Replacement target no longer exists')
        row, item = paired[uid]
        if not item['is_placeholder']:
            raise ValueError('Only an explicitly selected import placeholder can be replaced')
        targets.append({'record_id': uid, 'before_fingerprint': item['row_fingerprint']})
    payload_rows = [canonical_row(collection, item) for item in replacements]
    payload = {'collection': collection, 'target_ids': sorted(target_ids), 'replacements': payload_rows,
               'before_fingerprints': {x['record_id']: x['before_fingerprint'] for x in targets}}
    payload_hash = digest(payload)
    if event:
        if event['payload_hash'] != payload_hash:
            raise ValueError('An import-event ID cannot identify a different source, target or amount')
        return {'status': 'already_applied', 'event_id': event_id, 'payload_hash': payload_hash,
                'receipt': deepcopy(event['receipt'])}
    new = []
    for row in payload_rows:
        item = normalize_entry(collection, row, {'record_id': str(uuid.uuid4()),
                 'is_placeholder': False, 'unresolved_fields': []})
        new.append({'row': row, 'metadata': item})
    return {'status': 'planned', 'event_id': event_id, 'payload_hash': payload_hash,
            'payload': payload, 'targets': targets, 'new_records': new}


def apply_replacement(state, plan):
    """Pure transaction result; caller must atomically save data+metadata together."""
    state = normalize_state(state)
    if plan.get('status') == 'not_applied':
        return state, {'status': 'not_applied'}
    event_id = ident(plan.get('event_id'))
    if plan.get('status') == 'planned' and digest(plan.get('payload')) != plan.get('payload_hash'):
        raise ValueError('Replacement proposal payload changed')
    event = next((x for x in state['preparation_metadata']['income_import_events'] if x['event_id'] == event_id), None)
    if event:
        if event['payload_hash'] != plan.get('payload_hash'):
            raise ValueError('Conflicting import-event replay')
        return state, {'status': 'already_applied', **deepcopy(event['receipt'])}
    if plan.get('status') != 'planned' or digest(plan['payload']) != plan['payload_hash']:
        raise ValueError('Replacement proposal is not an intact planned operation')
    collection = plan['payload']['collection']; entries = state['preparation_metadata']['income_document_records'][collection]
    targets = {x['record_id']: x['before_fingerprint'] for x in plan['targets']}
    if targets != plan['payload'].get('before_fingerprints') or set(targets) != set(plan['payload']['target_ids']) or len(targets) != len(plan['targets']):
        raise ValueError('Replacement target identity mismatch')
    paired = list(zip(state['data'].get(collection, []), entries))
    archived = []
    for uid, expected in targets.items():
        match = [(r, m) for r, m in paired if m['record_id'] == uid]
        if len(match) != 1 or match[0][1]['row_fingerprint'] != expected or not match[0][1]['is_placeholder']:
            raise ValueError('Selected import placeholder has changed; review a fresh proposal')
        archived.append({'row': deepcopy(match[0][0]), 'metadata': deepcopy(match[0][1])})
    actual_rows = [canonical_row(collection, x['row']) for x in plan['new_records']]
    if actual_rows != plan['payload']['replacements']:
        raise ValueError('Replacement source rows differ from the reviewed proposal')
    for item in plan['new_records']:
        value = normalize_entry(collection, item['row'], item['metadata'])
        if value != item['metadata'] or value['reviewed'] or value['is_placeholder'] or value['unresolved_fields']:
            raise ValueError('New imported records require fresh, unchecked preparation metadata')
    # Delete by identity in a new collection, preserving all unrelated rows/order.
    # This avoids the unproven vendor DataUtils array-index deletion behavior.
    kept = [(r, m) for r, m in paired if m['record_id'] not in targets]
    first = min(i for i, (_, m) in enumerate(paired) if m['record_id'] in targets)
    insertion = sum(m['record_id'] not in targets for _, m in paired[:first])
    kept[insertion:insertion] = [(x['row'], x['metadata']) for x in plan['new_records']]
    state['data'][collection] = [r for r, _ in kept]
    state['preparation_metadata']['income_document_records'][collection] = [m for _, m in kept]
    receipt = {'collection': collection, 'removed_record_ids': sorted(targets),
               'result_record_ids': [x['metadata']['record_id'] for x in plan['new_records']],
               'archived_replaced_records': archived}
    state['preparation_metadata']['income_import_events'].append(
        {'event_id': event_id, 'payload_hash': plan['payload_hash'], 'receipt': receipt})
    return normalize_state(state), {'status': 'applied', **deepcopy(receipt)}


def plan(data, metadata, collection, target_ids, replacement_rows, event_id=None, successful=True):
    return replacement_plan({'data': data, 'preparation_metadata': metadata},
        event_id or str(uuid.uuid4()), collection, target_ids, replacement_rows, successful)


def apply(data, metadata, proposal):
    state, receipt = apply_replacement({'data': data, 'preparation_metadata': metadata}, proposal)
    return {'data': state['data'], 'metadata': state['preparation_metadata'],
            'already_applied': receipt['status'] == 'already_applied', 'receipt': receipt}
