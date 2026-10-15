#!/usr/bin/env python3
"""Read back a complete owned archive using stdlib ZIP and the App separately.

The caller records whether its file came from an actual native system save.
Only independently authored test sources are used by acceptance automation.
"""
from pathlib import Path
from io import BytesIO
import argparse
import base64
from decimal import Decimal
import hashlib
import json
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'web'))
sys.path.insert(0, str(ROOT / 'scripts'))
import taxml_preparation as prep
from create_clear_container_fixture import request


def local_records(data):
    with zipfile.ZipFile(BytesIO(data)) as archive:
        assert archive.testzip() is None
        infos = archive.infolist()
        assert len(infos) == len({i.filename for i in infos})
        ordered = sorted(infos, key=lambda row: row.header_offset)
        stops = [i.header_offset for i in ordered[1:]] + [archive.start_dir]
        raw = {i.filename: data[i.header_offset:end] for i, end in zip(ordered, stops)}
        payloads = {i.filename: archive.read(i) for i in infos}
        return infos, raw, payloads, archive.comment


def verify(source, output, field, amount):
    a, awire, apayload, acomment = local_records(source)
    b, bwire, bpayload, bcomment = local_records(output)
    assert [i.filename for i in a] == [i.filename for i in b]
    assert acomment == bcomment
    assert apayload['manifest.xml'] == bpayload['manifest.xml']
    selected = 'return.xml'
    exact = 0
    for old, new in zip(a, b):
        for name in ['date_time', 'comment', 'extra', 'flag_bits', 'compress_type',
                     'create_system', 'create_version', 'extract_version', 'external_attr']:
            assert getattr(old, name) == getattr(new, name), (old.filename, name)
        if old.filename != selected:
            assert apayload[old.filename] == bpayload[old.filename]
            assert awire[old.filename] == bwire[old.filename]
            exact += 1
    before = prep.inspect_request(request(source))
    after = prep.inspect_request(request(output))
    assert not before['unresolved_facts'] and not after['unresolved_facts']
    assert len(before['candidates']) == len(after['candidates']) == 3
    matches = 0
    for old, new in zip(before['candidates'], after['candidates']):
        assert old['source_owner'] == new['source_owner']
        assert set(old['amounts']) == set(new['amounts'])
        for key, value in old['amounts'].items():
            if key == field:
                assert Decimal(new['amounts'][key]) == Decimal(amount)
                matches += 1
            else: assert Decimal(new['amounts'][key]) == Decimal(value)
    assert matches == 1
    # The two unselected XML form sections remain byte-identical too.
    selected_form = 'FW2' if field == 'wages' else 'F1099I' if field == 'interest_income' else 'F1099D'
    for form in ('FW2', 'F1099I', 'F1099D'):
        if form == selected_form: continue
        name = form.encode(); raw = apayload[selected]
        start = raw.index(b'<' + name + b' '); end = raw.index(b'</' + name + b'>') + len(name) + 3
        assert raw[start:end] in bpayload[selected]
    return {'complete_stdlib_ZIP_CRC_passed': True, 'members': len(a),
            'untouched_local_records_exact': exact, 'manifest_bytes_unchanged': True,
            'other_form_XML_bytes_unchanged': True,
            'source_bytes': len(source), 'output_bytes': len(output),
            'source_sha256': hashlib.sha256(source).hexdigest(),
            'output_sha256': hashlib.sha256(output).hexdigest(),
            'edited_field': field, 'edited_amount': amount,
            'original_program_execution': 0, 'whole_original_tax_compatibility': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--field', default='wages')
    parser.add_argument('--amount', default='1234.57')
    args = parser.parse_args()
    print(json.dumps(verify(args.source.read_bytes(), args.output.read_bytes(), args.field, args.amount)))
