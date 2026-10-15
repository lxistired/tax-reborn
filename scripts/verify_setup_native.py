"""Read back the synthetic setup record created only through the native GUI."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import server


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',required=True)
    parser.add_argument('--name',default='Synthetic Windows22 filing-status migration')
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    store=server.Store(Path(args.data_dir))
    rows=[row for row in store.list() if row['name']==args.name]
    assert len(rows)==1,'One UI-created synthetic setup return required'
    saved=store.get(rows[0]['id'])
    assert saved['data']['filing_status']=='mfj'
    assert Decimal(saved['data']['w2'][0]['wages'])==Decimal('60000')
    assert saved['result']['summary']['amount_owed']==2946
    assert saved['result']['summary']['total_tax']==2946
    assert saved['result']['can_prepare'] is False
    for key in ('all_income_reported','filing_status_confirmed','hoh_eligible','qss_eligible'):
        assert saved['data']['eligibility'][key] is False,key
    event,=saved['metadata']['setup_import_events']
    assert event['previous_filing_status']=='single' and event['filing_status']=='mfj'
    expected=hashlib.sha256((ROOT/'fixtures/binary-tax/filing-status.taxbin').read_bytes()).hexdigest()
    receipt=event['source_document']['taxml_receipt']
    assert receipt['source_sha256']==expected
    assert event['source_document']['return_id']==saved['id']
    result=dict(synthetic_only=True,native_SQLite_readback=True,filing_status='mfj',wages_USD='60000',
        federal_tax_USD=2946,source_sha256=expected,immutable_source_history_retained=True,
        eligibility_not_asserted=True,original_engine_executed=False,whole_tax_compatibility=False)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':main()
