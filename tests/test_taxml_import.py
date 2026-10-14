"""Synthetic actual XML/XPRF/ZIP imports, rejection, and durable SQLite receipts.

These fixtures are independently constructed bytes. They are not vendor returns
and do not establish original-program compatibility or original tax parity.
"""
import base64
import copy
from datetime import datetime, timezone
from io import BytesIO
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
import zipfile
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'web'))
import taxml_preparation as preparation
import taxml_wire as wire
import return_metadata
import server
import tax_engine


def registry_bytes(extra=(), field_kinds=None):
    fields = [('NAME', 7), ('CA', 7), ('CA2', 7), ('WAGES', 11), ('FEDTAX', 11),
              ('SSWAGES', 11), ('SSTAX', 11), ('MEDWAGES', 11), ('MEDTAX', 11),
              ('SSTIPS', 11), ('DCB', 11), *extra]
    if field_kinds:
        fields = [(name, field_kinds.get(name, kind)) for name, kind in fields]
    dictionary = struct.pack('<H', len(fields)) + b''.join(b'\xff' + name.encode().ljust(32, b' ')
        + struct.pack('<BBI', kind, 0, 4 if kind == 7 else 132) for name, kind in fields)
    form, formset = b'FW2', b'S2025US1040PER'
    metadata = struct.pack('<H', 2) + bytes([len(form)]) + form + bytes([len(formset)]) + formset
    entries = [(18000, 41, metadata), (1900, 41, dictionary)]
    header = b'XPRF\0\1\x10\x0c\x0a\0\0\0' + struct.pack('<I', len(entries))
    offset, directory, bodies = len(header) + 12 * len(entries), b'', b''
    for kind, ident, content in entries:
        record = struct.pack('<IIH', len(content) + 10, len(content), 0) + content
        directory += struct.pack('<HHII', kind, ident, offset, len(record))
        bodies += record
        offset += len(record)
    return header + directory + bodies


def taxml_bytes(missing=(), extra='', owner_flag='', root='SyntheticReturn'):
    facts = [('NAME', 'Synthetic caption / do not use as employer'), ('CA', 'Synthetic Widgets'),
             ('CA2', 'LLC'), ('WAGES', '98231.17'), ('FEDTAX', '13542.09'),
             ('SSWAGES', '98231.17'), ('SSTAX', '6090.33'), ('MEDWAGES', '98231.17'),
             ('MEDTAX', '1424.35'), ('SSTIPS', '301.23'), ('DCB', '87.65')]
    fields = ''.join(f'<{key}><td:value {owner_flag}>{value}</td:value></{key}>'
        for key, value in facts if key not in missing)
    return (f'<{root} xmlns:td="{wire.TD}"><PER tpsPrefix="S2025US1040" checksum="7" '
        f'dataVersion="100" formsetAttribute="0"><FW2 copyNum="1" fileCopyNum="1">'
        f'{fields}{extra}</FW2></PER></{root}>').encode()


def profile(carrier):
    return {'format': 'tax-reborn-taxml-wire-profile-v1', 'tax_year': 2025,
        'root_qname': 'SyntheticReturn', 'namespace_profile': {'formset': [''], 'form': [''], 'field': ['']},
        'templates': [{'formset_id': 'S2025US1040PER', 'form_id': 'FW2',
            'carrier_sha256': wire.digest(carrier), 'resource_id': 41}]}


def request(data=None, carrier=None):
    carrier = registry_bytes() if carrier is None else carrier
    data = taxml_bytes() if data is None else data
    return {'base64': base64.b64encode(data).decode(), 'container': 'plaintext_xml',
        'profile': profile(carrier), 'carriers': [{'base64': base64.b64encode(carrier).decode(),
            'sha256': wire.digest(carrier)}], 'profile_acknowledged': True}


def plaintext_archive(data, security=''):
    manifest = (f'<Manifest xmlns="{wire.MANIFEST_NS}">{security}<documents><document>'
        f'<entityKey>return.xml</entityKey><entityType>{wire.TAXML_TYPE}</entityType>'
        f'</document></documents></Manifest>').encode()
    result = BytesIO()
    with zipfile.ZipFile(result, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr('manifest.xml', manifest)
        zipped.writestr('return.xml', data)
        zipped.writestr('original-attachment.bin', b'opaque retained local source')
    return result.getvalue()


class InspectionAcceptance(unittest.TestCase):
    def test_present_wrong_type_is_blocking_instead_of_manual_fallback(self):
        source_values = {'NAME': 'Synthetic caption / do not use as employer',
            'CA': 'Synthetic Widgets', 'CA2': 'LLC', 'SSTIPS': '301.23', 'DCB': '87.65'}
        for field, original in source_values.items():
            with self.subTest(field=field):
                carrier = registry_bytes(field_kinds={field: 12})
                data = taxml_bytes().replace(original.encode(), b'123')
                result = preparation.inspect_request(request(data, carrier))
                self.assertFalse(result['candidates'][0]['can_review'])
                self.assertTrue(any(row['code'] == 'unsupported_w2_semantic_type'
                    and row['detail'] == field for row in result['unresolved_facts']))

    def test_actual_bytes_map_employer_cents_and_extra_boxes_without_owner_inference(self):
        result = preparation.inspect_request(request(taxml_bytes(owner_flag='spouseAmount="true"')))
        candidate = result['candidates'][0]
        self.assertEqual(candidate['employer'], 'Synthetic Widgets LLC')
        self.assertEqual(candidate['amounts']['wages'], '98231.17')
        self.assertEqual(candidate['amounts']['social_security_tips'], '301.23')
        self.assertEqual(candidate['amounts']['dependent_care_benefits'], '87.65')
        self.assertEqual(candidate['sources']['wages']['wire_text'], '98231.17')
        self.assertIsNone(candidate['owner'])
        self.assertEqual(candidate['requires_manual_fields'], ['owner'])
        self.assertFalse(result['tax_values_imported'])
        self.assertFalse(result['full_return_imported'])
        self.assertFalse(result['original_program_acceptance_verified'])

    def test_missing_7_10_stays_missing_but_six_box_review_remains_possible(self):
        candidate = preparation.inspect_request(request(taxml_bytes(missing=('SSTIPS', 'DCB'))))['candidates'][0]
        self.assertTrue(candidate['can_review'])
        self.assertNotIn('social_security_tips', candidate['amounts'])
        self.assertNotIn('dependent_care_benefits', candidate['amounts'])
        self.assertEqual(candidate['requires_manual_fields'], ['owner', 'social_security_tips', 'dependent_care_benefits'])

    def test_missing_required_box_is_blocking_and_never_zero(self):
        candidate = preparation.inspect_request(request(taxml_bytes(missing=('FEDTAX',))))['candidates'][0]
        self.assertFalse(candidate['can_review'])
        self.assertNotIn('federal_withholding', candidate['amounts'])
        self.assertEqual(candidate['missing_boxes'][0]['box'], 2)

    def test_name_caption_never_becomes_employer(self):
        candidate = preparation.inspect_request(request(taxml_bytes(missing=('CA', 'CA2'))))['candidates'][0]
        self.assertIsNone(candidate['employer'])

    def test_unknown_field_and_known_unmapped_fact_both_block(self):
        for carrier, extra in [(registry_bytes(), '<UNKNOWN><td:value>1</td:value></UNKNOWN>'),
                (registry_bytes((('ALLOCTIP', 11),)), '<ALLOCTIP><td:value>25.00</td:value></ALLOCTIP>')]:
            result = preparation.inspect_request(request(taxml_bytes(extra=extra), carrier))
            self.assertTrue(result['unresolved_facts'])
            self.assertFalse(result['candidates'][0]['can_review'])

    def test_duplicate_six_box_cannot_replace_amount(self):
        result = preparation.inspect_request(request(taxml_bytes(extra='<WAGES><td:value>1.00</td:value></WAGES>')))
        self.assertFalse(result['candidates'][0]['can_review'])
        self.assertNotIn('wages', result['candidates'][0]['amounts'])

    def test_root_mismatch_and_unbound_profile_are_not_imported(self):
        result = preparation.inspect_request(request(taxml_bytes(root='OtherReturn')))
        self.assertFalse(result['root_qname_bound'])
        self.assertEqual(result['candidates'], [])
        value = request(); del value['profile']['root_qname']
        with self.assertRaises(ValueError): preparation.inspect_request(value)

    def test_unmapped_root_facts_are_blocking(self):
        data = taxml_bytes().replace(b'<SyntheticReturn ', b'<SyntheticReturn otherTaxFact="unmapped" ')
        result = preparation.inspect_request(request(data))
        self.assertFalse(result['candidates'][0]['can_review'])
        self.assertEqual(result['unresolved_facts'][0]['code'], 'unmapped_root_metadata')

    def test_registry_identity_profile_ambiguity_and_acknowledgement_reject(self):
        for mutate in (lambda r: r['profile']['templates'][0].update(carrier_sha256='0' * 64),
                lambda r: r['profile']['templates'].append(copy.deepcopy(r['profile']['templates'][0])),
                lambda r: r.update(profile_acknowledged=False),
                lambda r: r.update(container='encrypted_tax')):
            value = request(); mutate(value)
            with self.assertRaises(ValueError): preparation.inspect_request(value)

    def test_plaintext_zip_receipt_hashes_original_zip_and_identifies_member(self):
        data = plaintext_archive(taxml_bytes()); value = request(data); value['container'] = 'declared_plaintext_zip'
        result = preparation.inspect_request(value)
        self.assertEqual(result['source_sha256'], wire.digest(data))
        self.assertEqual(result['candidates'][0]['receipt']['archive_member'], 'return.xml')

    def test_zip_with_security_context_refuses_even_if_payload_looks_plain(self):
        value = request(plaintext_archive(taxml_bytes(), '<security/>'))
        value['container'] = 'declared_plaintext_zip'
        with self.assertRaises(ValueError): preparation.inspect_request(value)


class ReceiptPersistenceAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.http.store = server.Store(cls.temporary.name)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True); cls.thread.start()
        cls.origin = f'http://127.0.0.1:{cls.http.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown(); cls.http.server_close(); cls.thread.join(); cls.temporary.cleanup()

    def call(self, path, payload=None):
        req = urllib.request.Request(self.origin + path, data=json.dumps(payload).encode() if payload else None,
            headers={'Origin': self.origin, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response: return json.load(response)

    def prepared(self):
        candidate = preparation.inspect_request(request())['candidates'][0]
        data = tax_engine.default_return(); data['name'] = 'Synthetic TaxML imported W-2'
        data['w2'] = [{**tax_engine.ROW_DEFAULTS['w2'], 'employer': candidate['employer'],
            'owner': 'taxpayer', **candidate['amounts']}]
        ident = str(uuid.uuid4())
        metadata = return_metadata.normalize(data, None, tax_engine.ROW_DEFAULTS['w2'])
        item = metadata['w2_records'][0]
        item.update(reviewed=True, reviewed_at=datetime.now(timezone.utc).isoformat(),
            reviewed_fingerprint=item['row_fingerprint'], source_document={'document_id': str(uuid.uuid4()),
                'return_id': ident, 'name': 'synthetic-return.xml', 'method': 'taxml', 'taxml_receipt': candidate['receipt']})
        return {'id': ident, 'data': data, 'metadata': metadata}

    def test_http_save_reopen_backup_and_new_copy_preserve_receipt_without_income_assertion(self):
        payload = self.prepared(); saved = self.call('/api/returns', payload)
        reopened = self.call('/api/returns/' + saved['id'])
        backup = self.call('/api/returns/' + saved['id'] + '/export.json')
        self.assertEqual(saved['metadata'], reopened['metadata'])
        self.assertEqual(saved['metadata'], backup['metadata'])
        self.assertFalse(saved['data']['eligibility']['all_income_reported'])
        self.assertFalse(saved['result']['can_prepare'])
        self.assertEqual(saved['data']['w2'][0]['wages'], '98231.17')
        restored = self.call('/api/returns', {'id': str(uuid.uuid4()), 'data': backup['data'], 'metadata': backup['metadata']})
        self.assertEqual(restored['metadata'], saved['metadata'])
        self.assertNotEqual(restored['id'], restored['metadata']['w2_records'][0]['source_document']['return_id'])

    def test_receipt_tamper_and_method_spoof_reject_atomically(self):
        payload = self.prepared(); saved = self.call('/api/returns', payload)
        for action in ('hash', 'method', 'erase'):
            modified = copy.deepcopy(saved)
            source = modified['metadata']['w2_records'][0]['source_document']
            if action == 'hash': source['taxml_receipt']['source_sha256'] = 'f' * 64
            elif action == 'method': source['method'] = 'ocr'
            else: modified['metadata']['w2_records'][0]['source_document'] = None
            with self.assertRaises(urllib.error.HTTPError) as caught: self.call('/api/returns', modified)
            caught.exception.close()
            self.assertEqual(self.call('/api/returns/' + saved['id'])['metadata'], saved['metadata'])

    def test_amount_edit_clears_review_but_keeps_original_source_receipt(self):
        payload = self.prepared(); saved = self.call('/api/returns', payload)
        payload['data']['w2'][0]['wages'] = '98231.18'
        edited = self.call('/api/returns', payload)
        self.assertFalse(edited['metadata']['w2_records'][0]['reviewed'])
        self.assertEqual(edited['metadata']['w2_records'][0]['source_document'], saved['metadata']['w2_records'][0]['source_document'])


if __name__ == '__main__':
    unittest.main()
