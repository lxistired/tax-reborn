# Tax year 2025 additional federal worksheets

The new `tax_longtail.py` code independently implements five additional federal
workflows. It uses Decimal arithmetic and public IRS tax year 2025 forms and
instructions. It has no network calls, vendor code, filing API, or payment API.

The original 264 tests and their four independent oracle fixture files remain
unchanged. `tests/test_longtail.py` adds 59 directed checks, including 34 literal
source examples and handwritten numerical cases in
`fixtures/longtail_cases_2025.json`. These checks cover both valid results and
explicit rejection of unsupported or undocumented situations. They are not a
claim of exhaustive IRS certification or equality to every TurboTax scenario.

## Capital losses and wash sales

Verified positive short-term and long-term loss carry-ins are entered in the
existing `carryovers.capital_short` and `carryovers.capital_long` fields. They
reduce the corresponding Schedule D totals. A separate confirmation requires
the actual prior-year carryover worksheet and correct ownership allocation.
The carry-out worksheet retains the amount absorbed by ordinary income when
taxable income would be negative; it does not discard a loss just because the
printed Form 1040 line 15 has a zero floor.

For an ordinary security sale, documented nondeductible wash-sale loss is a
positive Form 8949 code W adjustment. Either the new `wash_sale_disallowed`
amount or a verified code W with the old adjustment field can be used; entering
both is rejected. The adjustment cannot exceed the actual unadjusted loss.
The user must verify the 61-day window, spouse/IRA/cross-broker records,
substantially identical securities, holding period and replacement basis.
The program applies verified records. It does not discover missing lots or
reconstruct an unreported cross-account wash sale.

Sources: [2025 Schedule D instructions](https://www.irs.gov/pub/irs-prior/i1040sd--2025.pdf),
[2025 Form 8949 instructions](https://www.irs.gov/pub/irs-prior/i8949--2025.pdf),
[2025 Publication 550](https://www.irs.gov/pub/irs-prior/p550--2025.pdf).

## Adoption credit

Form 8839 applies the $17,280 per-child limit, previously used expenses and
the $259,190–$299,190 MAGI phaseout. Domestic and foreign expense timing are
different. A final domestic special-needs adoption uses the documented state
or tribal determination. Up to $5,000 per eligible child is refundable on
Form 1040 line 30. The remaining credit is nonrefundable. Unexpired prior-year
nonrefundable credits are consumed oldest first; a remaining 2020 credit
expires after the 2025 return.

The published IRS example has $20,000 of final adoption expenses and a
$10,000 nonrefundable tax limit. It produces a $5,000 refund credit, a
$10,000 nonrefundable credit and $2,280 carried forward. The fixture also
checks finalization timing, multiple children, phaseout endpoints, foreign
prior expenses and zero-outlay special-needs eligibility.

Employer-provided adoption benefits, missing-TIN statements and expense-age
exceptions requiring additional evidence remain blocked.

Sources: [2025 Form 8839](https://www.irs.gov/pub/irs-prior/f8839--2025.pdf),
[2025 Form 8839 instructions](https://www.irs.gov/pub/irs-prior/i8839--2025.pdf).

## Residential energy credits

Form 5695 separates the 30% residential clean energy credit, including
qualified fuel-cell capacity limits and verified carryovers, from the energy
efficient home improvement credit. The latter has the $1,200 ordinary annual
cap and a separate $2,000 heat-pump/biomass cap. Doors, windows, equipment and
audits have the category limits printed on the official form. Specified 2025
property requires actual QMID and manufacturer eligibility records.

Only clean energy credit carries forward. A tax-limited unused home improvement
credit is reported as unused and does not become a carryforward. Joint
occupancy, business/condominium allocation and multi-year enabling-property
cases remain blocked. Net qualified costs must exclude rebates and subsidies;
building-envelope costs exclude installation labor.

Credit ordering follows Schedule 8812 Credit Limit Worksheets A and B. The
home improvement credit precedes CTC. Adoption and clean energy use the
Worksheet B reservation for CTC that cannot be refunded as ACTC. One literal
integrated example, MFJ $100,000 wages with two eligible children, produces
$3,200 home improvement credit, $3,546 clean energy credit, $1,000 CTC,
$3,400 ACTC and $2,454 clean energy carry-out. It checks actual amounts on the
integrated Form 1040, not only the individual module.

Sources: [2025 Form 5695](https://www.irs.gov/pub/irs-prior/f5695--2025.pdf),
[2025 instructions](https://www.irs.gov/pub/irs-prior/i5695--2025.pdf),
[2025 Schedule 8812 instructions](https://www.irs.gov/pub/irs-prior/i1040s8--2025.pdf).

## Foreign tax credit

The qualified-payee simplified election supports the $300 individual / $600
joint limit with actual passive income and creditable-tax confirmations. It
uses the smaller of eligible foreign tax and regular US tax.

The separate ordinary passive Form 1116 route computes per-country gross
income, standard deduction allocation, foreign taxable income, the limitation
denominator and the credit limit. Foreign income must already be included
once in the main 1099-INT/DIV totals. This route is restricted to ordinary
interest/dividends with standard deduction and no preferential-rate, AMT,
business, rental, capital-loss or adjustment allocation complication.
High-tax kickout, foreign losses, treaty resourcing, non-passive categories,
carryovers/redeterminations and foreign taxes deducted elsewhere remain
blocked. Unused current tax is reported as requiring carryback/carryover
review; it is not claimed automatically in another year.

Sources: [2025 Form 1116](https://www.irs.gov/pub/irs-prior/f1116--2025.pdf),
[2025 Form 1116 instructions](https://www.irs.gov/pub/irs-prior/i1116--2025.pdf).

## Estimated-tax penalty

Form 2210 regular installments use current tax after the refundable credits
specified by the instructions, the $1,000 exception, the prior full-year tax
safe harbor and the 110% higher-income rule. Dated estimated payments must
reconcile the recorded annual payments. Withholding can use the default four
equal installments or actual dated records. The prior-year overpayment uses
April 15 or its actual later origin date. June 16, 2025 payments receive the
official weekend deadline treatment.

The payment ledger applies funds to the earliest unpaid installment. Interest
is computed on the unpaid balance, through the payment date or April 15,
2026, with the four official periods and their 7% annual rates / 365 days.
Form 2210 Example 3 gives a $204 rounded penalty; the fixture verifies its
required installments, underpayments and dated repayments. Further cases
check partial-year delays, actual front/back-loaded withholding, annual
safe-harbor withholding and the zero-prior-tax exception.

Requested Schedule AI, disaster/waiver/farmer and early-filing exceptions
remain explicit blocks. Form 1040 line 38 is separate from line 37. The
result includes `payment_summary` so the amount including penalty and a
possible refund offset can be reviewed without changing the original line 37.

Sources: [2025 Form 2210](https://www.irs.gov/pub/irs-prior/f2210--2025.pdf),
[2025 Form 2210 instructions](https://www.irs.gov/pub/irs-prior/i2210--2025.pdf).

## Source and input evidence

`docs/longtail_sources_2025.json` records the downloaded official document URLs,
byte counts and SHA-256 hashes. The underlying PDFs stay in the private source
evidence folder. UI modules and row templates are published in the calculation
schema; the desktop and offline worker use the same pure-Python functions.

K-1/entity income remains blocked. A K-1 box amount alone does not supply
partner/shareholder basis, at-risk and passive-loss records, distribution
character, section 199A details or the self-employment allocation. These would
change taxable income and carryovers and cannot be replaced by a generic
income entry or guessed allocation.
