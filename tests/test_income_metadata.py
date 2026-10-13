"""Host-only synthetic HTTP/SQLite income preparation acceptance.

The loopback service, persistent database and actual JSON export are exercised.
This file requires host sockets and must be excluded from Pyodide discovery.
"""
from copy import deepcopy
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import income_preparation as income
import server
import tax_engine
from test_income_preparation import STAMP, synthetic_income_state
UNSPECIFIED_REVISION = object()


class IncomePreparationAPI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.http.store = server.Store(self.temp.name)
        self.thread = threading.Thread(target=lambda: self.http.serve_forever(poll_interval=.01), daemon=True)
        self.thread.start()
        self.origin = f'http://127.0.0.1:{self.http.server_port}'
        self.ident = str(uuid.uuid4())
        self.data = synthetic_income_state()['data']

    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join(); self.temp.cleanup()

    def call(self, path, payload=None):
        request = urllib.request.Request(self.origin + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={'Origin': self.origin, 'Content-Type': 'application/json'},
            method='POST' if payload is not None else 'GET')
        try:
            with urllib.request.urlopen(request) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            error.close()
            raise

    def save(self, data=None, metadata=None, ident=None, expected_updated_at=UNSPECIFIED_REVISION):
        payload = {'id': ident or self.ident, 'data': self.data if data is None else data}
        if metadata is not None:
            payload['metadata'] = metadata
        if expected_updated_at is not UNSPECIFIED_REVISION:
            payload['expected_updated_at'] = expected_updated_at
        return self.call('/api/returns', payload)

    def reopen(self, ident=None):
        return self.call('/api/returns/' + (ident or self.ident))

    def placeholder(self):
        first = self.save(); metadata = deepcopy(first['metadata'])
        metadata['income_document_records']['interest'][0]['is_placeholder'] = True
        return self.save(first['data'], metadata)

    def imported(self):
        first = self.placeholder()
        uid = first['metadata']['income_document_records']['interest'][0]['record_id']
        proposal = income.plan(first['data'], first['metadata'], 'interest', [uid],
            [{**tax_engine.ROW_DEFAULTS['interest'], 'payer': 'Same synthetic payer', 'taxable': '1200'}])
        result = income.apply(first['data'], first['metadata'], proposal)
        return first, self.save(result['data'], result['metadata']), proposal

    def assert_rejected_unchanged(self, record, data, metadata):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.save(data, metadata)
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(self.reopen(), record)

    def test_old_sqlite_return_migrates_income_metadata_without_recalculating(self):
        result = tax_engine.calculate_return(self.data)
        with self.http.store.connect() as db:
            db.execute('INSERT INTO returns VALUES (?,?,?,?,?)', (self.ident, self.data['name'],
                '2026-10-14T00:00:00Z', json.dumps(self.data), json.dumps(result)))
        record = self.reopen()
        self.assertEqual(record['data'], self.data); self.assertEqual(record['result'], result)
        self.assertEqual(record['updated_at'], '2026-10-14T00:00:00Z')
        entries = record['metadata']['income_document_records']
        ids = [x['record_id'] for rows in entries.values() for x in rows]
        self.assertEqual(len(set(ids)), 3)
        self.assertFalse(any(x['reviewed'] for rows in entries.values() for x in rows))
        self.assertEqual(self.reopen()['metadata'], record['metadata'])

    def test_legacy_unique_migration_and_ambiguous_same_payer_rows(self):
        first = self.save(); legacy = self.save(first['data'])
        self.assertEqual(first['metadata']['income_document_records'], legacy['metadata']['income_document_records'])
        duplicate = deepcopy(first['data']); duplicate['interest'] = [duplicate['interest'][1], deepcopy(duplicate['interest'][1])]
        saved = self.save(duplicate)
        ids = [x['record_id'] for x in saved['metadata']['income_document_records']['interest']]
        self.assertEqual(len(set(ids)), 2)
        self.assertNotIn(first['metadata']['income_document_records']['interest'][1]['record_id'], ids)
        self.assertFalse(any(x['reviewed'] for x in saved['metadata']['income_document_records']['interest']))

    def test_per_statement_review_changes_and_unresolved_zero_survive_save(self):
        first = self.save(); uid = first['metadata']['income_document_records']['interest'][1]['record_id']
        checked = income.mark_reviewed({'data': first['data'], 'preparation_metadata': first['metadata']}, 'interest', uid, STAMP)
        reviewed = self.save(checked['data'], checked['preparation_metadata'])
        self.assertFalse(reviewed['metadata']['income_document_records']['interest'][0]['reviewed'])
        self.assertTrue(reviewed['metadata']['income_document_records']['interest'][1]['reviewed'])
        equivalent = deepcopy(reviewed['data']); equivalent['interest'][1]['taxable'] = '350.00'
        same = self.save(equivalent, reviewed['metadata'])
        self.assertTrue(same['metadata']['income_document_records']['interest'][1]['reviewed'])
        changed = deepcopy(same['data']); changed['interest'][1]['taxable'] = '351'
        saved = self.save(changed, same['metadata'])
        self.assertFalse(saved['metadata']['income_document_records']['interest'][1]['reviewed'])
        changed['interest'][1]['taxable'] = '0'; metadata = deepcopy(saved['metadata'])
        metadata['income_document_records']['interest'][1]['unresolved_fields'] = ['taxable']
        state = income.mark_reviewed({'data': changed, 'preparation_metadata': metadata}, 'interest', uid, STAMP)
        zero = self.save(state['data'], state['preparation_metadata'])
        self.assertTrue(zero['metadata']['income_document_records']['interest'][1]['reviewed'])
        self.assertEqual(zero['metadata']['income_document_records']['interest'][1]['unresolved_fields'], ['taxable'])
        self.assertEqual(zero['result']['lines']['2b'], 1000)
        self.assertEqual(self.reopen()['metadata'], zero['metadata'])

    def test_replacement_commits_data_metadata_real_tax_and_old_row_audit(self):
        before, saved, proposal = self.imported()
        self.assertEqual(before['result']['lines']['2b'], 1350)
        self.assertEqual(saved['result']['lines']['2b'], 1550)
        self.assertEqual(saved['result']['summary']['refund'], 1215)
        self.assertEqual(saved['data']['interest'][1], before['data']['interest'][1])
        self.assertEqual(saved['metadata']['income_document_records']['interest'][1], before['metadata']['income_document_records']['interest'][1])
        event = saved['metadata']['income_import_events'][0]
        self.assertEqual(event['event_id'], proposal['event_id'])
        self.assertEqual(event['receipt']['archived_replaced_records'][0]['row'], before['data']['interest'][0])
        self.assertEqual(event['receipt']['removed_record_ids'], proposal['payload']['target_ids'])
        with self.http.store.connect() as db:
            row = db.execute('SELECT data,result FROM returns WHERE id=?', (self.ident,)).fetchone()
            metadata = db.execute('SELECT metadata FROM preparation_metadata WHERE return_id=?', (self.ident,)).fetchone()
        self.assertEqual(json.loads(row['data']), saved['data'])
        self.assertEqual(json.loads(row['result'])['lines']['2b'], 1550)
        self.assertEqual(json.loads(metadata['metadata']), saved['metadata'])
        restarted = server.Store(self.temp.name)
        self.assertEqual(restarted.get(self.ident), saved)

    def test_actual_json_backup_restore_and_event_replay_preserve_identities(self):
        _, saved, proposal = self.imported()
        backup = self.call('/api/returns/' + self.ident + '/export.json')
        self.assertEqual(backup['format'], 'tax-reborn-return-v1')
        restored_id = str(uuid.uuid4())
        restored = self.save(backup['data'], backup['metadata'], restored_id)
        self.assertEqual(restored['data'], saved['data']); self.assertEqual(restored['metadata'], saved['metadata'])
        self.assertEqual(restored['result'], saved['result'])
        replay = income.apply(restored['data'], restored['metadata'], proposal)
        self.assertTrue(replay['already_applied'])
        again = self.save(replay['data'], replay['metadata'], restored_id)
        self.assertEqual(again['data'], saved['data']); self.assertEqual(again['metadata'], saved['metadata'])
        self.assertEqual(again['result']['lines']['2b'], 1550)
        self.assertEqual(self.reopen()['metadata'], saved['metadata'])

    def test_malformed_ids_facts_money_receipts_and_stale_plan_leave_store_unchanged(self):
        original = self.placeholder(); before = self.reopen()
        uid = original['metadata']['income_document_records']['interest'][0]['record_id']
        proposal = income.plan(original['data'], original['metadata'], 'interest', [uid], [{'taxable': '1200'}])
        stale = deepcopy(original['data']); stale['interest'][0]['taxable'] = '1001'
        with self.assertRaises(ValueError): income.apply(stale, original['metadata'], proposal)
        failed = income.plan(original['data'], original['metadata'], 'interest', [], [], successful=False)
        self.assertEqual(income.apply(original['data'], original['metadata'], failed)['data'], original['data'])
        self.assertEqual(self.reopen(), before)
        invalids = []
        duplicate = deepcopy(original['metadata']); duplicate['income_document_records']['dividends'][0]['record_id'] = uid
        invalids.append((deepcopy(original['data']), duplicate))
        malformed = deepcopy(original['metadata']); malformed['income_document_records']['interest'][0]['unresolved_fields'] = [{}]
        invalids.append((deepcopy(original['data']), malformed))
        bad_money = deepcopy(original['data']); bad_money['interest'][0]['taxable'] = '1e3'
        invalids.append((bad_money, deepcopy(original['metadata'])))
        result = income.apply(original['data'], original['metadata'], proposal)
        bad_receipt = deepcopy(result['metadata']); bad_receipt['income_import_events'][0]['receipt']['extra'] = 'unexpected'
        invalids.append((result['data'], bad_receipt))
        for data, metadata in invalids:
            with self.subTest(metadata_fields=list(metadata)):
                self.assert_rejected_unchanged(original, data, metadata)

    def test_existing_event_history_cannot_be_removed_or_rewritten(self):
        _, saved, proposal = self.imported()
        variants = []
        cleared = deepcopy(saved['metadata']); cleared['income_import_events'] = []; variants.append(cleared)
        altered = deepcopy(saved['metadata']); altered['income_import_events'][0]['payload_hash'] = '0' * 64; variants.append(altered)
        rewritten = deepcopy(saved['metadata'])
        archived = rewritten['income_import_events'][0]['receipt']['archived_replaced_records'][0]
        archived['row']['taxable'] = '999'
        archived['metadata']['row_fingerprint'] = income.fingerprint('interest', archived['row'])
        # This receipt is structurally valid. Its rejection must come from the
        # immutable previous-history guard, not merely a malformed SHA field.
        income.validate_receipt(rewritten['income_import_events'][0]['receipt'])
        variants.append(rewritten)
        for metadata in variants:
            changed = deepcopy(saved['data']); changed['name'] = 'Must not overwrite after rejected history'
            self.assert_rejected_unchanged(saved, changed, metadata)
        with self.assertRaises(ValueError):
            income.plan(saved['data'], saved['metadata'], 'interest', proposal['payload']['target_ids'], [{'taxable': '1201'}], proposal['event_id'])
        # A legacy client omitting the new fields retains saved history.
        omitted = deepcopy(saved['metadata']); omitted.pop('income_import_events'); omitted.pop('income_document_records')
        compatible = self.save(saved['data'], omitted)
        self.assertEqual(compatible['metadata'], saved['metadata'])
        compatible = self.save(saved['data'])
        self.assertEqual(compatible['metadata'], saved['metadata'])

    def test_stale_api_client_revision_cannot_overwrite_new_target_or_append_event(self):
        first = self.placeholder()
        uid = first['metadata']['income_document_records']['interest'][0]['record_id']
        old_proposal = income.plan(first['data'], first['metadata'], 'interest', [uid], [{'taxable': '1200'}])
        old_client_result = income.apply(first['data'], first['metadata'], old_proposal)
        other_client_data = deepcopy(first['data']); other_client_data['interest'][0]['taxable'] = '1001'
        newer = self.save(other_client_data, first['metadata'], expected_updated_at=first['updated_at'])
        self.assertNotEqual(newer['updated_at'], first['updated_at'])
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.save(old_client_result['data'], old_client_result['metadata'], expected_updated_at=first['updated_at'])
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(self.reopen(), newer)
        self.assertEqual(self.reopen()['data']['interest'][0]['taxable'], '1001')
        self.assertEqual(self.reopen()['metadata']['income_import_events'], [])
        fresh = income.plan(newer['data'], newer['metadata'], 'interest', [uid], [{'taxable': '1200'}])
        applied = income.apply(newer['data'], newer['metadata'], fresh)
        saved = self.save(applied['data'], applied['metadata'], expected_updated_at=newer['updated_at'])
        self.assertEqual(saved['result']['lines']['2b'], 1550)
        self.assertEqual(len(saved['metadata']['income_import_events']), 1)
        copy_id = str(uuid.uuid4())
        created = self.save(saved['data'], saved['metadata'], copy_id, expected_updated_at=None)
        self.assertEqual(created['metadata'], saved['metadata'])
        with self.assertRaises(urllib.error.HTTPError):
            self.save(created['data'], created['metadata'], copy_id, expected_updated_at=None)
        self.assertEqual(self.reopen(copy_id), created)


if __name__ == '__main__':
    unittest.main()
