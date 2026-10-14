"""Public-safe, offline App regression checks against synthetic IRS2025 cases.

Expected values are independently calculated from IRS2025 primary worksheets.
No proprietary code, compiled tables, account data, keys, or native runtime is
needed. This verifies isolated supported calculation worksheets, not e-filing.
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys


def run(app_root: Path, cases_path: Path) -> dict:
    sys.path.insert(0, str(app_root.resolve()))
    engine = importlib.import_module("tax_engine")
    extended = importlib.import_module("tax_extended")
    document = json.loads(cases_path.read_text(encoding="utf-8"))
    failures = []
    for case in document["cases"]:
        inputs = case["inputs"]
        expected = case["expected"]
        status = inputs["filing_status"]
        agi = inputs["agi"]
        qualified = inputs["qualified_dividends"]
        deduction = engine.RULES["standard"][status]
        taxable = max(0, agi - deduction)
        if qualified:
            regular_tax, worksheet = engine.qualified_tax(taxable, qualified, status)
            regular_ordinary = worksheet["ordinary_income"]
        else:
            regular_tax = engine.ordinary_tax(taxable, status)
            regular_ordinary = taxable
        data = extended.default_inputs()["amt"]
        data.update(eligibility_confirmed=True,
                    iso_adjustment=str(inputs["additional_iso_adjustment"]))
        context = {
            "filing_status": status,
            "no_amt_preferences": inputs["additional_iso_adjustment"] == 0,
            "agi": agi,
            "total_deductions": deduction,
            "senior_deduction": 0,
            "deduction_addback": deduction,
            "preferred_income": qualified,
            "regular_ordinary_income": regular_ordinary,
            "regular_tax": regular_tax,
        }
        result = extended.alternative_minimum_tax(data, context, engine.RULES)
        lines = result["form_lines"]
        actual = {
            "standard_deduction": deduction,
            "regular_taxable_income": taxable,
            "regular_tax": regular_tax,
            "amti": lines["4"],
            "amt_exemption": lines["5"],
            "taxable_amti": lines["6"],
            "tentative_minimum_tax": lines["9"],
            "amt": result["tax"],
        }
        expected_values = {name: expected[name] for name in actual}
        if actual != expected_values or result["blocking_issues"]:
            failures.append({"id": case["id"], "inputs": inputs,
                             "expected": expected_values, "actual": actual,
                             "blocking_issues": result["blocking_issues"]})
    return {"year": 2025, "cases": len(document["cases"]),
            "passed": len(document["cases"]) - len(failures),
            "failed": len(failures), "failures": failures,
            "oracle": "Independent IRS2025 synthetic worksheet expectations",
            "original_vendor_runtime_executions": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", type=Path, required=True,
                        help="Directory containing Tax Reborn Python modules")
    parser.add_argument("--cases", type=Path,
                        default=Path(__file__).with_name("amt_2025_synthetic_cases.json"))
    parser.add_argument("--output", type=Path,
                        help="Optional JSON result path; no network is used")
    args = parser.parse_args()
    report = run(args.app_root, args.cases)
    serialized = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
