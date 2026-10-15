"""Read an actual native system-saved comparison; never seed App inputs."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'web')]
import server,tax_engine,source_calculation_command

def main():
    p=argparse.ArgumentParser();mode=p.add_mutually_exclusive_group(required=True);mode.add_argument('--data-dir');mode.add_argument('--backup-json');p.add_argument('--name');p.add_argument('--audit',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    if a.backup_json:
        record=json.loads(Path(a.backup_json).read_text());assert record['format']=='tax-reborn-return-v1'
        if a.name:assert record['data']['name']==a.name
    else:
        if not a.name:p.error('--name is required for a native SQLite readback')
        store=server.Store(a.data_dir);rows=[r for r in store.list() if r['name']==a.name];assert len(rows)==1
        record=store.get(rows[0]['id'])
    snapshot=source_calculation_command.current_app_snapshot(record['data'])
    raw=Path(a.audit).read_bytes();result=json.loads(raw);c=result['comparison']
    assert c['current_App_return_sha256']==snapshot['current_return_sha256']
    summary=snapshot['result']['summary']
    assert c['current_app_summary']=={k:str(summary[k]) for k in ('total_tax','amount_owed','refund','payments','taxable_income')}
    assert (c['source_total_tax'],c['source_payments'],c['source_signed_balance'])==('1279','100','1179')
    from decimal import Decimal as D
    assert D(c['current_app_signed_balance'])==D(summary['total_tax'])-D(summary['payments'])
    assert D(c['signed_balance_difference'])==D('1179')-D(c['current_app_signed_balance'])
    assert result['IRS_engine_called_for_complete_current_return'] and not result['IRS_engine_replaced']
    assert c['source_current_return_pair_acknowledged'] and not result['writeback_allowed'] and not result['source_modified']
    assert c['source_refund_not_calculated'] and not c['identical_input_context_or_engine_parity_asserted']
    sample=json.loads((ROOT/'web/samples/source-calculation-demo-request.json').read_text())
    import base64
    assert result['source_calculation']['source_sha256']==hashlib.sha256(base64.b64decode(sample['source']['base64'])).hexdigest()
    assert c['source_profile_sha256']==source_calculation_command.binary_tax.prep.canonical_hash(sample['source']['profile'])
    receipt=dict(actual_system_file_readback=True,current_input_readback_source='actual_system_backup_JSON' if a.backup_json else 'native_SQLite',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),full_saved_return_SHA_matches=True,complete_current_IRS_result_recalculated=True,current_return_sha256=snapshot['current_return_sha256'],actual_saved_refund=summary['refund'],current_blocking_issues_preserved=bool(snapshot['result']['blocking_issues']),comparison=c,source_and_saved_return_unchanged=True,comparison_only=True,synthetic_only=True,original_engine_executed=False,whole_original_tax_compatibility=False)
    Path(a.output).write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
