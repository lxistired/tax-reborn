from copy import deepcopy
import urllib.request,urllib.error,unittest
from foreign_address_qa import CASES,apply_address,verify_packet
from payment_voucher_qa import cases,return_for
import tax_engine,server,official_forms

class ForeignAddressHTTP(unittest.TestCase):
    def test_saved_reopened_backup_and_serialized_packet(self):
        from tests.test_income_metadata import IncomePreparationAPI
        api=IncomePreparationAPI('runTest');api.setUp()
        try:
            d=apply_address(return_for(tax_engine,cases()[0]),CASES[1]);saved=api.save(d)
            self.assertEqual(api.reopen(),saved);self.assertEqual(server.Store(api.temp.name).get(saved['id']),saved)
            exported=api.call('/api/returns/'+saved['id']+'/export.json')
            self.assertEqual(exported['data'],saved['data'])
            restored=api.call('/api/returns',{'data':exported['data'],'metadata':exported['metadata']})
            self.assertNotEqual(restored['id'],saved['id']);self.assertEqual(restored['data'],saved['data'])
            with urllib.request.urlopen(api.origin+'/api/returns/'+saved['id']+'/paper-packet.pdf')as response:raw=response.read()
            verify_packet(raw,CASES[1],official_forms)
            invalid=deepcopy(saved['data']);invalid['filing_details']['mailing_address_type']='unknown'
            with self.assertRaises(urllib.error.HTTPError)as error:api.save(invalid)
            self.assertEqual(error.exception.code,400);self.assertEqual(api.reopen(),saved)
        finally:api.tearDown()

if __name__=='__main__':unittest.main()
