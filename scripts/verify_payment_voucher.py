"""Generate independently checked synthetic payment-voucher packet artifacts."""
from pathlib import Path
import sys,argparse,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from payment_voucher_qa import cases,return_for,verify_packet
import tax_engine,forms,official_forms

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);args=p.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True);rows=[]
    for name,case,custom in [('balance-due',cases()[2],None),('custom-cents',cases()[0],'1000.25')]:
        d=return_for(tax_engine,case)
        if custom:d['filing_details'].update(paper_payment_amount_source='custom',paper_payment_amount=custom)
        result=tax_engine.calculate_return(d);record={'data':d,'result':result};status=forms.packet_status(record);assert status['paper_preparation_complete']and not status['filing_packet_ready']
        raw=forms.paper_packet_pdf(record);proof=verify_packet(raw,custom or str(case['owed'])+'.00',official_forms);target=args.output_dir/(name+'-official-packet.pdf');target.write_bytes(raw)
        rows.append({'case':name,'Form1040_line37':result['lines']['37'],'voucher_amount':status['payment_voucher']['amount'],'PDF_sha256':hashlib.sha256(raw).hexdigest(),'proof':proof,'payment_initiated':False})
    (args.output_dir/'official-voucher-packet-receipt.json').write_text(json.dumps({'tax_year':2025,'synthetic_only':True,'cases':2,'passed':2,'rows':rows},indent=2)+'\n');print('Two actual official voucher packets passed')
