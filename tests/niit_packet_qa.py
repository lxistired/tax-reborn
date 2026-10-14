"""Host HTTP/SQLite and exported canonical/widget checks with synthetic facts."""
from pathlib import Path
from http.server import ThreadingHTTPServer
import hashlib
import io
import json
import tempfile
import threading
from urllib.request import Request, urlopen

from pypdf import PdfReader
from capital_niit_amt_qa import cases, return_for


# Literal printed-row widget identities verified on the public IRS TY2025
# forms, independent of the application's mapping and renderer.
NIIT_WIDGET_NUMBERS = {'1':3,'2':4,'3':5,'4a':6,'4b':7,'4c':8,
    '5a':9,'5b':10,'5c':11,'5d':12,'6':13,'7':14,'8':15,'9a':16,
    '9b':17,'9c':18,'9d':19,'10':20,'11':21,'12':22,'13':23,
    '14':24,'15':25,'16':26,'17':27}
AMT_WIDGETS = {'4':(1,26),'5':(1,27),'6':(1,28),'9':(1,31),
    '10':(1,32),'11':(1,33),'17':(2,6),'18':(2,7),'23':(2,12),
    '30':(2,19),'31':(2,20),'33':(2,22),'34':(2,23),
    '38':(2,27),'39':(2,28),'40':(2,29)}


def expected_niit(case):
    detail = case['IRS_detail']
    return {'1':case['taxable_interest'],'2':case['ordinary_dividends'],
        '3':0,'4a':0,'4b':0,'4c':0,'5a':case['expected']['7a'],
        '5b':0,'5c':0,'5d':case['expected']['7a'],'6':0,'7':0,
        '8':detail['NIIT_8'],'9a':0,'9b':0,'9c':0,'9d':0,'10':0,
        '11':0,'12':detail['NIIT_12'],'13':detail['NIIT_13'],
        '14':detail['NIIT_14'],'15':detail['NIIT_15'],
        '16':detail['NIIT_16'],'17':detail['NIIT_17']}


def verify_pdf(pdf, case, official_forms, forms):
    reader = PdfReader(io.BytesIO(pdf))
    fields = reader.get_fields()
    expected = {}

    def require(form_id, suffix, value):
        matches = [key for key in fields if key.startswith(form_id+'_') and key.endswith('.'+suffix)]
        assert len(matches) == 1, (form_id, suffix, matches)
        expected[matches[0]] = str(value)

    for line, value in expected_niit(case).items():
        require('f8960', 'topmostSubform[0].Page1[0].f1_'+str(NIIT_WIDGET_NUMBERS[line])+'[0]', value)
    if case['expected']['17']:
        for line, (page, number) in AMT_WIDGETS.items():
            value = case['IRS_detail'].get('AMT_'+line)
            if line == '10': value = case['expected']['16']
            if line == '11': value = case['expected']['17']
            if line == '40': value = case['IRS_detail']['AMT_9']
            require('f6251', f'topmostSubform[0].Page{page}[0].f{page}_{number}[0]', value)
    require('f1040s2', 'form1[0].Page1[0].f1_12[0]', case['expected']['17'])
    require('f1040s2', 'form1[0].Page1[0].f1_23[0]', case['expected']['23'])
    require('f1040s2', 'form1[0].Page2[0].f2_24[0]', case['expected']['23'])
    for number, line in [(8,'16'),(9,'17'),(15,'23'),(16,'24'),(20,'25d'),(29,'33'),(31,'35a'),(35,'37')]:
        key = f'topmostSubform[0].Page2[0].f2_{number:02d}[0]'
        expected[key] = str(case['expected'][line])
    # Canonical fields, inherited page widgets and nonempty appearances are
    # all checked against the independently supplied dollar/row oracle.
    logical = official_forms.verify_official_pdf(pdf, expected)
    manifest = json.loads(reader.metadata['/TaxRebornPacketManifest'])
    pages = official_forms.verify_packet_pages(pdf, manifest)
    assert not manifest['filing_packet_ready']
    return {'canonical_and_widget_fields':logical['verified_fields'],
        'pages':len(reader.pages),'page_identities_verified':pages['page_identities_verified'],
        'expected_fields':expected,'packet_manifest':manifest}


def check_http_packet(output_dir=None):
    import server, tax_engine, official_forms, forms
    rows = []
    with tempfile.TemporaryDirectory(prefix='tax-niit-packet-') as temp:
        store = Path(temp)
        http = ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        http.store = server.Store(store)
        thread = threading.Thread(target=lambda: http.serve_forever(poll_interval=.01),daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{http.server_port}'

        def request(path, payload=None):
            request = Request(origin+path,
                data=json.dumps(payload).encode() if payload is not None else None,
                headers={'Origin':origin,'Content-Type':'application/json'})
            with urlopen(request,timeout=30) as response:
                assert response.status == 200
                return response.read()

        try:
            for case in cases()[:2]:
                data = return_for(tax_engine,case)
                data['identity'].update(first_name='Synthetic',last_name='Taxpayer',ssn='123456789',
                    address='100 Example Street',city='Example City',state='IL',zip='60000')
                data['filing_details'].update(digital_asset_answer='no',main_home_us_answer='yes')
                data['filing_details']['official_form_facts']['schedule_b'].update(
                    foreign_account_answer='no',fbar_required_answer='no',foreign_trust_answer='no',facts_confirmed=True)
                saved = json.loads(request('/api/returns',{'data':data}))
                assert saved['result']['can_prepare']
                assert {k:saved['result']['lines'][k] for k in case['expected']} == case['expected']
                path = '/api/returns/'+saved['id']
                reopened = json.loads(request(path))
                assert reopened == saved
                # A fresh Store/SQLite connection must read the saved record,
                # including the new printed NIIT rows, without recomputation.
                assert server.Store(store).get(saved['id']) == saved
                exported = json.loads(request(path+'/export.json'))
                assert exported['data'] == saved['data'] and exported['result'] == saved['result']
                assert reopened['result']['schedules']['form_8960']['form_lines'] == expected_niit(case)
                pdf = request(path+'/paper-packet.pdf')
                proof = verify_pdf(pdf,case,official_forms,forms)
                checklist = json.loads(request(path+'/paper-checklist.json'))
                assert checklist['calculation_ready'] and not checklist['transmitted'] and not checklist['filing_packet_ready']
                assert checklist['paper_preparation_complete'] and checklist['missing_facts'] == []
                assert json.loads(request(path)) == saved
                row = {'name':case['name'],'sqlite_reopen_exact':True,'fresh_sqlite_connection_exact':True,
                    'json_export_exact':True,'actual_HTTP_pdf_export':True,'saved_record_unchanged_after_exports':True,
                    'PDF_sha256':hashlib.sha256(pdf).hexdigest(),**proof,
                    'missing_paper_facts':checklist['missing_facts'],'electronic_filing':False}
                if output_dir:
                    output_dir.mkdir(parents=True,exist_ok=True)
                    (output_dir/(case['name']+'-paper-packet.pdf')).write_bytes(pdf)
                rows.append(row)
        finally:
            http.shutdown(); http.server_close(); thread.join()
    return {'synthetic_only':True,'tax_year':2025,'cases':len(rows),'passed':len(rows),
        'rows':rows,'scope':'Actual source HTTP/SQLite and exported interactive IRS fields; native package and original .tax acceptance are separate.'}
