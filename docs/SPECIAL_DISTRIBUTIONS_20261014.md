Preview.9 adds actual 1099-DIV special-rate distribution
preparation. This source has been integrated into the App. Native package receipts are recorded separately.

`tax_special_capital.py` independently implements the 2025 IRS Schedule D Tax
Worksheet lines1–47. The engine collects raw Box2a distributions, Box2b
unrecaptured Section1250 gains and Box2d collectibles gains. It sums cents before
rounding each form line. Box2a already includes the two special components, so
the engine does not add them again. The per-payer raw components cannot exceed
Box2a. The rounded worksheet components may exceed their rounded total by $1;
IRS worksheet line12 uses the smaller amount.

The dividend row gains `unrecaptured_1250_gain`, `collectibles_gain`, and
`special_distribution_confirmed`. Existing rows default to zero/false.
Confirmation means the source boxes were checked and there is no QSBS, nominee
or other allocation outside this bounded distribution profile. Securities
trades/losses, capital carryovers, investment-interest deduction/election and
foreign-tax-credit combinations block completion. They retain the entered data.

The engine preserves the existing ordinary/qualified/AMT path for rows without
special amounts. For special distributions, the independently computed ordinary
AMT rate on Form6251 line6 gives a tentative-minimum-tax upper bound: official
PartIII line40 cannot exceed line39. If that upper bound is no more than regular
tax, the AMT liability is proved zero. Otherwise special-rate AMT remains blocked
and its uncomputed worksheet values are omitted. Two of the150 IRS examples
reach that explicit block. All150 regular-tax line16 results match the
independent IRS oracle;148 cases finish supported preparation.

The actual dividend form source in `web/app.js` includes the new money fields,
source confirmation, capital eligibility and a named ScheduleD worksheet.
Host/browser preparation contracts hash the new facts and invalidate review
when a component changes. Default new fields are omitted from fingerprints, so
existing reviewed zero/default rows retain their original hashes. The tested
HTTP/SQLite path saves, reopens and exports the new amounts and clears stale
review flags.

Integration files and hashes are in `SPECIAL_CAPITAL_INTEGRATION_MANIFEST_SAFE.json`.
Use the listed files as a reviewed patch; do not copy the entire work directory.
The source includes staged additions to Android/Desktop module lists, the
browser-worker source list and the HTTP static-source allowlist. Root must
rebuild the generated worker, refresh the offline asset manifest, review any
template/form binding, and test the actual GUI/native packages. Neither generated
worker nor installers were rebuilt in this earlier private staging directory.

Validation:

```sh
python3 -m unittest tests.test_special_dividends tests.test_engine tests.test_acceptance tests.test_extended tests.test_credits tests.test_additional tests.test_additional_acceptance tests.test_longtail tests.test_income_preparation tests.test_income_metadata tests.test_investment_metadata
node tests/check_special_dividend_metadata.cjs
```

The suite passes346 methods, including150 independent IRS raw-distribution
fixtures, rejected combinations, the $1 rounding edge, legacy fingerprints and
real persistence. The separate existing825-case IRS AMT suite also passes. The
expectations and implementation contain no original software bytes, compiled
tables, decompiler text, keys or images.

Primary rules:
[IRS2025 Schedule D instructions](https://www.irs.gov/pub/irs-pdf/i1040sd.pdf),
[continuous-use Form1099-DIV instructions](https://www.irs.gov/pub/irs-pdf/i1099div.pdf),
[IRS2025 Form6251](https://www.irs.gov/pub/irs-pdf/f6251.pdf).

The staged official_forms.py now writes ScheduleD18/19 from actual component
outputs and selects PartIII17Yes/20No for the supported positive distributions.
forms.py includes a complete47line tax workpaper in the actual PDF packet.
The separate42method official-form/paper/preflight suite passes. A synthetic
single mixed-distribution packet has paper_preparation_complete=true after
identity and ScheduleB facts are supplied. Its exported/reopened official
ScheduleD shows18=10000,19=10000 andcorrectcheckboxes; actualForm1040line16=16220.
The physical PDF pages and workpaper were rendered and visually inspected.
Missing identity keeps paper readiness false while arithmetic remains ready.
filing_packet_ready, electronic_filing and transmitted remain false.
