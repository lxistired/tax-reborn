"""Host-only actual HTTP/SQLite special distribution persistence."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tests.test_special_dividends import CASES,prepared

class SpecialDividendHTTPTests(unittest.TestCase):
    def test_real_http_save_reopen_export_and_review_invalidation(self):
        # Existing host harness owns a real isolated HTTP service and SQLite store.
        from tests.test_income_metadata import IncomePreparationAPI
        from copy import deepcopy
        api=IncomePreparationAPI('runTest');api.setUp()
        try:
            import urllib.request
            with urllib.request.urlopen(api.origin+'/tax_special_capital.py') as response:
                self.assertEqual(response.status,200)
                self.assertIn(b'Independent TY2025 Schedule D',response.read())
            data=prepared(CASES[2]);saved=api.save(data)
            reopened=api.reopen();row=reopened['data']['dividends'][0]
            self.assertEqual(row['unrecaptured_1250_gain'],'10000')
            self.assertEqual(row['collectibles_gain'],'10000')
            self.assertTrue(row['special_distribution_confirmed'])
            exported=api.call('/api/returns/'+api.ident+'/export.json')
            self.assertEqual(exported['data']['dividends'],reopened['data']['dividends'])
            entry=deepcopy(reopened['metadata']['income_document_records']['dividends'][0])
            entry.update(reviewed=True,reviewed_at='2026-10-14T10:00:00Z',reviewed_fingerprint=entry['row_fingerprint'])
            metadata=deepcopy(reopened['metadata']);metadata['income_document_records']['dividends'][0]=entry
            checked=api.save(reopened['data'],metadata)
            self.assertTrue(checked['metadata']['income_document_records']['dividends'][0]['reviewed'])
            changed=deepcopy(checked['data']);changed['dividends'][0]['collectibles_gain']='9999'
            changed=api.save(changed,checked['metadata'])
            self.assertFalse(changed['metadata']['income_document_records']['dividends'][0]['reviewed'])
            self.assertEqual(changed['data']['dividends'][0]['unrecaptured_1250_gain'],'10000')
        finally:api.tearDown()


if __name__=="__main__":unittest.main()
