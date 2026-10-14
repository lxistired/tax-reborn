"""Host HTTP/SQLite, JSON backup and interactive paper-voucher export."""
from copy import deepcopy
import io,json,unittest,urllib.request,urllib.error
from pypdf import PdfReader
from payment_voucher_qa import cases,return_for,verify_packet
import tax_engine,server,official_forms


class PaymentVoucherHTTP(unittest.TestCase):
    def test_saved_cents_backup_and_actual_HTTP_PDF(self):
        from tests.test_income_metadata import IncomePreparationAPI
        api=IncomePreparationAPI('runTest');api.setUp()
        try:
            d=return_for(tax_engine,cases()[0]);d['filing_details'].update(paper_payment_amount_source='custom',paper_payment_amount='1000.25')
            saved=api.save(d);self.assertEqual(api.reopen(),saved)
            self.assertEqual(server.Store(api.temp.name).get(saved['id']),saved)
            exported=api.call('/api/returns/'+saved['id']+'/export.json');self.assertEqual(exported['data'],saved['data'])
            self.assertEqual(exported['result']['lines']['37'],2435)
            copy=api.call('/api/returns',{'data':exported['data'],'metadata':exported['metadata']})
            self.assertNotEqual(copy['id'],saved['id']);self.assertEqual(copy['data']['filing_details']['paper_payment_amount'],'1000.25')
            with urllib.request.urlopen(api.origin+'/api/returns/'+saved['id']+'/paper-packet.pdf')as response:pdf=response.read()
            verify_packet(pdf,'1000.25',official_forms)
            fields=PdfReader(io.BytesIO(pdf)).get_fields();self.assertEqual(fields['topmostSubform[0].Page2[0].f2_35[0]']['/V'],'2435')
            self.assertEqual(api.reopen(),saved)
            invalid=deepcopy(saved['data']);invalid['filing_details']['paper_payment_amount']='100000000'
            with self.assertRaises(urllib.error.HTTPError)as error:api.save(invalid)
            self.assertEqual(error.exception.code,400);self.assertEqual(api.reopen(),saved)
        finally:api.tearDown()


if __name__=='__main__':unittest.main()
