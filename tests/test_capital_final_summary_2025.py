"""Independent IRS fixtures across actual capital-tax and final refund/owed branches."""
import unittest
import tax_engine
from capital_final_summary_qa import check_app

class CapitalFinalSummary(unittest.TestCase):
    def test_actual_app_matches_fourteen_independent_IRS_cases(self):
        result = check_app(tax_engine)
        self.assertEqual(result['cases'], 14)
        self.assertEqual(result['passed'], 14)

if __name__ == '__main__':
    unittest.main()
