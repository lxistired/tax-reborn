"""Local investment identity and absolute-basis correction history.

This is preparation metadata, not a tax formula or a broker integration.
"""
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import re
import uuid

from tax_engine import ROW_DEFAULTS

ID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
HASH = re.compile(r'^[0-9a-f]{64}$')
AMOUNT = re.compile(r'^-?\d+(?:\.\d{1,2})?$')
MONEY = ('proceeds', 'cost_basis', 'adjustment', 'wash_sale_disallowed')


def amount(value):
    text = str(value).strip() or '0'
    if not AMOUNT.fullmatch(text) or len(text) > 64:
        raise ValueError('Investment amounts require USD decimals with at most two places')
    number = Decimal(text)
    return '0.00' if not number else format(number, '.2f')


def canonical(row):
    if not isinstance(row, dict):
        raise ValueError('Expected an investment-sale record')
    value = {**ROW_DEFAULTS['capital_gains'], **row}
    for name in MONEY:
        value[name] = amount(value.get(name, '0'))
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(row):
    return hashlib.sha256(canonical(row).encode('utf-8')).hexdigest()


def normalize(rows, entries=None, previous=None):
    if not isinstance(rows, list) or len(rows) > 1000:
        raise ValueError('Invalid investment-sale preparation collection')
    hashes = [fingerprint(row) for row in rows]
    if entries is None:
        entries = []
        for current in hashes:
            matches = [x for x in previous or [] if x.get('row_fingerprint') == current]
            entries.append(matches[0] if len(matches) == 1 and hashes.count(current) == 1 else {})
    if not isinstance(entries, list) or len(entries) != len(rows):
        raise ValueError('Investment preparation records must match their sale collection')
    output, record_ids, correction_ids = [], set(), set()
    for current, entry in zip(hashes, entries):
        if not isinstance(entry, dict) or set(entry) - {'record_id', 'row_fingerprint', 'basis_corrections'}:
            raise ValueError('Invalid investment preparation record')
        ident = entry.get('record_id') or str(uuid.uuid4())
        if not isinstance(ident, str) or not ID.fullmatch(ident) or ident in record_ids:
            raise ValueError('Investment record identifiers must be unique UUIDv4 values')
        record_ids.add(ident)
        history = entry.get('basis_corrections', [])
        if not isinstance(history, list) or len(history) > 100:
            raise ValueError('Invalid basis-correction history')
        normalized = []
        for item in history:
            keys = {'correction_id', 'previous_fingerprint', 'result_fingerprint',
                    'old_cost_basis', 'new_cost_basis', 'applied_at', 'reason'}
            if not isinstance(item, dict) or set(item) != keys:
                raise ValueError('Invalid basis-correction record')
            cid = item['correction_id']
            if not isinstance(cid, str) or not ID.fullmatch(cid) or cid in correction_ids:
                raise ValueError('Basis-correction identifiers must be unique UUIDv4 values')
            correction_ids.add(cid)
            if any(not isinstance(item[k], str) or not HASH.fullmatch(item[k])
                   for k in ('previous_fingerprint', 'result_fingerprint')):
                raise ValueError('Basis correction requires its before/after fingerprints')
            before, after = amount(item['old_cost_basis']), amount(item['new_cost_basis'])
            if Decimal(after) < 0:
                raise ValueError('Corrected cost basis cannot be negative')
            stamp = item['applied_at']
            if not isinstance(stamp, str) or len(stamp) > 40:
                raise ValueError('Invalid basis-correction time')
            try:
                if datetime.fromisoformat(stamp.replace('Z', '+00:00')).tzinfo is None:
                    raise ValueError()
            except ValueError:
                raise ValueError('Invalid basis-correction time')
            reason = item['reason']
            if not isinstance(reason, str) or len(reason) > 500 or re.search(r'[\x00-\x1f\x7f]', reason):
                raise ValueError('Invalid basis-correction source note')
            normalized.append({**item, 'old_cost_basis': before, 'new_cost_basis': after})
        output.append({'record_id': ident, 'row_fingerprint': current, 'basis_corrections': normalized})
    return output
