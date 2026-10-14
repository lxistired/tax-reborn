"""Actual loopback/SQLite Form8814 persistence and paper export; host only."""
from copy import deepcopy
import io
import unittest
import urllib.error
import urllib.request
from pypdf import PdfReader
from tests.test_child_income_integration import prepared


class ChildIncomeHTTPTests(unittest.TestCase):
    def test_save_reopen_backup_edit_and_actual_packet(self):
        from tests.test_income_metadata import IncomePreparationAPI
        api=IncomePreparationAPI('runTest');api.setUp()
        try:
            with urllib.request.urlopen(api.origin+'/tax_child_income.py') as response:
                self.assertEqual(response.status,200)
                self.assertIn(b'Form 8814 preparation calculation',response.read())
            saved=api.save(prepared());reopened=api.reopen()
            self.assertEqual(reopened['data']['child_income_election'],saved['data']['child_income_election'])
            self.assertEqual(reopened['result']['lines']['35a'],12484)
            export=api.call('/api/returns/'+api.ident+'/export.json')
            self.assertEqual(export['data']['child_income_election'],reopened['data']['child_income_election'])
            checklist=api.call('/api/returns/'+api.ident+'/paper-checklist.json')
            self.assertTrue(checklist['paper_preparation_complete'])
            with urllib.request.urlopen(api.origin+'/api/returns/'+api.ident+'/paper-packet.pdf') as response:
                pdf=PdfReader(io.BytesIO(response.read()))
            self.assertEqual(len(pdf.pages),12)
            self.assertEqual(sum(p.get('/TaxRebornForm')=='f8814' for p in pdf.pages),1)
            changed=deepcopy(reopened['data']);changed['child_income_election']['children'][0]['taxable_interest']='0'
            edited=api.save(changed);self.assertEqual(edited['result']['lines']['35a'],12868)
            self.assertEqual(api.reopen()['result']['lines']['35a'],12868)
            restored=api.save(prepared());self.assertEqual(restored['result']['lines']['35a'],12484)
            invalid=deepcopy(restored['data']);invalid['child_income_election']['children'][0]['birth_date']='2025-02-30'
            with self.assertRaises(urllib.error.HTTPError) as caught:api.save(invalid)
            self.assertEqual(caught.exception.code,400);self.assertEqual(api.reopen(),restored)
            blocked=deepcopy(restored['data']);blocked['child_income_election']['children'][0]['eligible_parent_confirmed']=False
            saved=api.save(blocked);self.assertFalse(saved['result']['can_prepare'])
            self.assertEqual(api.reopen()['data']['child_income_election']['children'][0]['taxable_interest'],'2000')
            self.assertFalse(api.call('/api/returns/'+api.ident+'/paper-checklist.json')['paper_preparation_complete'])
        finally:api.tearDown()

if __name__=='__main__':unittest.main()
