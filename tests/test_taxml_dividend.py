"""Owned six-box DIV migration, source preservation and actual durable drafts.

The XML/XPRF are authored fixtures, not original saved returns or a native oracle.
"""
import base64
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from decimal import Decimal
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'web')]
import income_preparation
import return_metadata
import server
import tax_engine
import taxml_preparation as prep
import taxml_wire as wire
from test_taxml_native import document, entity_xml, form_xml, field_xml, HEADERS

AMOUNTS = {'ordinary': '1200.31', 'qualified': '300.15', 'capital_gain_distributions': '1000.25',
           'unrecaptured_1250_gain': '150.05', 'collectibles_gain': '100.05', 'federal_withholding': '200.49'}


def registry(extra=(), kinds=None, formats=None):
    fields = [(field, (kinds or {}).get(field, 11), (formats or {}).get(field, 0))
              for _, field, _ in prep.DIVIDEND_FIELDS] + list(extra)
    dictionary = struct.pack('<H', len(fields)) + b''.join(
        b'\xff' + field.encode().ljust(32, b' ') + struct.pack('<BBI', kind, fmt, 132)
        for field, kind, fmt in fields)
    form_id, formset = b'F1099D', b'S2025US1040PER'
    metadata = struct.pack('<H', 2) + bytes([len(form_id)]) + form_id + bytes([len(formset)]) + formset
    entries = [(18000, 42, metadata), (1900, 42, dictionary)]
    header = b'XPRF\0\1\x10\x0c\x0a\0\0\0' + struct.pack('<I', len(entries))
    offset, directory, bodies = len(header) + 12 * len(entries), b'', b''
    for kind, ident, content in entries:
        block = struct.pack('<IIH', len(content) + 10, len(content), 0) + content
        directory += struct.pack('<HHII', kind, ident, offset, len(block))
        bodies += block; offset += len(block)
    return header + directory + bodies


def form(amounts=None, missing=(), extra='', copy_number='1'):
    values = AMOUNTS if amounts is None else amounts
    fields = ''.join(field_xml(field, text=values[name]) for _, field, name in prep.DIVIDEND_FIELDS if field not in missing)
    return form_xml(fields=fields + extra, copy=copy_number, filecopy=copy_number).replace('FW2', 'F1099D')


def request(payload=None, carrier=None):
    carrier = registry() if carrier is None else carrier
    payload = document(entity_xml(form())) if payload is None else payload
    return {'base64': base64.b64encode(payload).decode(), 'container': 'plaintext_xml',
            'profile': {'format': 'tax-reborn-taxml-native-windows-profile-v1', 'tax_year': 2025,
                'entity_name': 'USIndividualTaxReturn', 'formset_name': 'OwnedSet',
                'formset_headers': dict(HEADERS), 'template': {'formset_id': 'S2025US1040PER',
                    'form_id': 'F1099D', 'carrier_sha256': wire.digest(carrier), 'resource_id': 42}},
            'carriers': [{'base64': base64.b64encode(carrier).decode(), 'sha256': wire.digest(carrier)}],
            'profile_acknowledged': True}


def candidate(req):
    return prep.inspect_request(req)['candidates'][0]


def corrected(req, amounts=None):
    c = candidate(req)
    return prep.export_request({'inspection': req, 'expected_candidate_sha256': c['receipt']['candidate_sha256'],
        'amounts': AMOUNTS if amounts is None else amounts, 'confirmed': True})


def prepared():
    req = request(); c = candidate(req); ident = str(uuid.uuid4())
    data = tax_engine.default_return(); data['name'] = 'Synthetic native DIV import'
    data['interest'] = [{'payer': 'Existing synthetic bank', 'taxable': '1000', 'tax_exempt': '0', 'federal_withholding': '0.49'}]
    data['dividends'] = [{'payer': 'Existing synthetic fund', 'ordinary': '0.49', 'qualified': '0', 'capital_gain_distributions': '0', 'federal_withholding': '0'},
        {'payer': 'Synthetic six-box fund', **c['amounts'], 'special_distribution_confirmed': True}]
    metadata = return_metadata.normalize(data, None, tax_engine.ROW_DEFAULTS['w2'])
    entry = metadata['income_document_records']['dividends'][1]
    entry.update(reviewed=True, reviewed_at=datetime.now(timezone.utc).isoformat(), reviewed_fingerprint=entry['row_fingerprint'],
        source_document={'document_id': str(uuid.uuid4()), 'return_id': ident, 'name': 'synthetic-native-dividend.xml', 'method': 'taxml', 'taxml_receipt': c['receipt']},
        taxml_dividend_boxes={key: format(Decimal(value), '.2f') for key, value in c['amounts'].items()})
    return {'id': ident, 'data': data, 'metadata': metadata}


class SixBoxImport(unittest.TestCase):
    def test_dollars_field_identity_and_manual_eligibility(self):
        result = prep.inspect_request(request()); c = result['candidates'][0]
        self.assertTrue(c['can_review']); self.assertEqual(c['record_type'], 'dividends'); self.assertEqual(c['amounts'], AMOUNTS)
        self.assertEqual(c['sources']['qualified']['field_id'], 'QDIV'); self.assertEqual(c['sources']['federal_withholding']['field_id'], 'L2')
        self.assertEqual(c['requires_manual_fields'], ['payer', 'supported_dividend_scope', 'qualified_dividend_eligibility'])
        self.assertFalse(result['full_return_imported']); self.assertFalse(result['original_program_acceptance_verified'])

    def test_every_missing_box_stays_unresolved(self):
        for box, field, _ in prep.DIVIDEND_FIELDS:
            with self.subTest(box=box):
                c = candidate(request(document(entity_xml(form(missing=[field])))))
                self.assertFalse(c['can_review']); self.assertIn(box, c['missing_boxes'])

    def test_present_zero_and_unverified_copy_zero(self):
        self.assertTrue(candidate(request(document(entity_xml(form({k:'0' for k in AMOUNTS})))))['can_review'])
        self.assertFalse(candidate(request(document(entity_xml(form(copy_number='0')))))['can_review'])

    def test_money_requires_actual_kind_and_format(self):
        for _, field, _ in prep.DIVIDEND_FIELDS:
            with self.subTest(field=field):
                self.assertFalse(candidate(request(carrier=registry(kinds={field:12})))['can_review'])
                self.assertFalse(candidate(request(carrier=registry(formats={field:1})))['can_review'])

    def test_adjusted_qualified_wrong_withholding_and_unsupported_sibling_block(self):
        for field in ('ADJQDIV','L4','EXINT','FIRTAX','NONDIV'):
            req = request(document(entity_xml(form(extra=field_xml(field,text='0')))),registry(extra=[(field,11,0)]))
            with self.subTest(field=field): self.assertFalse(candidate(req)['can_review'])
        self.assertFalse(candidate(request(document(entity_xml(form()+'<OTHER tpsType="form"/>'))))['can_review'])

    def test_used_override_negative_precision_and_subset_reject(self):
        payload=base64.b64decode(request()['base64'])
        for before,after in [(b'<td:value >1200.31',b'<td:value used="false">1200.31'),(b'<td:value >1200.31',b'<td:value overridden="true">1200.31'),(b'>1200.31</td:value>',b'>-1</td:value>'),(b'>1200.31</td:value>',b'>1.001</td:value>')]:
            with self.subTest(after=after):self.assertFalse(candidate(request(payload.replace(before,after,1)))['can_review'])
        for values in [{**AMOUNTS,'qualified':'1200.32'},{**AMOUNTS,'unrecaptured_1250_gain':'900.21','collectibles_gain':'100.05'}]:
            with self.subTest(values=values): self.assertFalse(candidate(request(document(entity_xml(form(values)))))['can_review'])

    def test_six_box_export_preserves_other_bytes_and_source(self):
        req=request();before=base64.b64decode(req['base64']);values={**AMOUNTS,'ordinary':'1200.32','federal_withholding':'201.49'}
        out=corrected(req,values);after=base64.b64decode(out['base64'])
        self.assertEqual(after,before.replace(b'>1200.31</td:value>',b'>1200.32</td:value>').replace(b'>200.49</td:value>',b'>201.49</td:value>'))
        self.assertEqual(candidate({**req,'base64':out['base64']})['amounts'],values);self.assertEqual(base64.b64decode(req['base64']),before)
        self.assertEqual(out['output_sha256'],wire.digest(after));self.assertFalse(out['full_return_recalculated'])

    def test_export_field_set_bounds_subset_stale_and_confirmation(self):
        req=request();c=candidate(req)
        for values in [{k:v for k,v in AMOUNTS.items()if k!='qualified'},{**AMOUNTS,'wages':'1'},{**AMOUNTS,'ordinary':'1.001'},{**AMOUNTS,'ordinary':'1000000001'},{**AMOUNTS,'qualified':'1200.32'},{**AMOUNTS,'collectibles_gain':'900.21'}]:
            with self.subTest(values=values),self.assertRaises(ValueError):corrected(req,values)
        for key,value in [('expected_candidate_sha256','0'*64),('confirmed',False)]:
            out={'inspection':req,'expected_candidate_sha256':c['receipt']['candidate_sha256'],'amounts':AMOUNTS,'confirmed':True};out[key]=value
            with self.assertRaises(ValueError):prep.export_request(out)

    def test_selected_copy_only(self):
        req=request(document(entity_xml(form()+form(copy_number='2'))));self.assertEqual(len(prep.inspect_request(req)['candidates']),2)
        out=corrected(req,{**AMOUNTS,'ordinary':'1201.31'});read=prep.inspect_request({**req,'base64':out['base64']})['candidates']
        self.assertEqual([x['amounts']['ordinary']for x in read],['1201.31','1200.31'])

    def test_actual_calculation_subsets_not_added_to_income_and_joint_rounding(self):
        payload=prepared();result=tax_engine.calculate_return(payload['data'])
        self.assertEqual(result['lines']['3b'],1201);self.assertEqual(result['lines']['3a'],300)
        self.assertEqual(result['lines']['7a'],1000);self.assertEqual(result['lines']['9'],3201)
        self.assertEqual(result['lines']['25b'],201);self.assertEqual(result['summary']['refund'],201)
        self.assertFalse(result['can_prepare']);self.assertFalse(payload['data']['eligibility']['all_income_reported'])


class DividendDurableSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory();cls.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.http.store=server.Store(cls.temporary.name)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start();cls.origin=f'http://127.0.0.1:{cls.http.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join();cls.temporary.cleanup()
    def call(self,path,payload=None):
        req=urllib.request.Request(self.origin+path,data=json.dumps(payload).encode()if payload else None,headers={'Origin':self.origin,'Content-Type':'application/json'})
        with urllib.request.urlopen(req)as response:return json.load(response)
    def test_actual_http_sqlite_save_reload_backup_and_edit_preserve_source(self):
        payload=prepared();saved=self.call('/api/returns',payload);reopened=self.call('/api/returns/'+saved['id']);backup=self.call('/api/returns/'+saved['id']+'/export.json')
        self.assertEqual(saved['metadata'],reopened['metadata']);self.assertEqual(backup['metadata'],saved['metadata']);self.assertEqual(saved['result']['summary']['refund'],201)
        payload['data']['dividends'][1]['ordinary']='1200.32';edited=self.call('/api/returns',payload)
        entry=edited['metadata']['income_document_records']['dividends'][1];old=saved['metadata']['income_document_records']['dividends'][1]
        self.assertFalse(entry['reviewed']);self.assertEqual(entry['source_document'],old['source_document']);self.assertEqual(entry['taxml_dividend_boxes'],old['taxml_dividend_boxes'])
    def test_source_snapshot_tampering_rejected_atomically(self):
        saved=self.call('/api/returns',prepared())
        for action in ('hash','remove','boxes','missing_box','subset'):
            payload=copy.deepcopy(saved);item=payload['metadata']['income_document_records']['dividends'][1]
            if action=='hash':item['source_document']['taxml_receipt']['source_sha256']='f'*64
            elif action=='remove':item.pop('source_document');item.pop('taxml_dividend_boxes')
            elif action=='boxes':item['taxml_dividend_boxes']['federal_withholding']='0.00'
            elif action=='subset':item['taxml_dividend_boxes']['qualified']='1200.32'
            else:item['taxml_dividend_boxes'].pop('qualified')
            with self.subTest(action=action),self.assertRaises(urllib.error.HTTPError)as caught:self.call('/api/returns',payload)
            caught.exception.close();self.assertEqual(self.call('/api/returns/'+saved['id'])['metadata'],saved['metadata'])

if __name__=='__main__':unittest.main()
