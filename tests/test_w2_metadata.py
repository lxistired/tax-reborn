"""Actual loopback API/SQLite/JSON backup roundtrips; no tax oracle is changed."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
import tax_engine
import return_metadata


class W2PreparationAPI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = server.Store(self.temp.name)
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.http.store = self.store
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f'http://127.0.0.1:{self.http.server_port}'
        self.data = tax_engine.default_return()
        self.data.update(name='Synthetic W2 record review', filing_status='mfj')
        self.data['w2'] = [self.row('Employer A', 'taxpayer', '60000'),
                           self.row('Employer B', 'spouse', '25000')]
        self.ident = str(uuid.uuid4())

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        self.temp.cleanup()

    def row(self, employer, owner, wages):
        return {**tax_engine.ROW_DEFAULTS['w2'], 'employer': employer, 'owner': owner,
                'wages': wages, 'social_security_wages': wages, 'medicare_wages': wages}

    def call(self, path, payload=None, method=None):
        request = urllib.request.Request(self.origin + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Origin': self.origin, 'Content-Type': 'application/json'},
            method=method or ('POST' if payload is not None else 'GET'))
        try:
            with urllib.request.urlopen(request) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            error.close()
            raise

    def save(self, data=None, metadata=None, ident=None):
        payload = {'id': ident or self.ident, 'data': data or self.data}
        if metadata is not None:
            payload['metadata'] = metadata
        return self.call('/api/returns', payload)

    def reviewed(self, record, indices=(0, 1)):
        metadata = copy.deepcopy(record['metadata'])
        for index in indices:
            item = metadata['w2_records'][index]
            item['reviewed'] = True
            item['reviewed_at'] = datetime.now(timezone.utc).isoformat()
            item['reviewed_fingerprint'] = return_metadata.fingerprint(record['data']['w2'][index], tax_engine.ROW_DEFAULTS['w2'])
        return metadata

    def test_legacy_save_is_unreviewed_and_read_ids_are_stable(self):
        record = self.save()
        ids = [item['record_id'] for item in record['metadata']['w2_records']]
        self.assertEqual(len(set(ids)), 2)
        self.assertFalse(any(item['reviewed'] for item in record['metadata']['w2_records']))
        reopened = self.call('/api/returns/' + self.ident)
        self.assertEqual(ids, [item['record_id'] for item in reopened['metadata']['w2_records']])
        self.assertEqual(record['data']['w2'], reopened['data']['w2'])
        self.assertEqual(record['updated_at'], reopened['updated_at'])

    def test_old_sqlite_record_migrates_without_changing_data_or_result(self):
        result = tax_engine.calculate_return(self.data)
        with self.store.connect() as db:
            db.execute('INSERT INTO returns VALUES (?,?,?,?,?)',
                       (self.ident, self.data['name'], '2026-10-13T00:00:00Z', json.dumps(self.data), json.dumps(result)))
        record = self.call('/api/returns/' + self.ident)
        self.assertEqual(record['data'], self.data)
        self.assertEqual(record['result'], result)
        self.assertEqual(record['updated_at'], '2026-10-13T00:00:00Z')
        self.assertFalse(any(item['reviewed'] for item in record['metadata']['w2_records']))
        self.assertEqual(record['metadata'], self.call('/api/returns/' + self.ident)['metadata'])

    def test_review_metadata_does_not_enter_or_change_federal_calculation(self):
        record = self.save()
        reviewed = self.save(metadata=self.reviewed(record))
        self.assertEqual(reviewed['result'], record['result'])
        self.assertEqual(reviewed['data'], record['data'])
        self.assertNotIn('metadata', reviewed['data'])
        self.assertTrue(all(item['reviewed'] for item in reviewed['metadata']['w2_records']))
        bad = copy.deepcopy(self.data)
        bad['metadata'] = reviewed['metadata']
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.call('/api/calculate', bad)
        self.assertEqual(error.exception.code, 400)

    def test_reorder_delete_and_add_keep_the_correct_stable_id(self):
        initial = self.save()
        metadata = self.reviewed(initial)
        a, b = [item['record_id'] for item in metadata['w2_records']]
        data = copy.deepcopy(self.data)
        data['w2'].reverse()
        metadata['w2_records'].reverse()
        swapped = self.save(data, metadata)
        self.assertEqual([b, a], [item['record_id'] for item in swapped['metadata']['w2_records']])
        data['w2'].pop()
        metadata['w2_records'].pop()
        survivor = self.save(data, metadata)
        self.assertEqual(survivor['data']['w2'][0]['owner'], 'spouse')
        self.assertEqual(survivor['metadata']['w2_records'][0]['record_id'], b)
        data['w2'].append(self.row('Employer C', 'taxpayer', '1000'))
        metadata['w2_records'].append({'record_id': str(uuid.uuid4()), 'reviewed': False})
        added = self.save(data, metadata)
        self.assertEqual(added['metadata']['w2_records'][0]['record_id'], b)
        self.assertTrue(added['metadata']['w2_records'][0]['reviewed'])
        self.assertFalse(added['metadata']['w2_records'][1]['reviewed'])

    def test_duplicate_equal_w2_records_remain_independent_with_explicit_ids(self):
        self.data['w2'][1] = copy.deepcopy(self.data['w2'][0])
        record = self.save()
        metadata = self.reviewed(record, (1,))
        record = self.save(metadata=metadata)
        survivor = copy.deepcopy(self.data)
        survivor['w2'].pop(0)
        metadata['w2_records'].pop(0)
        new = self.save(survivor, metadata)
        self.assertEqual(new['metadata']['w2_records'][0]['record_id'], record['metadata']['w2_records'][1]['record_id'])
        self.assertTrue(new['metadata']['w2_records'][0]['reviewed'])

    def test_cent_equivalence_preserves_review_but_actual_edit_clears_only_one(self):
        record = self.save()
        metadata = self.reviewed(record)
        data = copy.deepcopy(self.data)
        data['w2'][0]['wages'] = '60000.00'
        same = self.save(data, metadata)
        self.assertTrue(all(item['reviewed'] for item in same['metadata']['w2_records']))
        data['w2'][0]['wages'] = '60000.01'
        edited = self.save(data, same['metadata'])
        self.assertFalse(edited['metadata']['w2_records'][0]['reviewed'])
        self.assertTrue(edited['metadata']['w2_records'][1]['reviewed'])
        self.assertIsNone(edited['metadata']['w2_records'][0]['reviewed_at'])

    def test_owner_change_clears_that_record_review(self):
        record = self.save()
        metadata = self.reviewed(record)
        data = copy.deepcopy(self.data)
        data['w2'][0]['owner'] = 'spouse'
        saved = self.save(data, metadata)
        self.assertFalse(saved['metadata']['w2_records'][0]['reviewed'])
        self.assertTrue(saved['metadata']['w2_records'][1]['reviewed'])
        self.assertEqual(saved['data']['w2'][0]['owner'], 'spouse')

    def test_json_backup_new_copy_preserves_ids_review_and_original_reference(self):
        record = self.save()
        metadata = self.reviewed(record)
        source = {'document_id': str(uuid.uuid4()), 'return_id': self.ident, 'name': 'Synthetic W2 source.pdf', 'method': 'ocr'}
        metadata['w2_records'][0]['source_document'] = source
        self.save(metadata=metadata)
        backup = self.call('/api/returns/' + self.ident + '/export.json')
        self.assertEqual(backup['format'], 'tax-reborn-return-v1')
        new_id = str(uuid.uuid4())
        restored = self.save(backup['data'], backup['metadata'], new_id)
        self.assertEqual(restored['metadata'], backup['metadata'])
        self.assertNotEqual(restored['id'], source['return_id'])
        self.assertEqual(restored['metadata']['w2_records'][0]['source_document'], source)
        self.assertEqual(restored['result'], backup['result'])
        self.assertEqual(self.call('/api/returns/' + self.ident)['metadata'], backup['metadata'])

    def test_bad_metadata_rejects_save_atomically(self):
        original = self.save()
        metadata = self.reviewed(original)
        metadata['w2_records'][1]['record_id'] = metadata['w2_records'][0]['record_id']
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.save(metadata=metadata)
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(self.call('/api/returns/' + self.ident)['metadata'], original['metadata'])
        metadata = self.reviewed(original)
        metadata['w2_records'][0]['source_document'] = {'document_id': 'https://external.invalid', 'return_id': self.ident, 'name': 'x', 'method': 'ocr'}
        with self.assertRaises(urllib.error.HTTPError):
            self.save(metadata=metadata)
        self.assertEqual(self.call('/api/returns/' + self.ident)['metadata'], original['metadata'])

    def test_delete_removes_preparation_metadata(self):
        self.save()
        self.call('/api/returns/' + self.ident, method='DELETE')
        with self.store.connect() as db:
            count = db.execute('SELECT count(*) FROM preparation_metadata WHERE return_id=?', (self.ident,)).fetchone()[0]
        self.assertEqual(count, 0)


if __name__ == '__main__':
    unittest.main()
