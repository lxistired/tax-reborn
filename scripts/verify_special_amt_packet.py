#!/usr/bin/env python3
"""Verify a saved native packet against a separately written public IRS fixture."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import official_forms
from pypdf import PdfReader


def verify(raw, case_id='IRS2025-AMT-special-005'):
    case = next(c for c in json.loads((ROOT/'fixtures/special_amt_2025.json').read_text())['cases'] if c['id']==case_id)
    reader = PdfReader(io.BytesIO(raw))
    fields = reader.get_fields()
    mapping = official_forms.MAP['f6251']['line_fields']
    prefixes = {name.split('.topmostSubform',1)[0]+'.' for name in fields if name.startswith('f6251_') and '.topmostSubform' in name}
    assert len(prefixes)==1, 'Exactly one serialized6251 field group is required'
    prefix = prefixes.pop()
    expected = dict(case['expected_partIII'], **{'9':case['expected']['tentative_minimum_tax'],'10':case['expected']['regular_tax'],'11':case['expected']['AMT']})
    for line, value in expected.items():
        assert str(fields[prefix+mapping[line]]['/V'])==str(value), 'Serialized6251 line'+line
    assert sum(page.get('/TaxRebornForm')=='f6251' for page in reader.pages)==2
    assert str(fields['topmostSubform[0].Page2[0].f2_09[0]']['/V'])==str(case['expected']['AMT'])
    assert ('AMT liability: $'+format(case['expected']['AMT'],',')) in '\n'.join(page.extract_text() for page in reader.pages)
    return {'case_id':case_id,'pages':len(reader.pages),'partIII_lines_verified':29,'form6251_pages':2,'AMT':case['expected']['AMT'],'packet_sha256':hashlib.sha256(raw).hexdigest(),'all_passed':True,'oracle':'Independent publicIRS2025 fixture, not output of the packaged engine'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('packet',type=Path)
    parser.add_argument('--case-id',default='IRS2025-AMT-special-005')
    args=parser.parse_args()
    print(json.dumps(verify(args.packet.read_bytes(),args.case_id),indent=2))
