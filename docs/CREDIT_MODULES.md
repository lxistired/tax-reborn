# IRA, HSA, education and Marketplace calculations — US federal 2025

These four modules calculate real deductions, credits, additional taxes and advance-credit repayment in the shared Form 1040 engine. They run locally with Python’s standard library. They do not submit a return. A qualification failure remains a blocking issue even when intermediate arithmetic is available.

## Inputs, outputs and calculation order

`tax_credits.default_inputs()` supplies the four input sections: `ira`, `hsa`, `education` and `marketplace`. `row_templates()` supplies HSA account, education student and Marketplace month shapes. `ui_fields()` supplies actual enums and plain-language qualification help to the desktop/mobile intake. Submitted money is a decimal USD string with at most two fractional digits. Output money is an integer whole dollar. Unknown fields and invalid types raise `ValueError`; string values such as `"true"` are not accepted as confirmations.

Each pure function accepts one section plus derived context. It returns `deduction`, `other_income`, `additional_tax`, `nonrefundable_credit`, `refundable_credit`, `repayment`, `can_compute`, `blocking_issues`, `warnings`, `trace` and `form_lines`. No function imports the main engine. A disabled section containing monetary values, accounts, students or1095-A rows blocks rather than discarding those inputs.

| Function | Required derived context | Main-return use |
|---|---|---|
| `calculate_hsa` | Filing status and each spouse’s age | Taxable distributions enter Schedule 1 income; contribution deduction enters1040 line 10;20% distribution and current-excess6% taxes enter line 23. |
| `calculate_ira` | Status, ages, each owner’s eligible compensation, MAGI beforeIRA, SSA/distribution flags | Deduction enters line 10 before the Social Security and student-loan worksheets. |
| `calculate_education` | Final MAGI, claimant age/status, tax-liability limit and dependency facts | Nonrefundable credit enters line 20 before CTC capacity; refundable AOTC enters line 29. |
| `calculate_marketplace` | Final household AGI, nontaxableSSA, exempt interest, tax-family size and SE-health deduction | ExcessAPTC repayment enters line 17; netPTC enters line 31. |

IRA compensation includes eligible wages and nonnegative net self-employment compensation after deductible halfSE. The module requires confirmation of any further compensation/MAGI exclusions. It blocks IRA contributions with Social Security or same-year IRA distributions instead of silently applying the simpler worksheet. Marketplace household income includes required-filer dependent MAGI; it can be negative before combining the household totals.

## Implemented worksheets and their boundaries

| Module | Implemented 2025 rules | Explicit remaining special cases |
|---|---|---|
| IRA | $7,000 limit; $8,000 at age50; aggregate traditional/Roth limit and compensation; spousal contribution pool; employer-plan phaseouts; reduced deduction rounded upward to the next$10 with$200 minimum; Roth MAGI screening; nondeductible contribution and prior basis when no distribution occurs. | Rollovers/recharacterizations/excess correction; SSA AppendixB interaction; contribution plus distribution/conversion Form 8606 allocation. Excess contribution requires review, not a silently allowed deduction. |
| HSA | Monthly first-day eligibility; $4,300 self/$8,550 family;55+catch-up; employer contribution reduction; married family allocation; last-month rule with testing-period acknowledgment; taxable distributions; actual-date65/disability/death exceptions; documented timely excess withdrawals; current6% excess tax. | Prior-year excess, testing-period failure, MSA/qualified funding distribution worksheets and employer-excess correction allocation. Employer excess not already included inW2 income blocks. |
| Education | Per-student AOTC and household LLC; qualified expenses net of tax-free assistance and expenses used elsewhere; $2,500 maximumAOTC/$2,000 maximumLLC;80–90k single-family and160–180kMFJ phaseouts; nonrefundable tax limit;40% refundableAOTC; actual claimant-under24 refund tests. | Foreign MAGI/credit recapture, scholarship-taxability and529 optimization, prior disallowance/Form 8862 review. Claimant/dependent allocation, timelyTIN, eligible institution,1098-T or valid exception and no double benefit must be confirmed. |
| Marketplace | All12 monthly1095-A records; annual line 11 only with unchanged raw premiums/SLCSP and full-year eligibility; monthly lines12–23 otherwise;2024FPL for2025; published applicable-percentage table; below-poverty exceptions; excessAPTC caps; ordinaryMFS no-credit reconciliation. | Shared-policy allocation, marriage alternative, QSEHRA/ICHRA, mixed lawful presence and self-employed health-insurance/PTC iterative worksheets. Missing SLCSP or unverified employer/MEC coverage blocks. |

HSA age65 is a transaction-date exception. Turning65 during2025 does not exempt distributions made before the birthday. The intake therefore requires a confirmed allocation of taxable distributions eligible for the exception. Form 5329’s excess-tax value includes contributions for2025 made in2026; a zero value cannot be assumed without confirmation. Married HSA calculations require actual spouse coverage even if only one spouse has an account.

For2025 PTC, income above400%FPL does not by itself eliminate the credit. The household contribution is8.5% at that level, while excessAPTC repayment has no cap. At399%FPL the single repayment cap is$1,625; at400% it is uncapped. Same-state duplicateSLCSP values from multiple policies must not be added blindly; the supplied benchmark must be the actual applicable householdSLCSP.

## Independent expected values

The dedicated fixture contains **28 literal cases:7 per module**, plus **21 blocking cases**. Expected arithmetic was recorded before calling the calculation functions. All dollar amounts below are synthetic tax year 2025 inputs and manual IRS worksheet results, not outputs from commercial tax software.

| Check | Independent expected amount |
|---|---:|
| Covered singleIRA, MAGI$84,000, contribution$7,000 | Deduction$3,500 |
| Covered singleIRA just below upper phaseout | Minimum deduction$200 |
| CoveredMFJ MAGI$126,500 plus uncovered spouse contribution | Covered deduction$6,830; spouse$7,000; total$13,830 |
| Self HSA, $1,000 employer contribution plus$3,000 personal | Deduction$3,000; total limit$4,300 |
| NonmedicalHSA taxable distribution$1,000 before65 | Income$1,000; additional tax$200 |
| HSA excess$700, confirmed account value$700 |6% tax$42 |
| FullAOTC with$500 remaining tax capacity | Refundable$1,000; nonrefundable$500 |
| Two eligibleAOTC students,MFJ midphase | Refundable$1,000; nonrefundable$1,500 |
| SinglePTC income$37,650 at250%FPL | Annual contribution$1,506; allowedPTC$6,294; net credit$294 |
| Same income, excessive advances | Uncapped excess$2,706; capped repayment$975 |

The education phaseout retains at least three decimal places, as permitted by Form 8863. The IRA source has a real editorial discrepancy: Pub590A Example1 prints$6,825, while the same publication’s Worksheet1-2 and the1040 IRA worksheet explicitly require rounding upward to the next$10, giving$6,830. This implementation and oracle follow the explicit worksheets. This conflict is disclosed rather than changing the result to match the example.

The initial fixture was recorded at **2026-10-13T04:09:21.839642+00:00**. Before calculation execution, explicit qualification fields were added and one synthetic enrollment premium was raised to keep an advance credit below that premium; the premium ceiling remained nonbinding. **All28 expected payloads remained identical**. The prior fixture SHA and adaptation are recorded in its metadata. After freeze, the test adapter added HSA distribution-breakdown and age65 transaction-timing confirmations for already specified synthetic facts. It did not change money expectations.

- Current frozen fixture SHA256: `e5a68f152b820f69a4455ce8b34a17ecc094b594018bfb29c6c1f497aff73629`.
- Expected-only payload SHA256: `32ea6e439bec7678e8db90300e7cdb0b3f07473f79b5cda0521f272907fdee65`.
- Original22 whole-return fixture remains unchanged: `bc6401f56c0b9ae7572908a23c6b5159c809723dde4ef9a0ae02c55c905e7d15`.

At the04:42 snapshot, `tests/test_credits.py` contained **70 tests**:61 component/qualification/rounding checks and9 whole-return integration checks. The latter use separately chosen literal Form 1040 values, including IRA+HSA+AOTC ordering, HSA income/taxes, PTC repayment/refund, and combined1099 withholding before rounding. For example, a$60,000W2 return with$7,000IRA+$3,000HSA+$4,000 qualifyingAOTC expenses produces AGI$50,000, taxable income$34,250, table tax$3,875, total tax$2,375 and refund$5,125 with$6,500 withholding.

The first two whole-returnPTC integration checks failed because the test helper lowered W2 wages but retained the original higher Box 6 withholding. The engine correctly credited the resulting$324 additional Medicare withholding. The helper was corrected to provide consistent synthetic payroll boxes. Literal expected tax/refund amounts were not changed. The failed run and correction remain in the private research receipts.

## Sources and dated receipts

All rules use official IRS tax year 2025 materials. Live HTML can change; snapshots were retained privately on2026-10-13. No runtime network or vendor data is required. Main sources are [Pub590A](https://www.irs.gov/publications/p590a), [1040 instructions](https://www.irs.gov/instructions/i1040gi), [8889 instructions](https://www.irs.gov/instructions/i8889), [8863 instructions](https://www.irs.gov/instructions/i8863), [2025 Form 8863](https://www.irs.gov/pub/irs-prior/f8863--2025.pdf), [8962 instructions](https://www.irs.gov/instructions/i8962), and [2025 Form 5329](https://www.irs.gov/pub/irs-prior/f5329--2025.pdf).

| Snapshot | Retrieved UTC | SHA256 |
|---|---|---|
| Pub590A |2026-10-13T04:29:16.674966+00:00|`c0fb6d539a6f50b9b92556da520cc23b72bcbdf0f54af04a294efe81ae876ea8`|
|8889 instructions|2026-10-13T04:29:16.629442+00:00|`d4e4ecb55c23454d252e51bf3d83c5e6e39449471d1fd6ba79b6f95fad10726f`|
|8863 instructions|2026-10-13T04:29:16.635253+00:00|`acc8c1081a5f9695c85d4af1d5f7df169a4608a0d26f6b84533875c96f68cff1`|
|2025 Form 8863|2026-10-13T04:29:16.517269+00:00|`a251a1cfbd613d5dd81646b276b1cc3562d7efb8bed969491eada7c8eb0d8e00`|
|8962 instructions|2026-10-13T04:29:18.354337+00:00|`d52bf784b4a1b9bcbd4068cf6ea92880d7129730785da3e40d68e63f51a25751`|
|2025 Form 5329|2026-10-13T04:29:18.231698+00:00|`2ad77023aebb280c90e4083c29c931b4f0fc9fc6264183e812d2361ba7e916bb`|

## Reproduce the validated backend

From the delivery directory:

```sh
python3 -m unittest discover -s tests -p test_credits.py -v
python3 -m unittest discover -s tests -v
```

The independent final regression ran at **2026-10-13T04:42:32.934405–04:42:33.046825 UTC** and passed **176 tests**:70 original independent,70 new independentcredit,13 core and23 extension tests. Eight tracked source/fixture hashes were unchanged before and after the run. The moduleSHA is `887f95f1b7910214c0afd3ddfb6a8e7548bff9d62df876a0e4a400996668d7e2`; integrated engineSHA is `22e00289c7c9079a485d59907620958b8791155f997563da0562f6e46db63eaf`. The machine-readable [run receipt](credit_validation_20261013.json) records every tracked hash and command.

These tests measure selected calculations and blocking boundaries. Desktop/mobile behavior, saves, OCR intake, PDF output, WASM execution, state-return calculations, electronic filing and originalTurboTax parity require separate evidence. `can_prepare` is the supported-calculation status; `form_readiness` separately describes whether a filing packet is available. General Form 2210 penalties remain uncomputed.

## Subsequent cents-rounding repair and latest regression

Independent source audit reproduced two education-expense rounding errors after the04:42 snapshot. AOTC tuition$1,500.49 plus materials$1,501.49 belongs on one expense line:$3,001.98 rounds to$3,002, giving tentative credit$2,251 rather than$2,250. LLC$1,001.49 plus required institutional materials$1,001.49 rounds to$2,003, giving$401 rather than$400. The module now adds cents before line rounding. Both failing tests were saved before the repair; the current dedicated suite has**72 passing tests**. The28 frozen module expected values remain unchanged.

The 05:07 independently executed full regression was**261 passed at2026-10-13 05:07 UTC**. Current moduleSHA256 is `a57cad57ff2b30848cd538e73bd4c9ee8e22e1b106bbb3f93e077ca8b73a3786`. The [final receipt](validation_20261013T050702Z.json) identifies the exact integrated engine and all13 tracked source/fixture hashes; before and after identities matched. The earlier176-test/887f95f1 module result above is preserved as a historical snapshot, not the final source identity.

## Final distribution and qualification retest — 05:12 UTC

One subsequent concrete cross-module omission was corrected: qualified employer-plan disability1099-R gross must also count in the Form8880 distribution window. A synthetic$5,000W2+$15,000 disability income+$2,000 IRA return with the Saver module enabled but no declared distributions now blocks. Entering the actual$15,000 distribution reduces the Saver contribution base to zero. Its earned income is$20,000, above the2025Single/no-child EIC$19,104 limit even though IRA deductions reduceAGI to$18,000; the possible-EIC review screen now checks both limits. No generic ineligible-review bypass was added.

Classified disability now also requires the existing explicit qualified-US-plan confirmation. The test adapter records this already stated synthetic plan fact, without changing any frozen expected amount. A separate missing-plan-confirmation check verifies blocking. The dedicated disability suite now has12 tests; the other independent suites remain70/72/66.

The last independently executed full run was **2026-10-13T05:12:52.586188–05:12:52.734291 UTC**: **264 tests passed**, exit0, all13 tracked source/test/fixture hashes identical before and after. There are220 independently authored acceptance checks and44 core-authored checks; these are test counts, not features. CurrentengineSHA256 is `bcc299054e700efc2db9339f032facc5caea9be770052309b4fa5ee77142f5a3`; creditsSHA remains `a57cad57ff2b30848cd538e73bd4c9ee8e22e1b106bbb3f93e077ca8b73a3786`. The [current final receipt](final_validation_20261013.json) holds the exact complete source identities and counts. The [05:07 receipt](validation_20261013T050702Z.json) is preserved as historical evidence. All four frozen fixtures remain unchanged. The stated specialist, device, filing-packet and commercial-parity limits continue to apply.
