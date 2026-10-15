"""Owned binary filing-status input reaches calculation and durable SQLite."""
import base64
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'web'), str(ROOT/'scripts')]
import binary_tax
import return_metadata
import server
import tax_engine
from interop.form_core.native_document_reference import replace_form, store_document_bytes


def request():
    return json.loads((ROOT/'fixtures/binary-tax/filing-status-request.json').read_text())


def changed_request(mutator):
    req = request()
    doc, buffers, context, *_ = binary_tax._context(req)
    form = doc.formsets[0].forms[0]
    form = replace(form, hash_state=replace(form.hash_state, buffers=tuple(
        replace(buffer, nodes=tuple(mutator(node) for node in buffer.nodes))
        for buffer in form.hash_state.buffers)))
    doc = replace_form(doc, (0,0), form)
    req['base64'] = base64.b64encode(store_document_bytes(doc,buffers,template_context=context)).decode()
    return req


def event(candidate):
    return dict(event_id=str(uuid.uuid4()),source_document=dict(document_id=str(uuid.uuid4()),
        return_id=str(uuid.uuid4()),name='fictional-setup.taxbin',method='taxml',taxml_receipt=candidate['receipt']),
        filing_status=candidate['filing_status'],previous_filing_status='single',reviewed_at='2026-10-15T04:45:00Z')


class BinaryFilingStatus(unittest.TestCase):
    def test_caller_owned_binding_not_assumed_FDI_and_no_complete_return_claim(self):
        req = request(); before = deepcopy(req)
        result = binary_tax.inspect_request(req)
        candidate, = result['setup_candidates']
        self.assertEqual(req,before)
        self.assertTrue(candidate['can_review'])
        self.assertEqual(candidate['filing_status'],'mfj')
        self.assertEqual(candidate['source_owner']['formset_id'],'OWNED2025SETUP')
        self.assertEqual([field['status'] for field in candidate['fields']],
                         ['unchecked','checked','unchecked','unchecked','unused'])
        self.assertEqual(candidate['fields'][4]['raw64'],'1')
        self.assertTrue(all(field['current_format']==255 for field in candidate['fields']))
        self.assertFalse(result['full_return_imported'])
        self.assertFalse(result['tax_values_imported'])
        self.assertFalse(result['original_program_acceptance_verified'])

    def test_each_status_uses_registry_ordinals_and_single_selection(self):
        for ordinal,status in enumerate(('single','mfj','mfs','hoh','qss'),1):
            req = changed_request(lambda node:replace(node,raw=int(node.field_index==ordinal),specific_attributes=1))
            candidate, = binary_tax.inspect_request(req)['setup_candidates']
            with self.subTest(status=status):
                self.assertEqual(candidate['filing_status'],status)
                self.assertTrue(candidate['can_review'])

    def test_all_current_format_bytes_are_ignored_for_boxes(self):
        for flag in range(256):
            req=changed_request(lambda node:replace(node,flag10=flag))
            candidate,=binary_tax.inspect_request(req)['setup_candidates']
            self.assertEqual(candidate['filing_status'],'mfj')

    def test_conflict_all_unused_noncanonical_or_diagnostic_refused(self):
        variants = [lambda node:replace(node,raw=1,specific_attributes=1),
            lambda node:replace(node,specific_attributes=2),
            lambda node:replace(node,raw=2) if node.field_index==2 else node,
            lambda node:replace(node,header=128) if node.field_index==2 else node,
            lambda node:replace(node,specific_attributes=17) if node.field_index==2 else node]
        for mutate in variants:
            candidate,=binary_tax.inspect_request(changed_request(mutate))['setup_candidates']
            self.assertFalse(candidate['can_review']);self.assertIsNone(candidate['filing_status'])

    def test_actual_calculation_and_sqlite_reopen_preserve_receipt(self):
        candidate,=binary_tax.inspect_request(request())['setup_candidates']
        data=tax_engine.default_return()
        data['name']='Fictional filing-status migration'
        data['w2']=[dict(tax_engine.ROW_DEFAULTS['w2'],employer='Synthetic',wages='60000')]
        before=tax_engine.calculate_return(data)
        data['filing_status']=candidate['filing_status']
        meta=return_metadata.normalize(data,None,tax_engine.ROW_DEFAULTS['w2'])
        receipt=event(candidate);meta['setup_import_events']=[receipt]
        with tempfile.TemporaryDirectory() as directory:
            store=server.Store(Path(directory))
            saved=store.save(dict(data=data,metadata=meta))
            reopened=server.Store(Path(directory)).get(saved['id'])
            self.assertEqual(reopened['data']['filing_status'],'mfj')
            self.assertEqual(reopened['metadata']['setup_import_events'],[receipt])
            self.assertLess(reopened['result']['summary']['total_tax'],before['summary']['total_tax'])
            self.assertFalse(reopened['data']['eligibility']['all_income_reported'])
            self.assertFalse(reopened['result']['can_prepare'])
            # A pre-feature client omitting this namespace preserves saved history.
            legacy=deepcopy(meta);legacy.pop('setup_import_events')
            self.assertEqual(store.save(dict(id=saved['id'],data=data,metadata=legacy))['metadata']['setup_import_events'],[receipt])
            for changed in ([],[{**receipt,'filing_status':'single'}],[receipt,dict(receipt,event_id=str(uuid.uuid4()))]):
                bad=deepcopy(meta);bad['setup_import_events']=changed
                with self.assertRaises(ValueError):store.save(dict(id=saved['id'],data=data,metadata=bad))


if __name__=='__main__':unittest.main()
