"""Read saved native binary-import state and an actual system-saved correction.

Read only; owned synthetic returns only. No UI or storage seeding.
"""
from pathlib import Path
import argparse, base64, hashlib, json, sys
from decimal import Decimal
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'web'), str(ROOT/'scripts')]
import server
import binary_tax
from verify_windows_mixed_native import verify

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data-dir', required=True)
    p.add_argument('--name', default='Synthetic Windows binary income migration')
    p.add_argument('--corrected-binary')
    p.add_argument('--output', required=True)
    args = p.parse_args()
    store = server.Store(args.data_dir)
    rows = [row for row in store.list() if row['name'] == args.name]
    assert len(rows) == 1, 'Expected one saved binary migration return'
    record = store.get(rows[0]['id'])
    # Existing numeric verifier predates normalized two-place binary amounts.
    assert Decimal(record['data']['w2'][0]['federal_withholding']) == Decimal('123')
    normalized = json.loads(json.dumps(record))
    normalized['data']['w2'][0]['federal_withholding'] = '123'
    receipt = verify(normalized)
    request = json.loads((ROOT/'fixtures/binary-tax/income-request.json').read_text())
    source_hash = hashlib.sha256(base64.b64decode(request['base64'])).hexdigest()
    records = [record['metadata']['w2_records'][0], record['metadata']['income_document_records']['interest'][0], record['metadata']['income_document_records']['dividends'][0]]
    assert all(item['source_document']['taxml_receipt']['source_sha256'] == source_hash for item in records)
    receipt.update(native_SQLite_readback=True, actual_binary_source_hash=source_hash, original_engine_executed=False, full_original_tax_compatibility=False)
    if args.corrected_binary:
        nested = json.loads((ROOT/'fixtures/binary-tax/nested-request.json').read_text())
        inspected = binary_tax.inspect_request(nested)
        form = inspected['binary_archive']['forms'][0]
        fact = next(v for v in form['fields'] if v['field_id'] == 'WAGES')
        output = binary_tax.edit_request({'inspection': nested, 'expected_source_sha256': inspected['source_sha256'], 'changes': [{'path': form['path'], 'ordinal': fact['ordinal'], 'element': 0, 'value': '1234.57'}], 'confirmed': True})
        actual = Path(args.corrected_binary).read_bytes()
        assert actual == base64.b64decode(output['base64']), 'System-saved binary differs from the verified full-structure correction'
        receipt.update(system_saved_corrected_binary_sha256=hashlib.sha256(actual).hexdigest(), nonempty_tables_children_links_retained=True, changed_WAGES='1234.57', other_parsed_facts_preserved=True)
    Path(args.output).write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt))

if __name__ == '__main__':
    main()
