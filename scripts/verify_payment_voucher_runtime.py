"""Read back actual-worker serialized payment-voucher packets on the host."""
from pathlib import Path
import sys,json,io
BASE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(BASE),str(BASE/'tests')]
import official_forms
from payment_voucher_qa import verify_packet
from pypdf import PdfReader

out=Path(sys.argv[1]) if len(sys.argv)>1 else BASE/'qa/payment-voucher-20261015/worker'
receipt=json.loads((out/'payment-voucher-worker-receipt.json').read_text());rows=[]
for case in receipt['rows']:
    for packet in case['packets']:
        raw=(out/packet['file']).read_bytes();checked=verify_packet(raw,packet['amount'],official_forms)
        fields=PdfReader(io.BytesIO(raw)).get_fields()
        key=official_forms.MAP['f1040']['line_fields']['37']
        assert str(fields[key]['/V'])==str(case['owed'])
        rows.append({'file':packet['file'],'owed':case['owed'],'amount':packet['amount'],
            'canonical_and_widget_fields':checked['canonical_and_widget_fields'],'voucher_pages':checked['voucher_pages']})
assert len(rows)==6
result={'synthetic_only':True,'actual_worker_packets_read_back':6,'rows':rows,'original_runtime_comparison':False,'native_UI_acceptance':False}
(out/'payment-voucher-worker-pdf-readback.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
