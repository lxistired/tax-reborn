"""Immutable, local filing-status import history outside federal calculation data."""
from datetime import datetime
import re
from source_documents import source_document

ID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
STATUSES = frozenset(('single', 'mfj', 'mfs', 'hoh', 'qss'))


def normalize_events(provided, previous=()):
    if not isinstance(provided, list) or len(provided) > 1000:
        raise ValueError('Invalid return-setup import history')
    out, seen, sources = [], set(), set()
    for event in provided:
        if (not isinstance(event, dict) or set(event) != {'event_id', 'source_document',
                'filing_status', 'previous_filing_status', 'reviewed_at'}
                or not isinstance(event['event_id'], str) or not ID.fullmatch(event['event_id'])
                or event['event_id'] in seen or not isinstance(event['filing_status'], str)
                or not isinstance(event['previous_filing_status'], str)
                or event['filing_status'] not in STATUSES or event['previous_filing_status'] not in STATUSES):
            raise ValueError('Invalid return-setup import receipt')
        stamp = event['reviewed_at']
        if not isinstance(stamp, str) or len(stamp) > 40:
            raise ValueError('Return-setup review time required')
        try:
            if datetime.fromisoformat(stamp.replace('Z', '+00:00')).tzinfo is None:
                raise ValueError()
        except ValueError as error:
            raise ValueError('Invalid return-setup review time') from error
        source = source_document(event['source_document'])
        if not source or source['method'] != 'taxml':
            raise ValueError('A verified tax-data source receipt is required')
        receipt = source['taxml_receipt']
        key = receipt['source_sha256'], receipt['form_path'], receipt['archive_member']
        if key in sources:
            raise ValueError('This source already supplied return setup')
        seen.add(event['event_id']); sources.add(key)
        out.append({**event, 'source_document': source})
    current = {event['event_id']: event for event in out}
    for old in previous:
        if current.get(old['event_id']) != old:
            raise ValueError('Saved return-setup import history cannot be removed or changed')
    return out
