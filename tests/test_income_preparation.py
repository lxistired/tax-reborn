"""Synthetic income preparation behavior; runs in host Python or Pyodide.

These checks exercise independently authored preparation state. They do not
execute a vendor binary or modify the federal tax calculation or its oracles.
"""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import income_preparation as income
import tax_engine

STAMP = '2026-10-14T01:00:00+00:00'


def synthetic_income_state():
    data = tax_engine.default_return()
    data['name'] = 'Synthetic income preparation acceptance'
    data['w2'] = [{**tax_engine.ROW_DEFAULTS['w2'], 'employer': 'Synthetic employer',
                   'wages': '60000', 'federal_withholding': '6500'}]
    data['interest'] = [{**tax_engine.ROW_DEFAULTS['interest'], 'payer': 'Same synthetic payer', 'taxable': '1000'},
                        {**tax_engine.ROW_DEFAULTS['interest'], 'payer': 'Same synthetic payer', 'taxable': '350'}]
    data['dividends'] = [{**tax_engine.ROW_DEFAULTS['dividends'], 'payer': 'Same synthetic payer', 'ordinary': '200'}]
    metadata = {'version': 1, 'w2_records': [], 'investment_records': [],
        'income_document_records': {'interest': [income.new_record(True), income.new_record()],
                                    'dividends': [income.new_record()]}}
    return income.normalize_state({'data': data, 'preparation_metadata': metadata})


def replacement(state, replacements=None, targets=None, event_id=None):
    records = state['preparation_metadata']['income_document_records']['interest']
    return income.plan(state['data'], state['preparation_metadata'], 'interest',
        targets or [records[0]['record_id']],
        replacements or [{**tax_engine.ROW_DEFAULTS['interest'], 'payer': 'Same synthetic payer', 'taxable': '1200'}],
        event_id=event_id)


class IncomePreparationTests(unittest.TestCase):
    def test_same_payer_review_targets_stable_id_and_deletion_rebuilds_summary(self):
        state = synthetic_income_state()
        ids = [x['record_id'] for x in state['preparation_metadata']['income_document_records']['interest']]
        self.assertNotEqual(*ids)
        checked = income.mark_reviewed(state, 'interest', ids[1], STAMP)
        summary = income.current_summary(checked)
        self.assertFalse(summary['reviewed_by_id'][ids[0]])
        self.assertTrue(summary['reviewed_by_id'][ids[1]])
        self.assertEqual(income.current_summary(state)['reviewed'], 0)
        del checked['data']['interest'][1]
        del checked['preparation_metadata']['income_document_records']['interest'][1]
        summary = income.current_summary(checked)
        self.assertNotIn(ids[1], summary['reviewed_by_id'])
        self.assertEqual(summary['reviewed'], 0)
        self.assertEqual(summary['total'], 2)

    def test_decimal_equivalence_preserves_review_edits_clear_it_and_draft_is_not_zero(self):
        state = synthetic_income_state()
        uid = state['preparation_metadata']['income_document_records']['interest'][1]['record_id']
        state = income.mark_reviewed(state, 'interest', uid, STAMP)
        equivalent = deepcopy(state); equivalent['data']['interest'][1]['taxable'] = '0350.00'
        self.assertTrue(income.current_summary(equivalent)['reviewed_by_id'][uid])
        for field, value in (('taxable', '350.01'), ('payer', 'Changed synthetic payer')):
            with self.subTest(field=field):
                edited = deepcopy(state); edited['data']['interest'][1][field] = value
                normalized = income.normalize_state(edited)
                entry = normalized['preparation_metadata']['income_document_records']['interest'][1]
                self.assertFalse(entry['reviewed']); self.assertIsNone(entry['reviewed_at'])
                self.assertEqual(entry['record_id'], uid)
        invalid = deepcopy(state['data']); invalid['interest'][1]['taxable'] = 'not an amount'
        draft = income.normalize(invalid, state['preparation_metadata']['income_document_records'], options={'draft': True})
        self.assertIsNone(draft['interest'][1]['row_fingerprint'])
        self.assertFalse(draft['interest'][1]['reviewed']); self.assertEqual(draft['interest'][1]['record_id'], uid)
        self.assertEqual(invalid['interest'][1]['taxable'], 'not an amount')
        with self.assertRaises(ValueError): income.normalize(invalid, state['preparation_metadata']['income_document_records'])

    def test_zero_and_unresolved_facts_are_separate_from_review(self):
        state = synthetic_income_state(); state['data']['interest'][1]['taxable'] = '0'
        state['preparation_metadata']['income_document_records']['interest'][1]['unresolved_fields'] = ['taxable']
        state = income.normalize_state(state)
        uid = state['preparation_metadata']['income_document_records']['interest'][1]['record_id']
        state = income.mark_reviewed(state, 'interest', uid, STAMP)
        summary = income.current_summary(state)
        self.assertTrue(summary['reviewed_by_id'][uid]); self.assertEqual(summary['missing_facts_by_id'][uid], ['taxable'])
        self.assertEqual(tax_engine.calculate_return(state['data'])['lines']['2b'], 1000)
        state['preparation_metadata']['income_document_records']['interest'][1]['unresolved_fields'] = []
        self.assertEqual(income.current_summary(state)['missing_facts_by_id'][uid], [])

    def test_legacy_unique_exact_match_retains_identity_ambiguous_rows_get_fresh_ids(self):
        state = synthetic_income_state(); previous = state['preparation_metadata']['income_document_records']
        normalized = income.normalize(state['data'], previous=previous)
        self.assertEqual(normalized, previous)
        duplicate = deepcopy(state['data']); duplicate['interest'] = [duplicate['interest'][1], deepcopy(duplicate['interest'][1])]
        normalized = income.normalize(duplicate, previous=previous)
        ids = [item['record_id'] for item in normalized['interest']]
        self.assertEqual(len(set(ids)), 2)
        self.assertNotIn(previous['interest'][1]['record_id'], ids)
        self.assertFalse(any(item['reviewed'] for item in normalized['interest']))
        with self.assertRaises(ValueError): income.normalize(state['data'], {'interest': []})

    def test_exact_placeholder_replacement_audits_old_row_and_changes_real_tax_result(self):
        state = synthetic_income_state(); original = deepcopy(state)
        proposal = replacement(state)
        result = income.apply(state['data'], state['preparation_metadata'], proposal)
        old_id = state['preparation_metadata']['income_document_records']['interest'][0]['record_id']
        self.assertEqual(state, original)
        self.assertEqual(result['data']['interest'][1], original['data']['interest'][1])
        self.assertEqual(result['metadata']['income_document_records']['interest'][1], original['preparation_metadata']['income_document_records']['interest'][1])
        self.assertNotEqual(result['metadata']['income_document_records']['interest'][0]['record_id'], old_id)
        self.assertFalse(result['metadata']['income_document_records']['interest'][0]['reviewed'])
        self.assertEqual(result['receipt']['archived_replaced_records'], [{'row': original['data']['interest'][0], 'metadata': original['preparation_metadata']['income_document_records']['interest'][0]}])
        before = tax_engine.calculate_return(original['data']); after = tax_engine.calculate_return(result['data'])
        appended = deepcopy(original['data']); appended['interest'].append({'payer': 'Same synthetic payer', 'taxable': '1200'})
        naive = tax_engine.calculate_return(appended)
        self.assertEqual(before['lines']['2b'], 1350); self.assertEqual(after['lines']['2b'], 1550)
        self.assertEqual(naive['lines']['2b'], 2550)
        self.assertEqual(after['summary']['refund'], 1215); self.assertEqual(naive['summary']['refund'], 1095)

    def test_dividend_replacement_preserves_other_same_payer_review_and_amounts(self):
        state = synthetic_income_state()
        state['data']['dividends'].append({**tax_engine.ROW_DEFAULTS['dividends'], 'payer': 'Same synthetic payer', 'ordinary': '100'})
        state['preparation_metadata']['income_document_records']['dividends'][0]['is_placeholder'] = True
        state['preparation_metadata']['income_document_records']['dividends'].append(income.new_record())
        state = income.normalize_state(state)
        ids = [x['record_id'] for x in state['preparation_metadata']['income_document_records']['dividends']]
        state = income.mark_reviewed(state, 'dividends', ids[1], STAMP)
        proposal = income.plan(state['data'], state['preparation_metadata'], 'dividends', [ids[0]],
            [{**tax_engine.ROW_DEFAULTS['dividends'], 'payer': 'Same synthetic payer', 'ordinary': '350'}])
        result = income.apply(state['data'], state['preparation_metadata'], proposal)
        self.assertEqual(result['data']['dividends'][1], state['data']['dividends'][1])
        self.assertEqual(result['metadata']['income_document_records']['dividends'][1]['record_id'], ids[1])
        self.assertTrue(result['metadata']['income_document_records']['dividends'][1]['reviewed'])
        self.assertFalse(result['metadata']['income_document_records']['dividends'][0]['reviewed'])
        self.assertEqual(tax_engine.calculate_return(state['data'])['lines']['3b'], 300)
        self.assertEqual(tax_engine.calculate_return(result['data'])['lines']['3b'], 450)
        self.assertEqual(result['metadata']['income_import_events'][0]['receipt']['collection'], 'dividends')

    def test_failure_and_nonplaceholder_selection_cannot_replace_income(self):
        state = synthetic_income_state(); original = deepcopy(state)
        failed = income.plan(state['data'], state['preparation_metadata'], 'interest', [], [], successful=False)
        result = income.apply(state['data'], state['preparation_metadata'], failed)
        self.assertEqual(result['data'], original['data']); self.assertEqual(result['metadata'], original['preparation_metadata'])
        uid = state['preparation_metadata']['income_document_records']['interest'][1]['record_id']
        with self.assertRaises(ValueError): replacement(state, targets=[uid])
        with self.assertRaises(ValueError): replacement(state, targets=[str(uuid.uuid4())])
        self.assertEqual(state, original)

    def test_stale_target_refused_unrelated_edit_and_adjacent_targets_preserved(self):
        state = synthetic_income_state(); proposal = replacement(state)
        stale = deepcopy(state); stale['data']['interest'][0]['taxable'] = '1001'
        with self.assertRaises(ValueError): income.apply(stale['data'], stale['preparation_metadata'], proposal)
        unrelated = deepcopy(state); unrelated['data']['interest'][1]['taxable'] = '351'
        result = income.apply(unrelated['data'], unrelated['preparation_metadata'], proposal)
        self.assertEqual(result['data']['interest'][1]['taxable'], '351')
        adjacent = deepcopy(state); adjacent['preparation_metadata']['income_document_records']['interest'][1]['is_placeholder'] = True
        adjacent['data']['interest'].append({'payer': 'Same synthetic payer', 'taxable': '25'})
        adjacent['preparation_metadata']['income_document_records']['interest'].append(income.new_record())
        adjacent = income.normalize_state(adjacent)
        ids = [x['record_id'] for x in adjacent['preparation_metadata']['income_document_records']['interest'][:2]]
        result = income.apply(adjacent['data'], adjacent['preparation_metadata'], replacement(adjacent, targets=ids))
        self.assertEqual([r['taxable'] for r in result['data']['interest']], ['1200.00', '25'])
        self.assertEqual(len(result['receipt']['archived_replaced_records']), 2)

    def test_event_replay_is_noop_changed_payload_or_target_is_refused(self):
        state = synthetic_income_state(); proposal = replacement(state)
        first = income.apply(state['data'], state['preparation_metadata'], proposal)
        current = {'data': first['data'], 'preparation_metadata': first['metadata']}
        replay = replacement(current, targets=proposal['payload']['target_ids'], event_id=proposal['event_id'])
        second = income.apply(first['data'], first['metadata'], replay)
        self.assertTrue(second['already_applied']); self.assertEqual(second['data'], first['data']); self.assertEqual(second['metadata'], first['metadata'])
        with self.assertRaises(ValueError): replacement(current, [{'taxable': '1201'}], proposal['payload']['target_ids'], proposal['event_id'])
        with self.assertRaises(ValueError): replacement(current, targets=[str(uuid.uuid4())], event_id=proposal['event_id'])
        altered = deepcopy(proposal); altered['payload']['replacements'][0]['taxable'] = '1201.00'
        with self.assertRaises(ValueError): income.apply(first['data'], first['metadata'], altered)

    def test_strict_receipt_money_metadata_and_typed_refusals(self):
        state = synthetic_income_state(); result = income.apply(state['data'], state['preparation_metadata'], replacement(state))
        for field, value in (('unknown', 'x'), ('collection', []), ('removed_record_ids', ['not a UUID']), ('result_record_ids', [])):
            with self.subTest(field=field):
                receipt = deepcopy(result['receipt']); receipt.pop('status'); receipt[field] = value
                with self.assertRaises(ValueError): income.validate_receipt(receipt)
        for amount in ('NaN', '1e3', '12.345', '', True):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError): replacement(state, [{'taxable': amount}])
        malformed = deepcopy(state); malformed['preparation_metadata']['income_document_records']['interest'][0]['unresolved_fields'] = [{}]
        with self.assertRaises(ValueError): income.normalize_state(malformed)
        with self.assertRaises(ValueError): replacement(state, targets=[{}])
        duplicate = deepcopy(state); duplicate['preparation_metadata']['income_document_records']['dividends'][0]['record_id'] = duplicate['preparation_metadata']['income_document_records']['interest'][0]['record_id']
        with self.assertRaises(ValueError): income.normalize_state(duplicate)


if __name__ == '__main__':
    unittest.main()
