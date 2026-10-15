#!/usr/bin/env python3
"""Independent ZIP/byte checks plus App readback of an owned saved example."""
from pathlib import Path
import argparse
import base64
from decimal import Decimal
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'web'), str(ROOT / 'scripts')]
from verify_clear_container_native import local_records
import taxml_preparation


def verify(output, field, amount):
    request = json.loads((ROOT / 'fixtures/mac-taxml/request.json').read_text())
    source = base64.b64decode(request['base64'], validate=True)
    a, ar, ap, ac = local_records(source)
    b, br, bp, bc = local_records(output)
    assert [i.filename for i in a] == [i.filename for i in b] and ac == bc
    exact = 0
    for old, new in zip(a, b):
        for name in ('date_time', 'comment', 'extra', 'flag_bits', 'compress_type',
                     'create_system', 'create_version', 'extract_version', 'external_attr'):
            assert getattr(old, name) == getattr(new, name), (old.filename, name)
        if old.filename != 'return.xml':
            assert ar[old.filename] == br[old.filename]
            assert ap[old.filename] == bp[old.filename]
            exact += 1
    before = taxml_preparation.inspect_request(request)
    after = taxml_preparation.inspect_request({**request, 'base64': base64.b64encode(output).decode()})
    assert len(before['candidates']) == len(after['candidates']) == 7
    assert not before['unresolved_facts'] and not after['unresolved_facts']
    target = {'wages': '0/0/0', 'interest_income': '0/0/2', 'ordinary': '0/0/3'}[field]
    changed = 0
    for old, new in zip(before['candidates'], after['candidates']):
        assert old['source_owner'] == new['source_owner']
        assert old['receipt']['form_path'] == new['receipt']['form_path']
        assert set(old['amounts']) == set(new['amounts'])
        for key, value in old['amounts'].items():
            if old['receipt']['form_path'] == target and key == field:
                assert Decimal(new['amounts'][key]) == Decimal(amount)
                changed += 1
            else:
                assert Decimal(new['amounts'][key]) == Decimal(value)
    assert changed == 1
    # Do not use the App's patcher for the independent byte check. All source
    # sample values have two decimals, so a single text replacement suffices.
    blocks = lambda xml: list(re.finditer(rb'<(FW2|F1099I|F1099D)\s[^>]*>.*?</\1>', xml, re.S))
    oldblocks, newblocks = blocks(ap['return.xml']), blocks(bp['return.xml'])
    assert len(oldblocks) == len(newblocks) == 7
    index = {'wages': 0, 'interest_income': 2, 'ordinary': 3}[field]
    label = {'wages': 'WAGES', 'interest_income': 'L1', 'ordinary': 'L1B'}[field].encode()
    selected = oldblocks[index]
    pattern = rb'(<'+label+rb'\s[^>]*><td:value>)[^<]+(</td:value></'+label+rb'>)'
    changed_block, count = re.subn(pattern, lambda m: m[1] + format(Decimal(amount), '.2f').encode() + m[2], selected[0])
    assert count == 1
    expected = ap['return.xml'][:selected.start()] + changed_block + ap['return.xml'][selected.end():]
    assert bp['return.xml'] == expected
    return {'complete_stdlib_ZIP_CRC_passed': True, 'members': len(a),
        'untouched_local_records_exact': exact, 'manifest_bytes_unchanged': True,
        'other_form_XML_bytes_unchanged': True, 'complete_XML_exact_except_selected_text': True,
        'entities': 2, 'form_copies': 7,
        'source_bytes': len(source), 'output_bytes': len(output),
        'source_sha256': hashlib.sha256(source).hexdigest(),
        'output_sha256': hashlib.sha256(output).hexdigest(),
        'edited_field': field, 'edited_amount': amount,
        'original_program_execution': 0, 'whole_original_tax_compatibility': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--field', default='wages')
    parser.add_argument('--amount', default='1234.57')
    args = parser.parse_args()
    print(json.dumps(verify(args.output.read_bytes(), args.field, args.amount)))
