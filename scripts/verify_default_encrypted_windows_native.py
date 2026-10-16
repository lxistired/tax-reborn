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
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server

# The public fixture's selected decrypted binary member (main.entity), not the
# outer encrypted ZIP and not the unused synthetic-default-current.tax sample.
# Regenerate with scripts/create_default_encrypted_binary_fixture.py and
# compare binary_tax.inspect_request(...)["source_sha256"] before changing.
PUBLIC_SELECTED_MAIN_ENTITY_SHA256 = 'f37e00fce34dab082697800b70acda964ae67e2106e750f478f67b7c5f41c5f5'
PUBLIC_SELECTED_PROFILE_SHA256 = '5ea55eeb0df0bebf2c7770e06f4ef42ce2641cb0ea8651756e83e8f641758d6f'
PUBLIC_SELECTED_TEMPLATE_CARRIER_SHA256 = '228e1ea894116f473d44b9d8a7969780052e88f4840aa114398cfd0da967789f'


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
    if not isinstance(source, dict) or not isinstance(source.get('document_id'), str):
        raise ValueError('Reviewed W-2 has no persisted source-document reference')
    try:
        if uuid.UUID(source['document_id']).version != 4:
            raise ValueError
    except (ValueError, AttributeError) as exc:
        raise ValueError('Reviewed W-2 source document ID is not a UUIDv4') from exc
    # `taxml` is the established metadata method label for this local reader
    # route.  The selected entity itself is binary and its exact source hash is
    # asserted below; this does not describe it as plaintext TaxML.
    if source.get('method') != 'taxml':
        raise ValueError('Reviewed W-2 does not retain the established local reader method')
    receipt = source.get('taxml_receipt')
    if not isinstance(receipt, dict):
        raise ValueError('Reviewed W-2 has no persisted local reader receipt')
    if receipt.get('source_sha256') != PUBLIC_SELECTED_MAIN_ENTITY_SHA256:
        raise ValueError('Reviewed W-2 receipt is not bound to the public selected main.entity')
    if receipt.get('wire_profile_sha256') != PUBLIC_SELECTED_PROFILE_SHA256:
        raise ValueError('Reviewed W-2 receipt is not bound to the public selected wire profile')
    if receipt.get('template_carrier_sha256') != PUBLIC_SELECTED_TEMPLATE_CARRIER_SHA256:
        raise ValueError('Reviewed W-2 receipt is not bound to the public selected template carrier')
    if receipt.get('archive_member') is not None:
        raise ValueError('Reviewed W-2 unexpectedly identifies an archive-member wrapper')
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
        'source_document_id_is_uuid4': True,
        'selected_entity_reader_receipt_present': True,
        'selected_main_entity_sha256': PUBLIC_SELECTED_MAIN_ENTITY_SHA256,
        'selected_profile_sha256': PUBLIC_SELECTED_PROFILE_SHA256,
        'selected_template_carrier_sha256': PUBLIC_SELECTED_TEMPLATE_CARRIER_SHA256,
        'selected_entity_is_plaintext_taxml': False,
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
