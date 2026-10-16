"""Read back one native-UI default-encrypted sample review from local SQLite.

This checks only the App's own saved W-2 and source-reference metadata after
the installed Windows executable has closed.  It never parses the encrypted
sample, exposes compatibility material, or claims original-file compatibility.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server

PUBLIC_MAIN_ENTITY_SHA256 = '8c5c1ce618bdae851a23a27aede0184d851be2e1ccfae747dbba978e479c403f'


def verify(data_dir: Path, name: str) -> dict:
    store = server.Store(data_dir)
    rows = [row for row in store.list() if row['name'] == name]
    if len(rows) != 1:
        raise ValueError('Expected exactly one native default-encrypted sample return')
    record = store.get(rows[0]['id'])
    w2 = record['data'].get('w2')
    if not isinstance(w2, list) or len(w2) != 1:
        raise ValueError('Expected one source-derived W-2')
    selected = w2[0]
    if selected.get('wages') != '60000' or selected.get('federal_withholding') != '5000':
        raise ValueError('Saved W-2 values do not match the native review and edit')
    records = record['metadata'].get('w2_records')
    if not isinstance(records, list) or len(records) != 1:
        raise ValueError('Reviewed W-2 metadata is missing')
    source = records[0].get('source_document')
    if not isinstance(source, dict) or not source.get('document_id'):
        raise ValueError('Reviewed W-2 has no persisted source-document reference')
    if source.get('method') != 'taxml':
        raise ValueError('Reviewed W-2 does not identify the TaxML reader path')
    receipt = source.get('taxml_receipt')
    if not isinstance(receipt, dict) or receipt.get('source_sha256') != PUBLIC_MAIN_ENTITY_SHA256:
        raise ValueError('Reviewed W-2 has no persisted TaxML reader receipt')
    summary = record['result'].get('summary')
    if not isinstance(summary, dict) or summary.get('refund') != 0 or summary.get('amount_owed') != 75:
        raise ValueError('Saved return does not retain the expected $75 amount due')
    serialized = json.dumps(record['metadata'], sort_keys=True)
    if 'key_base64' in serialized or 'iv_base64' in serialized:
        raise ValueError('Compatibility configuration fields were persisted in SQLite metadata')
    return {
        'sqlite_readback': True,
        'return_name': name,
        'reviewed_w2_count': 1,
        'wages': '60000',
        'federal_withholding': '5000',
        'source_document_reference_present': True,
        'taxml_reader_receipt_present': True,
        'public_main_entity_sha256': PUBLIC_MAIN_ENTITY_SHA256,
        'saved_refund': 0,
        'saved_amount_owed': 75,
        'compatibility_config_fields_absent': True,
        'synthetic_type0_only': True,
        'original_archive_compatibility_claimed': False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.data_dir, args.name)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
