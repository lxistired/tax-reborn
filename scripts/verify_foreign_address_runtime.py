"""Independent serialized-field readback of actual worker PDFs."""
from pathlib import Path
import sys,json,hashlib
BASE=Path(__file__).resolve().parents[1];sys.path[:0]=[str(BASE),str(BASE/'tests')]
import official_forms
from foreign_address_qa import verify_packet
out=Path(sys.argv[1]) if len(sys.argv)>1 else BASE/'qa/foreign-address-20261015/worker'
receipt=json.loads((out/'foreign-address-worker-receipt.json').read_text());rows=[]
for case in receipt['rows']:
    raw=(out/case['file']).read_bytes();assert hashlib.sha256(raw).hexdigest()==case['sha256']
    rows.append({'file':case['file'],**verify_packet(raw,case,official_forms)})
result={'synthetic_only':True,'actual_worker_packets_read_back':len(rows),'rows':rows,'original_runtime_comparison':False,'native_UI_acceptance':False}
(out/'foreign-address-worker-pdf-readback.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
