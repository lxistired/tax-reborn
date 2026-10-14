"""Owned four-box INT migration, corrected XML and durable source provenance.

The XPRF/XML specimens are independently authored. No original saved return or
native TurboTax execution is asserted by these tests.
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

AMOUNTS = {'interest_income': '100.23', 'treasury_interest': '40.27',
           'tax_exempt_interest': '12.34', 'federal_withholding': '20.45'}


def registry(extra=(), kinds=None, formats=None):
    fields = [(field, (kinds or {}).get(field, 11), (formats or {}).get(field, 0))
              for _, field, _ in prep.INTEREST_FIELDS] + list(extra)
    dictionary = struct.pack('<H', len(fields)) + b''.join(
        b'\xff' + field.encode().ljust(32, b' ') + struct.pack('<BBI', kind, fmt, 132)
        for field, kind, fmt in fields)
    form, formset = b'F1099I', b'S2025US1040PER'
    metadata = struct.pack('<H', 2) + bytes([len(form)]) + form + bytes([len(formset)]) + formset
    entries = [(18000, 41, metadata), (1900, 41, dictionary)]
    header = b'XPRF\0\1\x10\x0c\x0a\0\0\0' + struct.pack('<I', len(entries))
    offset, directory, bodies = len(header) + 12 * len(entries), b'', b''
    for kind, ident, content in entries:
        block = struct.pack('<IIH', len(content) + 10, len(content), 0) + content
        directory += struct.pack('<HHII', kind, ident, offset, len(block))
        bodies += block; offset += len(block)
    return header + directory + bodies


def form(amounts=None, missing=(), extra='', copy_number='1'):
    values = AMOUNTS if amounts is None else amounts
    fields = ''.join(field_xml(field, text=values[name]) for _, field, name in prep.INTEREST_FIELDS if field not in missing)
    return form_xml(fields=fields + extra, copy=copy_number, filecopy=copy_number).replace('FW2', 'F1099I')


def request(payload=None, carrier=None):
    carrier = registry() if carrier is None else carrier
    payload = document(entity_xml(form())) if payload is None else payload
    return {'base64': base64.b64encode(payload).decode(), 'container': 'plaintext_xml',
            'profile': {'format': 'tax-reborn-taxml-native-windows-profile-v1', 'tax_year': 2025,
                'entity_name': 'USIndividualTaxReturn', 'formset_name': 'OwnedSet',
                'formset_headers': dict(HEADERS), 'template': {'formset_id': 'S2025US1040PER',
                    'form_id': 'F1099I', 'carrier_sha256': wire.digest(carrier), 'resource_id': 41}},
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
    data = tax_engine.default_return(); data['name'] = 'Synthetic native INT import'
    data['interest'] = [{'payer': 'Existing synthetic bank', 'taxable': '0.49', 'tax_exempt': '0', 'federal_withholding': '0'},
        {'payer': 'Synthetic Treasury bank', 'taxable': str(Decimal(c['amounts']['interest_income']) + Decimal(c['amounts']['treasury_interest'])),
         'tax_exempt': c['amounts']['tax_exempt_interest'], 'federal_withholding': c['amounts']['federal_withholding']}]
    metadata = return_metadata.normalize(data, None, tax_engine.ROW_DEFAULTS['w2'])
    entry = metadata['income_document_records']['interest'][1]
    entry.update(reviewed=True, reviewed_at=datetime.now(timezone.utc).isoformat(), reviewed_fingerprint=entry['row_fingerprint'],
        source_document={'document_id': str(uuid.uuid4()), 'return_id': ident, 'name': 'synthetic-native-interest.xml', 'method': 'taxml', 'taxml_receipt': c['receipt']},
        taxml_interest_boxes={key: format(Decimal(value), '.2f') for key, value in c['amounts'].items()})
    return {'id': ident, 'data': data, 'metadata': metadata}


class FourBoxImport(unittest.TestCase):
    def test_dollar_values_not_divided_by_100_and_copy_context_retained(self):
        result = prep.inspect_request(request()); c = result['candidates'][0]
        self.assertTrue(c['can_review']); self.assertEqual(c['record_type'], 'interest')
        self.assertEqual(c['amounts'], AMOUNTS); self.assertEqual(c['source_owner']['copyNum'], '1')
        self.assertEqual(c['requires_manual_fields'], ['payer', 'supported_interest_scope'])
        self.assertFalse(result['full_return_imported']); self.assertFalse(result['original_program_acceptance_verified'])

    def test_missing_box_does_not_establish_zero(self):
        for box, field, _ in prep.INTEREST_FIELDS:
            with self.subTest(box=box):
                c = candidate(request(document(entity_xml(form(missing=[field])))))
                self.assertFalse(c['can_review']); self.assertIn(box, c['missing_boxes'])

    def test_explicit_zero_is_present_and_copy_zero_is_blocked(self):
        c = candidate(request(document(entity_xml(form({k:'0' for k in AMOUNTS})))))
        self.assertTrue(c['can_review']); self.assertEqual(set(c['amounts'].values()), {'0'})
        self.assertFalse(candidate(request(document(entity_xml(form(copy_number='0')))))['can_review'])

    def test_kind_or_format_mismatch_cannot_be_money(self):
        for _, field, _ in prep.INTEREST_FIELDS:
            with self.subTest(field=field):
                self.assertFalse(candidate(request(carrier=registry(kinds={field:12})))['can_review'])
                self.assertFalse(candidate(request(carrier=registry(formats={field:1})))['can_review'])

    def test_adjustments_and_unknown_sibling_block_entire_import(self):
        for field in ('L2', 'PAB', 'PREM', 'FOREIGN', 'TAX'):
            req = request(document(entity_xml(form(extra=field_xml(field, text='0')))), registry(extra=[(field,11,0)]))
            with self.subTest(field=field): self.assertFalse(candidate(req)['can_review'])
        req = request(document(entity_xml(form() + '<OTHER tpsType="form"/>')))
        self.assertFalse(candidate(req)['can_review'])

    def test_flags_and_negative_amounts_block(self):
        payload = base64.b64decode(request()['base64'])
        for before, after in [(b'<td:value >100.23', b'<td:value used="false">100.23'),
                              (b'<td:value >100.23', b'<td:value overridden="true">100.23'),
                              (b'>100.23</td:value>', b'>-1</td:value>')]:
            with self.subTest(after=after): self.assertFalse(candidate(request(payload.replace(before,after,1)))['can_review'])

    def test_four_box_correction_preserves_other_bytes_and_reparses(self):
        req = request(); before = base64.b64decode(req['base64']); values={**AMOUNTS, 'interest_income':'100.24', 'federal_withholding':'22.45'}
        out = corrected(req, values); after=base64.b64decode(out['base64'])
        self.assertEqual(after, before.replace(b'>100.23</td:value>',b'>100.24</td:value>').replace(b'>20.45</td:value>',b'>22.45</td:value>'))
        self.assertEqual(candidate({**req,'base64':out['base64']})['amounts'], values)
        self.assertEqual(base64.b64decode(req['base64']),before); self.assertFalse(out['full_return_recalculated'])
        self.assertEqual(out['output_sha256'],wire.digest(after)); self.assertEqual(set(out['edited_fields']),set(AMOUNTS))

    def test_wrong_field_set_precision_stale_and_unconfirmed_export_reject(self):
        req=request(); c=candidate(req)
        for values in [{k:v for k,v in AMOUNTS.items() if k!='treasury_interest'}, {**AMOUNTS,'wages':'1'},
                       {**AMOUNTS,'interest_income':'1.001'}, {**AMOUNTS,'interest_income':'-1'}, {**AMOUNTS,'interest_income':'1000000001'}]:
            with self.subTest(values=values), self.assertRaises(ValueError): corrected(req,values)
        for key,value in [('expected_candidate_sha256','0'*64),('confirmed',False)]:
            out={'inspection':req,'expected_candidate_sha256':c['receipt']['candidate_sha256'],'amounts':AMOUNTS,'confirmed':True};out[key]=value
            with self.assertRaises(ValueError):prep.export_request(out)

    def test_edit_one_selected_copy_preserves_other(self):
        req=request(document(entity_xml(form()+form(copy_number='2'))));cs=prep.inspect_request(req)['candidates'];self.assertEqual(len(cs),2)
        out=corrected(req,{**AMOUNTS,'interest_income':'101.23'});read=prep.inspect_request({**req,'base64':out['base64']})['candidates']
        self.assertEqual([x['amounts']['interest_income'] for x in read],['101.23','100.23'])

    def test_federal_engine_cumulative_rounding_and_withholding_are_actual(self):
        payload=prepared(); result=tax_engine.calculate_return(payload['data'])
        self.assertEqual(result['lines']['2b'],141);self.assertEqual(result['lines']['2a'],12)
        self.assertEqual(result['lines']['25b'],20);self.assertEqual(result['summary']['refund'],20)
        self.assertFalse(result['can_prepare']);self.assertFalse(payload['data']['eligibility']['all_income_reported'])


class InterestDurableSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory();cls.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.http.store=server.Store(cls.temporary.name)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start();cls.origin=f'http://127.0.0.1:{cls.http.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join();cls.temporary.cleanup()
    def call(self,path,payload=None):
        req=urllib.request.Request(self.origin+path,data=json.dumps(payload).encode() if payload else None,headers={'Origin':self.origin,'Content-Type':'application/json'})
        with urllib.request.urlopen(req)as response:return json.load(response)
    def test_actual_http_sqlite_save_reload_backup_and_edit_preserve_source(self):
        payload=prepared();saved=self.call('/api/returns',payload);reopened=self.call('/api/returns/'+saved['id']);backup=self.call('/api/returns/'+saved['id']+'/export.json')
        self.assertEqual(saved['metadata'],reopened['metadata']);self.assertEqual(backup['metadata'],saved['metadata']);self.assertEqual(saved['data']['interest'][0],payload['data']['interest'][0])
        self.assertEqual(saved['result']['summary']['refund'],20)
        payload['data']['interest'][1]['taxable']='140.52';edited=self.call('/api/returns',payload)
        entry=edited['metadata']['income_document_records']['interest'][1];old=saved['metadata']['income_document_records']['interest'][1]
        self.assertFalse(entry['reviewed']);self.assertEqual(entry['source_document'],old['source_document']);self.assertEqual(entry['taxml_interest_boxes'],old['taxml_interest_boxes'])
    def test_saved_source_and_four_box_snapshot_tamper_rejected_atomically(self):
        saved=self.call('/api/returns',prepared())
        for action in ('hash','method','remove','boxes','missing_box'):
            payload=copy.deepcopy(saved);item=payload['metadata']['income_document_records']['interest'][1]
            if action=='hash':item['source_document']['taxml_receipt']['source_sha256']='f'*64
            elif action=='method':item['source_document']['method']='manual';item['source_document'].pop('taxml_receipt')
            elif action=='remove':item.pop('source_document');item.pop('taxml_interest_boxes')
            elif action=='boxes':item['taxml_interest_boxes']['treasury_interest']='0.00'
            else:item['taxml_interest_boxes'].pop('treasury_interest')
            with self.subTest(action=action),self.assertRaises(urllib.error.HTTPError)as caught:self.call('/api/returns',payload)
            caught.exception.close();self.assertEqual(self.call('/api/returns/'+saved['id'])['metadata'],saved['metadata'])

if __name__=='__main__':unittest.main()
