"""Independent HTTP/SQLite investment-history acceptance; frozen tax oracles untouched."""
import copy
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
import tax_engine
import investment_metadata


class InvestmentPreparationAPI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.http.store = server.Store(self.temp.name)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f'http://127.0.0.1:{self.http.server_port}'
        self.ident = str(uuid.uuid4())
        self.data = tax_engine.default_return()
        self.data['name'] = 'Synthetic basis acceptance'
        self.data['w2'] = [{**tax_engine.ROW_DEFAULTS['w2'], 'employer': 'Synthetic employer',
            'wages': '60000', 'federal_withholding': '6500',
            'social_security_wages': '60000', 'medicare_wages': '60000'}]
        self.data['capital_gains'] = [{**tax_engine.ROW_DEFAULTS['capital_gains'],
            'description': 'Same synthetic lot', 'term': 'short', 'proceeds': '1500',
            'cost_basis': '1000', 'adjustment': '0'} for _ in range(2)]
        self.data['eligibility']['capital_gains_eligible'] = True

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        self.temp.cleanup()

    def call(self, path, payload=None):
        req = urllib.request.Request(self.origin + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Origin': self.origin, 'Content-Type': 'application/json'},
            method='POST' if payload is not None else 'GET')
        try:
            with urllib.request.urlopen(req) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            error.close()
            raise

    def save(self, data=None, metadata=None, ident=None):
        value = {'id': ident or self.ident, 'data': self.data if data is None else data}
        if metadata is not None:
            value['metadata'] = metadata
        return self.call('/api/returns', value)

    def correction_payload(self, record, index=1):
        data = copy.deepcopy(record['data'])
        metadata = copy.deepcopy(record['metadata'])
        old = copy.deepcopy(data['capital_gains'][index])
        data['capital_gains'][index]['cost_basis'] = '1200.00'
        event = {'correction_id': str(uuid.uuid4()),
            'previous_fingerprint': investment_metadata.fingerprint(old),
            'result_fingerprint': investment_metadata.fingerprint(data['capital_gains'][index]),
            'old_cost_basis': '1000.00', 'new_cost_basis': '1200.00',
            'applied_at': datetime.now(timezone.utc).isoformat(),
            'reason': 'Synthetic source statement correction'}
        metadata['investment_records'][index]['basis_corrections'].append(event)
        return data, metadata, event

    def test_legacy_duplicate_lots_receive_independent_stable_ids(self):
        record = self.save()
        entries = record['metadata']['investment_records']
        self.assertEqual(record['metadata']['version'], 1)
        self.assertEqual(len(record['metadata']['w2_records']), 1)
        self.assertEqual(len({entry['record_id'] for entry in entries}), 2)
        self.assertTrue(all(not entry['basis_corrections'] for entry in entries))
        reopened = self.call('/api/returns/' + self.ident)
        self.assertEqual(reopened['metadata'], record['metadata'])
        self.assertEqual(reopened['data'], record['data'])
        self.assertNotIn('investment_records', reopened['data'])

    def test_absolute_basis_change_persists_and_changes_real_gain_and_refund(self):
        first = self.save()
        data, metadata, event = self.correction_payload(first)
        saved = self.save(data, metadata)
        self.assertEqual(first['result']['lines']['7a'], 1000)
        self.assertEqual(first['result']['summary']['refund'], 1305)
        self.assertEqual(saved['result']['lines']['7a'], 800)
        self.assertEqual(saved['result']['summary']['refund'], 1329)
        self.assertEqual(saved['data']['capital_gains'][1]['cost_basis'], '1200.00')
        self.assertEqual(saved['data']['capital_gains'][1]['proceeds'], '1500')
        self.assertEqual(saved['data']['capital_gains'][1]['adjustment'], '0')
        self.assertEqual(saved['metadata']['investment_records'][1]['basis_corrections'], [event])
        # Independently read the actual committed SQLite rows, not an API cache.
        with self.http.store.connect() as db:
            raw = db.execute('SELECT data,result FROM returns WHERE id=?', (self.ident,)).fetchone()
            prep = db.execute('SELECT metadata FROM preparation_metadata WHERE return_id=?', (self.ident,)).fetchone()
        self.assertEqual(json.loads(raw['data']), saved['data'])
        self.assertEqual(json.loads(raw['result'])['lines']['7a'], 800)
        self.assertEqual(json.loads(prep['metadata']), saved['metadata'])

    def test_equal_description_lots_do_not_share_identity_or_history(self):
        first = self.save()
        data, metadata, event = self.correction_payload(first, 0)
        saved = self.save(data, metadata)
        self.assertEqual(saved['data']['capital_gains'][1], first['data']['capital_gains'][1])
        self.assertEqual(saved['metadata']['investment_records'][1], first['metadata']['investment_records'][1])
        self.assertEqual(saved['metadata']['investment_records'][0]['record_id'], first['metadata']['investment_records'][0]['record_id'])
        self.assertEqual(saved['metadata']['investment_records'][0]['basis_corrections'][0]['correction_id'], event['correction_id'])

    def test_decimal_equivalence_keeps_ids_and_fingerprints(self):
        first = self.save()
        data = copy.deepcopy(first['data'])
        data['capital_gains'][0].update(proceeds='1500.00', cost_basis='01000.00', adjustment='-0.00')
        saved = self.save(data, first['metadata'])
        self.assertEqual(saved['metadata']['investment_records'], first['metadata']['investment_records'])
        self.assertEqual(saved['result'], first['result'])

    def test_actual_json_export_and_new_copy_restore_keep_history(self):
        first = self.save()
        data, metadata, _ = self.correction_payload(first)
        saved = self.save(data, metadata)
        backup = self.call('/api/returns/' + self.ident + '/export.json')
        self.assertEqual(backup['format'], 'tax-reborn-return-v1')
        ident = str(uuid.uuid4())
        restored = self.save(backup['data'], backup['metadata'], ident)
        self.assertNotEqual(restored['id'], self.ident)
        self.assertEqual(restored['metadata'], saved['metadata'])
        self.assertEqual(restored['result'], saved['result'])
        self.assertEqual(self.call('/api/returns/' + ident)['metadata'], saved['metadata'])
        self.assertEqual(self.call('/api/returns/' + self.ident)['metadata'], saved['metadata'])

    def test_invalid_money_is_rejected_without_mutating_saved_return(self):
        first = self.save()
        for value in ('nan', '1e3', '1000.001'):
            with self.subTest(value=value):
                bad = copy.deepcopy(first['data'])
                bad['capital_gains'][1]['cost_basis'] = value
                with self.assertRaises(urllib.error.HTTPError) as error:
                    self.save(bad, first['metadata'])
                self.assertEqual(error.exception.code, 400)
                self.assertEqual(self.call('/api/returns/' + self.ident), first)

    def test_duplicate_record_id_is_rejected_atomically(self):
        first = self.save()
        bad = copy.deepcopy(first['metadata'])
        bad['investment_records'][1]['record_id'] = bad['investment_records'][0]['record_id']
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.save(metadata=bad)
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(self.call('/api/returns/' + self.ident), first)

    def test_duplicate_correction_id_across_lots_is_rejected_atomically(self):
        first = self.save()
        data, metadata, event = self.correction_payload(first)
        metadata['investment_records'][0]['basis_corrections'] = [copy.deepcopy(event)]
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.save(data, metadata)
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(self.call('/api/returns/' + self.ident), first)

if __name__ == '__main__':
    unittest.main()
