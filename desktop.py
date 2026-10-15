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
            for path in ('/','/app.js','/style.css','/local-api.js','/tax-worker.js','/tax_engine.py','/tax_special_capital.py','/tax_child_income.py','/tax_extended.py','/tax_credits.py','/tax_longtail.py','/tax_filing.py','/official_forms.py','/native-file-bridge.js','/forms/paper-fact-schema-2025.json','/state-worker.js','/state-workspace.js','/document-import.js','/rules_2025.json','/forms/f1040-2025.pdf','/vendor/pyodide/pyodide.asm.wasm'):
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
            import tax_engine
            special=next(row['data'] for row in tax_engine.demo_returns() if row['name']=='Synthetic 1099-DIV special distributions')
            status,special_saved=request('POST','/api/returns',{'data':special});assert status==200
            special_id=special_saved['id'];status,special_reopened=request('GET','/api/returns/'+special_id)
            assert status==200 and special_reopened['result']['can_prepare']
            assert special_reopened['result']['lines']['16']==16220 and special_reopened['result']['summary']['refund']==13780
            assert special_reopened['data']['dividends'][0]['unrecaptured_1250_gain']=='10000'
            status,special_packet=request('GET',f'/api/returns/{special_id}/paper-packet.pdf');assert status==200
            special_reader=PdfReader(io.BytesIO(special_packet));special_fields=special_reader.get_fields();prefix='f1040sd_1.topmostSubform[0].Page2[0].'
            assert str(special_fields[prefix+'f2_2[0]']['/V'])=='10000' and str(special_fields[prefix+'f2_3[0]']['/V'])=='10000'
            assert 'Worksheet line 47: $16,220' in '\n'.join(page.extract_text() for page in special_reader.pages)
            status,special_checklist=request('GET',f'/api/returns/{special_id}/paper-checklist.json')
            assert status==200 and special_checklist['paper_preparation_complete'] and not special_checklist['transmitted']
            checks.append('Packaged1099-DIV2a/2b/2d save/reopen, tax16220/refund13780, actualScheduleD18/19 and full47line workpaper read back')
            special_amt=next(row['data'] for row in tax_engine.demo_returns() if row['name']=='Synthetic 1099-DIV special AMT')
            status,amt_saved=request('POST','/api/returns',{'data':special_amt});assert status==200
            amt_id=amt_saved['id'];status,amt_reopened=request('GET','/api/returns/'+amt_id)
            assert status==200 and amt_reopened['result']['can_prepare']
            assert amt_reopened['result']['lines']['16']==5413 and amt_reopened['result']['lines']['17']==13624
            assert amt_reopened['result']['summary']['refund']==10963
            status,amt_packet=request('GET',f'/api/returns/{amt_id}/paper-packet.pdf');assert status==200
            amt_reader=PdfReader(io.BytesIO(amt_packet));amt_fields=amt_reader.get_fields()
            fixture=next(c for c in json.loads((server.BASE/'fixtures/special_amt_2025.json').read_text())['cases'] if c['id']=='IRS2025-AMT-special-005')
            prefixes={key.split('.topmostSubform',1)[0]+'.' for key in amt_fields if key.startswith('f6251_') and '.topmostSubform' in key};assert len(prefixes)==1
            amt_prefix=prefixes.pop()
            for line,value in fixture['expected_partIII'].items():
                assert str(amt_fields[amt_prefix+official_forms.MAP['f6251']['line_fields'][line]]['/V'])==str(value)
            assert str(amt_fields['topmostSubform[0].Page2[0].f2_09[0]']['/V'])=='13624'
            assert sum(page.get('/TaxRebornForm')=='f6251' for page in amt_reader.pages)==2
            checks.append('Packaged special AMT13624/refund10963 survives save/reopen; actual2page6251 all29PartIII fields match independentIRS fixture and1040line17')
            child=next(row['data'] for row in tax_engine.demo_returns() if row['name']=='Synthetic parent and child income')
            status,child_saved=request('POST','/api/returns',{'data':child});assert status==200
            child_id=child_saved['id'];status,child_reopened=request('GET','/api/returns/'+child_id)
            assert status==200 and child_reopened['result']['can_prepare']
            assert child_reopened['result']['lines']['16']==37467 and child_reopened['result']['lines']['24']==37516 and child_reopened['result']['lines']['35a']==12484
            status,child_packet=request('GET',f'/api/returns/{child_id}/paper-packet.pdf');assert status==200
            child_reader=PdfReader(io.BytesIO(child_packet));child_fields=child_reader.get_fields()
            cp='f8814_0.topmostSubform[0].Page1[0].'
            for suffix,value in {'f1_04[0]':'111111111','f1_14[0]':'150','f1_16[0]':'250','f1_17[0]':'195','f1_18[0]':'325','f1_20[0]':'780','f1_23[0]':'135'}.items():assert str(child_fields[cp+suffix]['/V'])==value
            assert str(child_fields['topmostSubform[0].Page2[0].c2_9[0]']['/V'])=='/1'
            assert len(child_reader.pages)==12 and sum(page.get('/TaxRebornForm')=='f8814' for page in child_reader.pages)==1
            status,child_checklist=request('GET',f'/api/returns/{child_id}/paper-checklist.json');assert status==200 and child_checklist['paper_preparation_complete'] and not child_checklist['transmitted']
            checks.append('Packaged Form8814 allocations195/325/780 and135 extra tax persist; parenttax37516/refund12484, actual12page packet andsplitratio/1040checkbox verified')
            birthday=next(row['data'] for row in tax_engine.demo_returns() if row['name']=='Synthetic EIC birthday boundary')
            status,birthday_saved=request('POST','/api/returns',{'data':birthday});assert status==200
            birthday_id=birthday_saved['id'];assert birthday_saved['result']['lines']['27a']==649 and birthday_saved['result']['lines']['35a']==1649
            birthday['taxpayer']['birth_date']='2001-01-02'
            status,birthday_changed=request('POST','/api/returns',{'id':birthday_id,'data':birthday});assert status==200
            status,birthday_reopened=request('GET','/api/returns/'+birthday_id)
            assert birthday_reopened['data']['taxpayer']['birth_date']=='2001-01-02' and birthday_reopened['result']['lines']['35a']==1000
            status,birthday_pdf=request('GET',f'/api/returns/{birthday_id}/form1040.pdf');assert status==200
            birthday_fields=PdfReader(io.BytesIO(birthday_pdf)).get_fields();assert str(birthday_fields['topmostSubform[0].Page2[0].c2_13[0]']['/V'])=='/1'
            birthday['taxpayer']['birth_date']='2001-02-29'
            status,_=request('POST','/api/returns',{'id':birthday_id,'data':birthday});assert status==400
            status,birthday_unchanged=request('GET','/api/returns/'+birthday_id);assert birthday_unchanged==birthday_reopened
            checks.append('Packaged DOB2001-01-01 to01-02 changes EIC649 to0/refund1649 to1000; saveddate/result survive reopen and invalid date cannot overwrite')
            birthday['taxpayer']['birth_date']='1961-01-01'
            birthday['schedule_1a']['eligibility_confirmed']=True
            birthday['elderly_credit'].update(enabled=True,eligibility_confirmed=True,nontaxable_benefits_confirmed=True)
            status,older=request('POST','/api/returns',{'id':birthday_id,'data':birthday});assert status==200 and older['result']['can_prepare']
            assert older['result']['lines']['27a']==649 and older['result']['lines']['12e']==17750 and older['result']['lines']['13b']==6000
            status,older_pdf=request('GET',f'/api/returns/{birthday_id}/form1040.pdf');assert status==200
            older_fields=PdfReader(io.BytesIO(older_pdf)).get_fields();pp='topmostSubform[0].Page2[0].'
            assert str(older_fields[pp+'f2_23[0]']['/V'])=='649' and str(older_fields[pp+'f2_31[0]']['/V'])=='1649' and str(older_fields[pp+'c2_5[0]']['/V'])=='/1'
            checks.append('Actualpackaged Jan1,1961 independently qualifies forEIC andage65 deductions; serialized1040 EIC/refund/seniorcheckbox verified')
            high=server.tax_engine.default_return();high['name']='Synthetic packaged NIIT and positive AMT'
            high['eligibility'].update(full_year_us_resident=True,filing_status_confirmed=True,all_income_reported=True,no_amt_preferences=True,capital_gains_eligible=True,eitc_not_applicable=True)
            high['niit'].update(eligibility_confirmed=True,deductions_confirmed=True);high['amt']['eligibility_confirmed']=True
            high['identity'].update(first_name='Synthetic',last_name='Taxpayer',ssn='123456789',address='100 Example Street',city='Example City',state='IL',zip='60000')
            high['filing_details'].update(digital_asset_answer='no',main_home_us_answer='yes')
            high['filing_details']['official_form_facts']['schedule_b'].update(foreign_account_answer='no',fbar_required_answer='no',foreign_trust_answer='no',facts_confirmed=True)
            high['w2']=[{'employer':'Synthetic employer','wages':'190000','medicare_wages':'190000','federal_withholding':'250000'}]
            high['interest']=[{'payer':'Synthetic bank','taxable':'1000'}]
            high['dividends']=[{'payer':'Synthetic fund','ordinary':'1000','qualified':'0','capital_gain_distributions':'800000'}]
            status,high_saved=request('POST','/api/returns',{'data':high});assert status==200 and high_saved['result']['can_prepare']
            high_id=high_saved['id'];status,high_reopened=request('GET','/api/returns/'+high_id);assert high_reopened==high_saved
            assert {k:high_reopened['result']['lines'][k] for k in ('16','17','23','24','35a')}=={'16':177290,'17':14773,'23':30096,'24':222159,'35a':27841}
            status,high_pdf=request('GET',f'/api/returns/{high_id}/paper-packet.pdf');assert status==200
            high_fields=PdfReader(io.BytesIO(high_pdf)).get_fields();high_expected={}
            for suffix,value in [('f1_9[0]',800000),('f1_12[0]',800000),('f1_19[0]',0),('f1_27[0]',30096)]:
                keys=[k for k in high_fields if k.startswith('f8960_') and k.endswith('.topmostSubform[0].Page1[0].'+suffix)];assert len(keys)==1;high_expected[keys[0]]=str(value)
            for number,value in [(8,177290),(9,14773),(15,30096),(16,222159),(31,27841)]:high_expected[f'topmostSubform[0].Page2[0].f2_{number:02d}[0]']=str(value)
            official_forms.verify_official_pdf(high_pdf,high_expected)
            status,high_checklist=request('GET',f'/api/returns/{high_id}/paper-checklist.json');assert status==200 and high_checklist['paper_preparation_complete'] and not high_checklist['filing_packet_ready']
            checks.append('Packaged positive AMT14773/NIIT30096/refund27841 save/reopen and complete printed8960 component rows survive actual interactive PDF export')
            high['name']='Synthetic packaged payment voucher'
            high['w2'][0]['federal_withholding']='1000'
            high['estimated_penalty'].update(enabled=True,prior_year_tax='0',prior_year_agi='0',prior_year_full_12_months=True,prior_year_tax_verified=True,no_prior_year_tax_full_year_resident_confirmed=True,actual_payment_records_confirmed=True)
            high['filing_details'].update(balance_due_payment_method='check_money_order',paper_payment_amount_source='custom',paper_payment_amount='1000.25',paper_payment_confirmed=True)
            status,voucher_saved=request('POST','/api/returns',{'data':high});assert status==200 and voucher_saved['result']['can_prepare']and voucher_saved['result']['lines']['37']==221159
            voucher_id=voucher_saved['id'];status,voucher_reopened=request('GET','/api/returns/'+voucher_id);assert voucher_reopened==voucher_saved
            status,voucher_pdf=request('GET',f'/api/returns/{voucher_id}/paper-packet.pdf');assert status==200
            voucher_fields=PdfReader(io.BytesIO(voucher_pdf)).get_fields();keys=[k for k in voucher_fields if k.startswith('f1040v_')and k.endswith('.topmostSubform[0].Page1[0].f1_3[0]')];assert len(keys)==1
            official_forms.verify_official_pdf(voucher_pdf,{keys[0]:'1000.25','topmostSubform[0].Page2[0].f2_35[0]':'221159'})
            status,voucher_status=request('GET',f'/api/returns/{voucher_id}/paper-checklist.json');assert status==200 and voucher_status['paper_preparation_complete']and not voucher_status['payment_voucher']['payment_initiated']
            checks.append('Packaged221159 USD balance and separate1000.25 paper-payment voucher save/reopen and actual official1040-V PDF preserve cents without recording payment')
            high['name']='Synthetic packaged foreign mailing address'
            high['filing_details']['mailing_address_type']='foreign'
            high['identity'].update(city='Berlin',foreign_country='Germany',foreign_province='Berlin',foreign_postal_code='10115')
            status,foreign_saved=request('POST','/api/returns',{'data':high});assert status==200
            assert foreign_saved['result']['lines']==voucher_saved['result']['lines']
            status,foreign_reopened=request('GET','/api/returns/'+foreign_saved['id']);assert foreign_reopened==foreign_saved
            assert foreign_reopened['data']['identity']['state']==high['identity']['state']
            status,foreign_pdf=request('GET',f"/api/returns/{foreign_saved['id']}/paper-packet.pdf");assert status==200
            foreign_fields=PdfReader(io.BytesIO(foreign_pdf)).get_fields();foreign_expected={}
            for number,value in [(22,'Berlin'),(23,''),(24,''),(25,'Germany'),(26,'Berlin'),(27,'10115')]:
                key=f'topmostSubform[0].Page1[0].Address_ReadOrder[0].f1_{number}[0]'
                assert str(foreign_fields[key].get('/V',''))==value
                if value:foreign_expected[key]=value
            for number,value in [(11,'Berlin'),(12,''),(13,''),(14,'Germany'),(15,'Berlin'),(16,'10115')]:
                keys=[k for k in foreign_fields if k.startswith('f1040v_') and k.endswith(f'.topmostSubform[0].Page1[0].f1_{number}[0]')];assert len(keys)==1
                assert str(foreign_fields[keys[0]].get('/V',''))==value
                if value:foreign_expected[keys[0]]=value
            official_forms.verify_official_pdf(foreign_pdf,foreign_expected)
            status,foreign_status=request('GET',f"/api/returns/{foreign_saved['id']}/paper-checklist.json");assert status==200 and foreign_status['paper_preparation_complete']
            checks.append('Packaged foreign mailing address save/reopen and actual1040/1040-V country/province/postal/AP rows verified; inactive US rows blank, inputs and tax retained')
            high['name']='Synthetic legacy foreign mailing address'
            del high['filing_details']['mailing_address_type'];high['identity'].update(state='',zip='')
            status,legacy_saved=request('POST','/api/returns',{'data':high});assert status==200
            legacy_cached=legacy_saved['result'];legacy_cached['form_readiness']['missing_identity']=['State','ZIP code']
            with server.Store(Path(folder)/'data').connect()as connection:
                connection.execute('UPDATE returns SET result=? WHERE id=?',(json.dumps(legacy_cached),legacy_saved['id']))
            status,legacy_status=request('GET',f"/api/returns/{legacy_saved['id']}/paper-checklist.json");assert status==200 and legacy_status['paper_preparation_complete']
            status,legacy_pdf=request('GET',f"/api/returns/{legacy_saved['id']}/paper-packet.pdf");assert status==200
            official_forms.verify_official_pdf(legacy_pdf,foreign_expected)
            checks.append('Packaged legacy foreign address without selector and stale cached US readiness still exports current foreign address packet; US tax unchanged')
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
        from desktop_export import DesktopExport
        exports=DesktopExport(service.url)
        window=webview.create_window(PRODUCT_NAME,service.url+'?desktop=1',width=1360,height=900,min_size=(860,640),text_select=True,background_color='#f6f8fa',js_api=exports)
        exports._window=window
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
