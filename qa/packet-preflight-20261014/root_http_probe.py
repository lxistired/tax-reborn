"""Root acceptance through actual HTTP and SQLite; synthetic returns only."""
import hashlib, io, json, sys, tempfile, threading
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import server, forms, official_forms, tax_engine
from pypdf import PdfReader
from tests.test_paper_packet import example
from tests.test_official_forms import business_sample
OUT=Path(__file__).parent
receipt={'synthetic_only':True,'checks':[],'electronic_filing':False}
with tempfile.TemporaryDirectory(prefix='tax-packet-http-') as temp:
    http=server.create_server(0,Path(temp));thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(http.server_port)
    def request(path,payload=None):
        raw=None if payload is None else json.dumps(payload).encode()
        with urlopen(Request(base+path,data=raw,headers={'Content-Type':'application/json','Origin':base}),timeout=30) as res:
            return res.status,res.read()
    try:
        for label,data in [('simple',example()['data']),('business',business_sample()['data'])]:
            code,raw=request('/api/returns',{'data':data});record=json.loads(raw);rid=record['id']
            before=request('/api/returns/'+rid)[1]
            _,raw=request('/api/returns/'+rid+'/paper-checklist.json');status=json.loads(raw)
            proof=status['supporting_packet_preflight']
            assert proof['page_identities_verified'] is True
            assert proof['expected_pages']==proof['actual_pages']
            assert status['filing_packet_ready'] is False and status['transmitted'] is False
            code,pdf=request('/api/returns/'+rid+'/paper-packet.pdf')
            assert code==200
            reader=PdfReader(io.BytesIO(pdf));manifest=json.loads(reader.metadata['/TaxRebornPacketManifest'])
            final=official_forms.verify_packet_pages(pdf,manifest)
            assert len(reader.pages)==manifest['expected_pdf_pages']
            assert manifest['filing_packet_ready'] is False
            assert request('/api/returns/'+rid)[1]==before
            _,single=request('/api/returns/'+rid+'/form1040.pdf')
            standalone=PdfReader(io.BytesIO(single))
            # This endpoint includes a cover and calculation workpapers in
            # addition to the two selected official 1040 pages.
            assert len(standalone.pages)>=3
            single_fields=standalone.get_fields()
            packet_fields=reader.get_fields()
            assert all(str(v.get('/V'))==str(packet_fields[k].get('/V')) for k,v in single_fields.items())
            OUT.joinpath(label+'-paper-packet.pdf').write_bytes(pdf)
            receipt['checks'].append({'case':label,'actual_http_export':True,'sqlite_return_unchanged':True,'standalone_1040_pdf_pages':len(standalone.pages),'standalone_1040_field_values_preserved':True,'final_pages':len(reader.pages),'supporting_pages':proof['actual_pages'],'final_page_identities_verified':final['page_identities_verified'],'sha256':hashlib.sha256(pdf).hexdigest()})
    finally:
        http.shutdown();http.server_close();thread.join(timeout=5)
receipt['passed']=all(x['actual_http_export'] and x['sqlite_return_unchanged'] and x['final_page_identities_verified'] for x in receipt['checks'])
OUT.joinpath('root-http-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
