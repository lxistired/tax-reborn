"""Host-only real save/reopen and official high-income PDF export regression."""
import unittest
from niit_packet_qa import check_http_packet


class NIITPacketHTTP(unittest.TestCase):
    def test_capital_NIIT_and_positive_AMT_saved_exported_packets(self):
        report = check_http_packet()
        self.assertEqual(report['cases'],2)
        self.assertEqual(report['passed'],2)


if __name__ == '__main__':
    unittest.main()
