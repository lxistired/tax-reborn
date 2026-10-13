"""Held-out whole-return acceptance; expected values are frozen literal IRS oracles.

No expected amount is obtained from tax_engine, default_return, demos, or its rules.
Run from the delivery root: python3 -m unittest discover -s tests -p test_acceptance.py -v
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURE = ROOT / "fixtures" / "independent_cases.json"
FROZEN_SHA256 = "bc6401f56c0b9ae7572908a23c6b5159c809723dde4ef9a0ae02c55c905e7d15"
RAW = FIXTURE.read_bytes()
if hashlib.sha256(RAW).hexdigest() != FROZEN_SHA256:
    raise RuntimeError("Independent tax oracle changed after freeze; investigate before importing engine")
ORACLE = json.loads(RAW)
CASES = {case["id"]: case for case in ORACLE["supported_cases"]}

# Transparent, root-approved qualification additions after the oracle freeze.
# Expected values and original submitted fixture remain byte-for-byte unchanged.
# These two dividend samples have verified payer/holding-period qualification;
# these two pension samples are domestic qualified retirement-plan distributions.
QUALIFIED_DIVIDEND_CASES = {
    "mfj_ctc_qualified_dividends", "itemized_and_qualified_capital_gains"
}
QUALIFIED_PENSION_CASES = {"senior_social_security", "mfj_two_seniors_phaseout_each"}


def adapted_input(case):
    data = deepcopy(case["input"])
    if case["id"] in QUALIFIED_DIVIDEND_CASES:
        data["eligibility"]["qualified_dividends_eligible"] = True
    if case["id"] in QUALIFIED_PENSION_CASES:
        data["retirement"]["qualified_plan_confirmed"] = True
    return data


def nested(data, path):
    for key in path.split("."):
        data = data[key]
    return data


def apply_patch(data, patch):
    keys = patch["path"]
    current = data
    for key in keys[:-1]:
        current = current[int(key)] if isinstance(current, list) else current[key]
    key = int(keys[-1]) if isinstance(current, list) else keys[-1]
    current[key] = deepcopy(patch["value"])


class IndependentTaxAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Product import happens after frozen fixture integrity has been verified.
        spec = importlib.util.spec_from_file_location("held_out_tax_engine", ROOT / "tax_engine.py")
        cls.engine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.engine)

    def test_frozen_oracle_integrity(self):
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), FROZEN_SHA256)
        self.assertEqual(ORACLE["tax_year"], 2025)
        self.assertEqual(len(CASES), 22)
        self.assertEqual(len(ORACLE["blocking_cases"]), 44)
        self.assertEqual(len(CASES), len(ORACLE["supported_cases"]), "duplicate case identifier")
        for case in CASES.values():
            self.assertTrue(case["manual_workings"])
            self.assertTrue(case["source_ids"])

    def check_supported(self, case):
        submitted = adapted_input(case)
        before = deepcopy(submitted)
        result = self.engine.calculate_return(submitted)
        self.assertEqual(submitted, before, "calculation mutated taxpayer's input")
        self.assertIs(result["can_prepare"], True, result.get("blocking_issues"))
        self.assertEqual(result["blocking_issues"], [])
        self.assertEqual(result["tax_year"], 2025)
        self.assertEqual(result["currency"], "USD")
        self.assertEqual(result["filing_status"], submitted["filing_status"])
        actual = result["lines"]
        # Every contract line is compared, including explicit zero lines. A correct
        # refund cannot hide an incorrect adjustment/credit/withholding allocation.
        for line, amount in case["expected"]["lines"].items():
            with self.subTest(line=line):
                self.assertIs(type(actual[line]), int, "whole-dollar integer required")
                self.assertEqual(actual[line], amount)
        for key, value in case["expected"]["summary"].items():
            with self.subTest(summary=key):
                self.assertEqual(result["summary"][key], value)
        for path, value in case["expected"]["schedules"].items():
            with self.subTest(schedule=path):
                self.assertEqual(nested(result["schedules"], path), value)
        # Independent return-level conservation identities, not copied engine branches.
        self.assertEqual(actual["9"] - actual["10"], actual["11a"])
        self.assertEqual(actual["12e"] + actual["13a"] + actual["13b"], actual["14"])
        self.assertEqual(max(0, actual["11b"] - actual["14"]), actual["15"])
        self.assertEqual(actual["16"] + actual["17"], actual["18"])
        self.assertEqual(actual["19"] + actual["20"], actual["21"])
        self.assertEqual(max(0, actual["18"] - actual["21"]) + actual["23"], actual["24"])
        self.assertEqual(actual["25a"] + actual["25b"] + actual["25c"], actual["25d"])
        self.assertEqual(sum(actual[k] for k in ["27a", "28", "29", "30", "31"]), actual["32"])
        self.assertEqual(actual["25d"] + actual["26"] + actual["32"], actual["33"])
        self.assertEqual(actual["33"] - actual["24"], actual["34"] - actual["37"])
        self.assertEqual(actual["34"], actual["35a"] + actual["36"])
        self.assertFalse(actual["34"] > 0 and actual["37"] > 0)
        self.assertTrue(result["trace"], "return must disclose a calculation trace")
        self.assertIn("38", result["not_computed_lines"], "penalty placeholder must be labeled uncomputed")

    def check_blocking(self, case):
        submitted = adapted_input(CASES[case["base_case"]])
        for patch in case["patches"]:
            apply_patch(submitted, patch)
        before = deepcopy(submitted)
        mode = case["expected_mode"]
        if mode == "reject":
            with self.assertRaises(ValueError, msg=case["reason"]):
                self.engine.calculate_return(submitted)
        else:
            try:
                result = self.engine.calculate_return(submitted)
            except ValueError:
                if mode != "reject_or_block":
                    raise
            else:
                self.assertIs(result["can_prepare"], False, case["reason"])
                self.assertTrue(result["blocking_issues"], "blocked result needs specific reasons")
                for issue in result["blocking_issues"]:
                    self.assertIsInstance(issue, str)
                    self.assertTrue(issue.strip())
                if case["message_contains_any"]:
                    message = " ".join(result["blocking_issues"]).lower()
                    self.assertTrue(any(word.lower() in message for word in case["message_contains_any"]), message)
        self.assertEqual(submitted, before, "failed calculation mutated taxpayer's input")

    def test_qualified_dividend_confirmation_required(self):
        for case_id in sorted(QUALIFIED_DIVIDEND_CASES):
            with self.subTest(case=case_id):
                data = adapted_input(CASES[case_id])
                data["eligibility"]["qualified_dividends_eligible"] = False
                result = self.engine.calculate_return(data)
                self.assertIs(result["can_prepare"], False)
                self.assertTrue(any("qualified dividends" in issue.lower() for issue in result["blocking_issues"]))

    def test_qualified_pension_confirmation_required(self):
        for case_id in sorted(QUALIFIED_PENSION_CASES):
            with self.subTest(case=case_id):
                data = adapted_input(CASES[case_id])
                data["retirement"]["qualified_plan_confirmed"] = False
                result = self.engine.calculate_return(data)
                self.assertIs(result["can_prepare"], False)
                self.assertTrue(any("qualified us retirement-plan" in issue.lower() for issue in result["blocking_issues"]))

    def test_nonqualified_annuity_cannot_hide_niit(self):
        # Independently found after the freeze: a 1099-R CodeD commercial annuity
        # is NIIT income. Its classification cannot be inferred from a gross box.
        # IRS8960: min(100000,300000-200000)*3.8%=3800, unimplemented => block.
        data = adapted_input(CASES["single_senior_phaseout"])
        data["name"] = "Synthetic nonqualified commercial annuity scope probe"
        data["w2"][0].update(wages="200000", social_security_wages="176100",
                            medicare_wages="200000", social_security_withholding="10918.20",
                            medicare_withholding="2900", federal_withholding="40000")
        data["retirement"].update(pension_gross="100000", pension_taxable="100000",
                                  taxable_amounts_confirmed=True, qualified_plan_confirmed=False,
                                  early_distribution_exception_confirmed=True)
        data["notes"] = "Synthetic1099-R Box7CodeD nonqualified annuity; Box2a taxable100000."
        result = self.engine.calculate_return(data)
        self.assertIs(result["can_prepare"], False, "nonqualified annuity would otherwise omit3800 NIIT")
        self.assertTrue(any("nonqualified" in issue.lower() for issue in result["blocking_issues"]))


def supported_test(case):
    def test(self):
        self.check_supported(case)
    test.__doc__ = "Independent complete return: " + case["id"]
    return test


def blocking_test(case):
    def test(self):
        self.check_blocking(case)
    test.__doc__ = case["reason"]
    return test


for CASE in ORACLE["supported_cases"]:
    setattr(IndependentTaxAcceptance, "test_return_" + CASE["id"], supported_test(CASE))
for CASE in ORACLE["blocking_cases"]:
    setattr(IndependentTaxAcceptance, "test_guard_" + CASE["id"], blocking_test(CASE))


if __name__ == "__main__":
    unittest.main(verbosity=2)
