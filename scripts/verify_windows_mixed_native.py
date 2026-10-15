"""Read back an actual saved mixed-income GUI test and system-exported XML.

Synthetic fixtures only. This checker does not seed or mutate the native return.
"""
from pathlib import Path
import argparse, hashlib, json, sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def verify(record, corrected_xml=None):
    data, metadata, result = record['data'], record['metadata'], record['result']
    assert [len(data[k]) for k in ('w2', 'interest', 'dividends')] == [1, 1, 1]
    w2, interest, dividend = data['w2'][0], data['interest'][0], data['dividends'][0]
    assert w2['owner'] == 'taxpayer' and w2['employer'].strip()
    for name, expected in {'wages':'1234.56', 'federal_withholding':'123', 'social_security_withholding':'76.54', 'medicare_withholding':'17.90', 'social_security_tips':'0', 'dependent_care_benefits':'0'}.items():
        assert w2[name] == expected, (name, w2[name])
    assert interest['payer'].strip() and dividend['payer'].strip()
    for name, expected in {'taxable':'140.50', 'tax_exempt':'12.34', 'federal_withholding':'20.45'}.items():
        assert interest[name] == expected, (name, interest[name])
    for name, expected in {'ordinary':'1200.31', 'qualified':'300.15', 'capital_gain_distributions':'1000.25', 'unrecaptured_1250_gain':'150.05', 'collectibles_gain':'100.05', 'federal_withholding':'200.49'}.items():
        assert dividend[name] == expected, (name, dividend[name])
    assert dividend['special_distribution_confirmed'] is True
    for name, expected in {'1a':1235, '2a':12, '2b':141, '3a':300, '3b':1200, '7a':1000, '11b':3576, '24':0, '25d':344, '35a':344}.items():
        assert result['lines'][name] == expected, (name, result['lines'][name])
    assert result['summary']['refund'] == 344
    rows = [metadata['w2_records'][0], metadata['income_document_records']['interest'][0], metadata['income_document_records']['dividends'][0]]
    assert all(row['reviewed'] is True for row in rows)
    sources = [row['source_document'] for row in rows]
    assert len({row['document_id'] for row in sources}) == 1
    paths = [row['taxml_receipt']['form_path'] for row in sources]
    assert paths == ['0/0/0', '0/0/1', '0/0/2']
    correction = False
    if corrected_xml:
        original = (Path(__file__).resolve().parents[1] / 'fixtures/taxml/synthetic-mixed-income.xml').read_bytes()
        actual = Path(corrected_xml).read_bytes()
        start = original.index(b'<F1099I ')
        end = original.index(b'</F1099I>') + len(b'</F1099I>')
        before = original[start:end]
        assert before.count(b'>100.23</td:value>') == 1
        expected = original[:start] + before.replace(b'>100.23</td:value>', b'>101.24</td:value>') + original[end:]
        assert actual == expected, 'The system-saved XML differs outside the reviewed interest correction'
        correction = True
    return dict(saved_record_counts=[1,1,1], refund=344, saved_interest_unchanged='140.50', one_attachment_three_distinct_paths=paths,
                selected_corrected_XML_byte_exact=correction, all_passed=True, synthetic_only=True, original_runtime=0,
                full_original_tax_compatibility=False)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--data-dir')
    mode.add_argument('--record-json', help='Offline checker development only; does not prove Windows GUI')
    p.add_argument('--corrected-xml')
    p.add_argument('--output', required=True)
    args = p.parse_args()
    if args.data_dir:
        import server
        store = server.Store(args.data_dir)
        rows = [row for row in store.list() if row['name'] == 'Synthetic Windows mixed income migration']
        assert len(rows) == 1, 'Expected exactly one named native mixed GUI test return'
        record = store.get(rows[0]['id'])
    else:
        record = json.loads(Path(args.record_json).read_text())
    receipt = verify(record, args.corrected_xml)
    receipt.update(readback_source='native_SQLite' if args.data_dir else 'offline_checker_fixture', return_id=record['id'])
    Path(args.output).write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt))
