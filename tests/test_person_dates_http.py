"""Host HTTP/SQLite DOB save, reload, backup and rejected-update acceptance."""
from copy import deepcopy
import io
import unittest
import urllib.error
import urllib.request
from pypdf import PdfReader
from tests.test_person_dates import prepared


class PersonDateHTTPTests(unittest.TestCase):
    def test_DOB_edit_invalid_update_and_paper_export_preserve_saved_return(self):
        from tests.test_income_metadata import IncomePreparationAPI
        api=IncomePreparationAPI('runTest');api.setUp()
        try:
            saved=api.save(prepared());self.assertEqual(saved['result']['person_age_rules']['taxpayer']['day_before_birthday_age'],25)
            self.assertEqual(api.reopen()['result']['lines']['35a'],1649)
            exported=api.call('/api/returns/'+api.ident+'/export.json')
            self.assertEqual(exported['data']['taxpayer']['birth_date'],'2001-01-01')
            changed=deepcopy(saved['data']);changed['taxpayer']['birth_date']='2001-01-02'
            edited=api.save(changed);self.assertEqual(api.reopen()['result']['lines']['35a'],1000)
            self.assertEqual(edited['result']['person_age_rules']['taxpayer']['day_before_birthday_age'],24)
            invalid=deepcopy(edited['data']);invalid['taxpayer']['birth_date']='2001-02-29'
            with self.assertRaises(urllib.error.HTTPError) as caught:api.save(invalid)
            self.assertEqual(caught.exception.code,400);self.assertEqual(api.reopen(),edited)
            restored=api.save(exported['data']);self.assertEqual(restored['result']['lines']['35a'],1649)
            with urllib.request.urlopen(api.origin+'/api/returns/'+api.ident+'/form1040.pdf') as response:
                fields=PdfReader(io.BytesIO(response.read())).get_fields()
            self.assertEqual(str(fields['topmostSubform[0].Page2[0].f2_31[0]']['/V']),'1649')
        finally:api.tearDown()


if __name__=='__main__':unittest.main()
