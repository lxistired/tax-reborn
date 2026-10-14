#!/usr/bin/env python3
"""Native desktop shell, private loopback backend and frozen API smoke check."""
from __future__ import annotations
import argparse
import http.client
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import platform
import socket
import sys
import tempfile
import threading
import server

PRODUCT_NAME = 'Tax Reborn'
VERSION = server.VERSION


class LocalService:
    def __init__(self,data_dir=None):
        directory = Path(data_dir or server.default_data_dir()).expanduser().resolve()
        self._windows_instance_file = None
        # IndexedDB uses the full origin. Keep this directory's local origin
        # stable across relaunches so document blobs and workspace state survive.
        port = 24000 + int(hashlib.sha256(os.path.normcase(str(directory)).encode()).hexdigest()[:8],16) % 20000
        try:
            if sys.platform == 'win32':
                # Windows allows HTTPServer's SO_REUSEADDR to bind an active
                # listener twice. Hold a workspace lock and reject an existing
                # listener before binding; keep normal immediate reopen working.
                import msvcrt
                directory.mkdir(parents=True,exist_ok=True)
                self._windows_instance_file = (directory/'.desktop-instance.lock').open('a+b')
                if self._windows_instance_file.seek(0,2) == 0:
                    self._windows_instance_file.write(b'\0')
                    self._windows_instance_file.flush()
                self._windows_instance_file.seek(0)
                msvcrt.locking(self._windows_instance_file.fileno(),msvcrt.LK_NBLCK,1)
                with socket.socket() as probe:
                    probe.settimeout(1)
                    if probe.connect_ex(('127.0.0.1',port)) == 0:
                        raise OSError('Workspace listener is already active')
            self.http = server.create_server(port=port,data_dir=directory)
        except OSError as error:
            if self._windows_instance_file:
                self._windows_instance_file.close()
                self._windows_instance_file = None
            raise RuntimeError('This local workspace port is already in use. Close its other Tax Reborn window or the conflicting local service, then reopen. A different origin was not selected because it would hide saved documents.') from error
        self.thread = threading.Thread(target=self.http.serve_forever,kwargs={'poll_interval':0.05},daemon=True)
        self.lock = threading.Lock()
        self.stopped = False
    @property
    def url(self):
        return f'http://127.0.0.1:{self.http.server_port}/'
    def start(self):
        self.thread.start()
        return self
    def stop(self,*args):
        with self.lock:
            if self.stopped:return
            self.stopped = True
            if self.thread.is_alive():self.http.shutdown()
            self.http.server_close()
            self.thread.join(timeout=5)
            if self._windows_instance_file:
                self._windows_instance_file.close()
                self._windows_instance_file = None
            if self.thread.is_alive():raise RuntimeError('Local tax service did not shut down')


def smoke_test(report_path=None):
    checks = []
    with tempfile.TemporaryDirectory(prefix='tax-reborn-packaged-smoke-') as folder:
        service = LocalService(Path(folder)/'data').start()
        port = service.http.server_port
        def request(method,path,payload=None,origin=None,host=None):
            conn = http.client.HTTPConnection('127.0.0.1',port,timeout=25)
            headers = {'Host':host or f'127.0.0.1:{port}'}
            if method in ('POST','DELETE'):
                headers.update({'Origin':origin or service.url.rstrip('/'),'Content-Type':'application/json'})
            body = json.dumps(payload).encode() if payload is not None else None
            conn.request(method,path,body,headers)
            response = conn.getresponse();raw = response.read();status=response.status
            kind = response.getheader('Content-Type','');conn.close()
            return status,json.loads(raw) if 'json' in kind else raw
        try:
            for path in ('/','/app.js','/style.css','/local-api.js','/tax-worker.js','/tax_engine.py','/tax_extended.py','/tax_credits.py','/tax_longtail.py','/tax_filing.py','/official_forms.py','/native-file-bridge.js','/forms/paper-fact-schema-2025.json','/state-worker.js','/state-workspace.js','/document-import.js','/rules_2025.json','/forms/f1040-2025.pdf','/vendor/pyodide/pyodide.asm.wasm'):
                status,raw=request('GET',path);assert status==200 and raw
            checks.append('Bundled desktop/mobile assets and IRS2025 template load')
            status,contract=request('GET','/api/schema');assert status==200 and contract['capabilities']['tax_year']==2025
            status,empty=request('GET','/api/returns');assert empty=={'returns':[]}
            checks.append('Empty private data and final input schema are available')
            data=contract['default_return'];data['name']='Packaged synthetic household'
            data['eligibility'].update(full_year_us_resident=True,filing_status_confirmed=True,all_income_reported=True,no_amt_preferences=True,eitc_not_applicable=True)
            data['w2']=[{'employer':'Synthetic example','wages':'60000','federal_withholding':'6500','social_security_wages':'60000','medicare_wages':'60000','social_security_withholding':'3720'}]
            data['interest']=[{'payer':'Synthetic bank','taxable':'100'}]
            status,result=request('POST','/api/calculate',data)
            assert status==200 and result['can_prepare'] and result['lines']['16']==5087 and result['summary']['refund']==1413
            checks.append('Real packaged tax engine matches independent official2025 tax table and refund')
            status,saved=request('POST','/api/returns',{'data':data});assert status==200
            ident=saved['id'];status,reopened=request('GET','/api/returns/'+ident)
            assert reopened['data']==data and reopened['result']['summary']['refund']==1413
            checks.append('Return input and results persist across independent HTTP connections')
            state_input={'jurisdiction':'il','filingStatus':'single','federalAGI':60100,'stateWithholding':3000}
            status,state_saved=request('POST',f'/api/returns/{ident}/states',{'jurisdiction':'il','input':state_input});assert status==200 and state_saved['states']['il']==state_input
            status,_=request('POST','/api/returns',{'id':ident,'data':data});assert status==200
            status,state_reopened=request('GET',f'/api/returns/{ident}/states');assert status==200 and state_reopened['states']['il']==state_input
            checks.append('State drafts persist independently and survive saving the federal return')
            status,raw=request('GET',f'/api/returns/{ident}/form1040.pdf');assert status==200 and raw.startswith(b'%PDF')
            import forms
            verified=forms.verify_fields(raw,forms.field_values(result));assert verified['pages']>=3 and verified['verified_fields']>=48
            checks.append('Interactive official1040 PDF fields and appearances verify after write')
            status,packet=request('GET',f'/api/returns/{ident}/paper-packet.pdf');assert status==200 and packet.startswith(b'%PDF')
            status,checklist=request('GET',f'/api/returns/{ident}/paper-checklist.json');assert status==200 and not checklist['transmitted'] and checklist['missing_facts']
            assert any(row['id']=='f1040sb' for row in checklist['supporting_forms'])
            checks.append('Real official supporting PDF packet and factual checklist without a false filing status')
            import io
            from pypdf import PdfReader
            import official_forms
            preflight=checklist['supporting_packet_preflight']
            assert preflight['page_identities_verified'] and preflight['expected_pages']==preflight['actual_pages']
            manifest=json.loads(PdfReader(io.BytesIO(packet)).metadata['/TaxRebornPacketManifest'])
            assert official_forms.verify_packet_pages(packet,manifest)['page_identities_verified']
            assert manifest['filing_packet_ready'] is False
            checks.append('Actual serialized packet pages and copy identities match the required plan')
            status,export=request('GET',f'/api/returns/{ident}/export.json');assert status==200 and export['data']==data
            status,worksheet=request('GET',f'/api/returns/{ident}/worksheet.html');assert status==200 and b'Not computed' in worksheet
            checks.append('JSON backup and printable worksheet export, without fabricated filing or penalty status')
            status,_=request('POST','/api/returns',{'id':ident,'data':data},origin='https://foreign.example');assert status==400
            status,_=request('GET','/api/returns',host='foreign.example');assert status==400
            status,_=request('GET','/../server.py');assert status==404
            checks.append('Foreign Origin, DNS-rebinding Host and file traversal rejected')
            data['adjustments']['hsa_deduction']='1000';status,blocked=request('POST','/api/calculate',data)
            assert status==200 and not blocked['can_prepare'] and blocked['blocking_issues']
            checks.append('Unsupported nonzero tax situation remains visibly blocked')
        finally:service.stop()
        with socket.socket() as probe:assert probe.connect_ex(('127.0.0.1',port))!=0
        checks.append('Service socket closes cleanly')
    report={'product':PRODUCT_NAME,'project_number':'000002','version':VERSION,'all_passed':True,
            'frozen':bool(getattr(sys,'frozen',False)),'platform':sys.platform,'machine':platform.machine(),
            'passed':len(checks),'checks':checks,'scope':'US2025 federal calculation and draft exports; no filing or fullTurboTax parity'}
    if report_path:
        report_path=Path(report_path);report_path.parent.mkdir(parents=True,exist_ok=True)
        report_path.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description='Tax Reborn - personal federal tax2025')
    parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--smoke-test',action='store_true')
    parser.add_argument('--smoke-report',type=Path)
    parser.add_argument('--version',action='version',version=VERSION)
    args=parser.parse_args()
    if args.smoke_test:
        smoke_test(args.smoke_report);return 0
    service=LocalService(args.data_dir).start()
    try:
        import webview
        webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER']=True
        webview.settings['ALLOW_DOWNLOADS']=True
        window=webview.create_window(PRODUCT_NAME,service.url,width=1360,height=900,min_size=(860,640),text_select=True,background_color='#f6f8fa')
        window.events.closed+=service.stop
        webview.start(gui='cocoa' if sys.platform=='darwin' else 'edgechromium' if sys.platform=='win32' else None,
                      private_mode=False,storage_path=str(service.http.data_dir/'webview'))
    finally:service.stop()
    return 0


if __name__=='__main__':
    multiprocessing.freeze_support()
    if sys.stdout is None:sys.stdout=open(os.devnull,'w')
    if sys.stderr is None:sys.stderr=open(os.devnull,'w')
    raise SystemExit(main())
