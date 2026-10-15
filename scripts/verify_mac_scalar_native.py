#!/usr/bin/env python3
"""Verify a complete independently generated Mac decimal source export."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import zipfile
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'web'), str(ROOT / 'scripts')]
import taxml_mac as mac
import taxml_preparation as prep
from interop.container.raw_zip_reference import load_archive


def verify(path):
    # Verify the exact source loaded by the installed UI, including its ZIP
    # creator metadata. Regenerating ZipInfo on another OS changes those bytes.
    req = json.loads((ROOT / 'fixtures/mac-scalar-taxml/request.json').read_text())
    before = prep.inspect_request(req)
    selected = before['scalar_fields'][0]
    expected = prep.export_request({'inspection': req,
        'expected_scalar_sha256': selected['receipt']['field_sha256'],
        'value': '0.8', 'confirmed': True})
    blob = Path(path).read_bytes()
    # Independently check the actual ZIP/XML bytes, without using the App's
    # source patcher to define which other fields may change.
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(req['base64']))) as a, zipfile.ZipFile(io.BytesIO(blob)) as b:
        assert a.testzip() is None and b.testzip() is None
        assert a.namelist() == b.namelist()
        old_xml = a.read('return.xml')
        pattern = rb'(<DECIMAL\s[^>]*><td:value>)0\.7(</td:value></DECIMAL>)'
        changed_xml, count = re.subn(pattern, lambda m: m[1] + b'0.8' + m[2], old_xml, count=1)
        assert count == 1 and b.read('return.xml') == changed_xml
        for name in a.namelist():
            if name != 'return.xml':
                assert a.read(name) == b.read(name)
    if blob != base64.b64decode(expected['base64']):
        raise ValueError('The complete exported archive differs from the verified one-field correction.')
    after = prep.inspect_request({**req, 'base64': base64.b64encode(blob).decode()})
    old, new = load_archive(base64.b64decode(req['base64'])), load_archive(blob)
    assert len(old.members) == len(new.members) == 5
    assert sum(a.local == b.local for a, b in zip(old.members, new.members)) == 4
    assert [f['text'] for f in after['scalar_fields']] == ['0.8', '1.2', '-0.3']
    assert [c['amounts'] for c in before['candidates']] == [c['amounts'] for c in after['candidates']]
    assert not after['unresolved_facts']
    doc = mac._context({**req, 'base64': base64.b64encode(blob).decode()})[-1]
    return {'all_passed': True, 'output_bytes': len(blob), 'output_sha256': hashlib.sha256(blob).hexdigest(),
        'entities': 2, 'copies': 7, 'all_fields': len(doc.fields), 'decimal_fields': 3,
        'decimal_values': ['0.8', '1.2', '-0.3'], 'current_ordinal': 9,
        'income_candidates_unchanged': 7, 'untouched_local_records_exact': 4,
        'independent_stdlib_ZIP_CRC_and_exact_XML_except_one_field': True,
        'original_manifest_exact': True, 'native_program_acceptance': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('file', type=Path)
    print(json.dumps(verify(parser.parse_args().file)))
