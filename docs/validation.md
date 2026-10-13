# Independent validation for US federal tax year 2025

This is an independently authored, synthetic whole-return acceptance suite for Tax Reborn. It is not a comparison with a licensed TurboTax session, an IRS certification, or a check of electronic filing. No taxpayer data or vendor material is included.

The original70-check baseline and its source identity remain documented below. A later extension phase adds IRA/HSA/education/Marketplace calculations and selected EITC/NIIT/AMT/rental worksheets. The latest independently executed full backend regression is **264 passing tests at2026-10-13 05:12 UTC**, not a claim of264 product orUI features. See the current extension result at the end and [credit-module evidence](CREDIT_MODULES.md).


## Oracle provenance and freeze

The oracle was frozen at **2026-10-13T03:44:07.452519+00:00**, before importing or running `tax_engine.calculate_return`. The exact fixture SHA-256 is `bc6401f56c0b9ae7572908a23c6b5159c809723dde4ef9a0ae02c55c905e7d15`. `tests/test_acceptance.py` checks that hash before importing the engine. Do not revise expected numbers to follow engine output. Any correction must identify the original arithmetic or source error and preserve a before/after record.

The acceptance author read only the project contract and the literal `default_return()` shape for input compatibility. Expected amounts are literal Form 1040 whole-dollar values from manual arithmetic, the official 2025 Tax Table, and official worksheets. No product rule table, product demonstration output, or product calculation was used as an oracle. Each of the 22 returns compares all 48 contract fields, including zeros, summary values and selected schedule intermediates. There are 44 separate declared/automatic scope and invalid-input probes, plus one fixture-integrity test: the original suite had 67 unittest cases. Three subsequent qualification/classification checks bring the current suite to 70. Counts describe checks, not distinct product features.

All amounts below are US dollars for tax year 2025. The 47 computed worksheet fields are compared with explicit zeros where applicable. Field38 is a contract placeholder marked not computed; its zero does not establish zero estimated-tax penalty.

| Held-out case | AGI | Taxable income | Total federal tax | Refund | Owed |
|---|---:|---:|---:|---:|---:|
| single_w2 | 60,000 | 44,250 | 5,075 | 1,425 | 0 |
| w2_aggregate_rounding_boundary | 20,050 | 4,300 | 433 | 568 | 0 |
| mfj_ctc_qualified_dividends | 90,375 | 58,875 | 2,176 | 6,824 | 0 |
| mfj_additional_child_tax_credit | 53,000 | 21,500 | 0 | 2,747 | 0 |
| itemized_and_qualified_capital_gains | 122,000 | 89,150 | 12,377 | 0 | 2,377 |
| schedule_c_se_qbi | 46,467 | 24,574 | 9,776 | 224 | 0 |
| senior_social_security | 44,000 | 20,250 | 2,195 | 805 | 0 |
| single_senior_phaseout | 100,000 | 77,750 | 12,025 | 0 | 25 |
| mfj_two_seniors_phaseout_each | 160,000 | 114,500 | 15,018 | 982 | 0 |
| ctc_phaseout_200001 | 200,001 | 184,251 | 34,917 | 5,083 | 0 |
| table_99999 | 115,749 | 99,999 | 16,909 | 91 | 0 |
| computation_100000 | 115,750 | 100,000 | 16,914 | 86 | 0 |
| dependent_age_16 | 60,000 | 44,250 | 2,875 | 3,625 | 0 |
| dependent_age_17 | 60,000 | 44,250 | 4,575 | 1,925 | 0 |
| salt_40000_cap | 90,000 | 50,000 | 5,920 | 1,080 | 0 |
| capital_gain_zero_fifteen_stack | 70,000 | 54,250 | 4,760 | 240 | 0 |
| capital_loss_current_limit | 57,000 | 41,250 | 4,715 | 1,785 | 0 |
| mfj_additional_medicare_withheld | 300,000 | 268,500 | 50,584 | 2,316 | 0 |
| irs_mfj_25300_example_extended | 56,800 | 25,300 | 2,562 | 438 | 0 |
| mfs_spouse_itemizes | 60,000 | 60,000 | 8,120 | 0 | 1,620 |
| qualifying_surviving_spouse_child | 56,800 | 25,300 | 362 | 2,638 | 0 |
| head_of_household_child | 52,000 | 28,375 | 865 | 3,135 | 0 |

## Source receipts

Official IRS pages were checked in the browser and downloaded separately for provenance on 2026-10-13. HTML source hashes describe the retrieved page, not a promise that the IRS will keep a live URL byte-identical. Pinned PDF links identify tax year 2025. Source snapshots are retained in the private research workspace; the public fixture includes URL, timestamp, hash and size.

| Official source | Retrieved UTC | SHA-256 |
|---|---|---|
| [i1040gi_2025.html](https://www.irs.gov/instructions/i1040gi) | 2026-10-13T03:38:29.185478+00:00 | `d7df4e7826cf6d8ba95fca8f88512bde1fb332f848cdb65ae045515f7fe47de6` |
| [p1040_2025.html](https://www.irs.gov/publications/p1040) | 2026-10-13T03:38:29.180088+00:00 | `83174f37b76e34f6ba5d4ceb7193119899409fcd8c192e5a259771ece86d70ec` |
| [i1040sca_2025.html](https://www.irs.gov/instructions/i1040sca) | 2026-10-13T03:38:28.958893+00:00 | `b44e41320e26321901e29c81b4153a940d08651d65d9ddf986b7265cd1d8dd6d` |
| [p554_2025.html](https://www.irs.gov/publications/p554) | 2026-10-13T03:38:28.928461+00:00 | `56c09fe0dcd13f214436e9dfefd0c0dcbea21f22d0e6e8b3f8cc94d686d71c43` |
| [f1040sse_2025.pdf](https://www.irs.gov/pub/irs-prior/f1040sse--2025.pdf) | 2026-10-13T03:38:28.788323+00:00 | `05bc2b3e1dfca65d8c6fc6d652af4fa3736e953c6575d6e9f82590484677d347` |
| [f1040s1a_2025.pdf](https://www.irs.gov/pub/irs-prior/f1040s1a--2025.pdf) | 2026-10-13T03:38:29.865884+00:00 | `64f97b38ff4218e2f188fd55a8aab7043556687487c82bbefe0b6dd1a956ecd4` |
| [f1040s8_2025.pdf](https://www.irs.gov/pub/irs-prior/f1040s8--2025.pdf) | 2026-10-13T03:38:30.016214+00:00 | `6936462d67e2309d14a795aa0b88ef613cc6d79617431cfda3a2edf44aea52db` |
| [f8995_2025.pdf](https://www.irs.gov/pub/irs-prior/f8995--2025.pdf) | 2026-10-13T03:38:30.007506+00:00 | `55380ad230303e1586ce97f0f224265b8337ad18c9204f0fb7325e95a76b5cde` |
| [f8959_2025.pdf](https://www.irs.gov/pub/irs-prior/f8959--2025.pdf) | 2026-10-13T03:38:30.189267+00:00 | `13e64004948331d2b708c80b1b664bf69675028edd0b84f2de6e3ca9afaa996d` |
| [i8995_2025.html](https://www.irs.gov/instructions/i8995) | 2026-10-13T03:38:30.455526+00:00 | `45b18b75c03693e803cf34a303f8e780d86f1cd22c87af71079ba72055d2f280` |

## High-value manual checks

- Two W-2 values are added with cents before rounding the Form 1040 line. The deliberately selected values move taxable income from the wrong $4,299 to the correct $4,300 and change the table tax by $5.
- The official IRS married-filing-jointly worked Tax Table example gives taxable income $25,300 and tax $2,562. The fixture extends this table lookup into a synthetic full return; the IRS did not supply the other synthetic inputs.
- The $50,000 Schedule C profit case independently derives Schedule SE 4a $46,175; Social Security tax $5,726; Medicare tax $1,339; total $7,065; deductible half $3,533. QBI is limited by taxable income to $6,143, not its larger business-income component.
- The qualified-dividend and capital-gain cases separately test the ordinary Tax Table lookup, 0%/15% stacking, and the worksheet comparison with tax on all ordinary taxable income.
- The two-senior MFJ case reduces each person’s $6,000 deduction by $600, yielding $10,800. Applying one household reduction to $12,000 would be wrong.
- The ACTC case has $13,000 investment income, which exceeds the official 2025 $11,950 EITC limit; no applicable EITC is silently omitted from that supported oracle.
- The Additional Medicare case supplies actual W-2 Box 6. It checks both the $450 additional tax and the $900 additional withholding credited to line 25c.
- The $99,999/$100,000 taxable-income pair changes from the required Tax Table to the Tax Computation Worksheet. The adjacent expected taxes are $16,909 and $16,914.
- Filing-status, dependency, itemized-expense and business qualifications are explicit synthetic assertions. Their absence is tested separately. State/local tax deduction is a federal Schedule A calculation; it is not a state return.

## Reproduction

From the delivery directory, run:

```sh
python3 -m unittest discover -s tests -p test_acceptance.py -v
```

Tests also run from another working directory because paths resolve from the test file. They require the local Python engine, the frozen fixture, and Python’s standard library. They do not use the network during a run.

## Execution status

The initial independent run completed at **2026-10-13 03:46:07 UTC**: **67 tests passed**, no arithmetic differences in the 22 held-out returns. The tested engine SHA-256 was `37f352504b76021383bdd04e33ea3244f2e160548d1ae6f077e2e722bcf5ea74`. Initial run output is preserved in the private research workspace. This is a timestamped result for that engine version, not a claim that later source changes were already tested. A passing backend suite does not validate browser, desktop, mobile, persistence, print/export or original TurboTax interaction. Those require separate evidence from the integration owner.

## Historical baseline scope gaps (03:53 UTC)

The probes require explicit blocking for NIIT, general AMT/ISO, Marketplace/ACA, education credits, foreign income/foreign tax credit, state returns, passive rentals, special 28%/25% gains, prior-year capital/QBI/charity carry-ins, Form 4952 investment-interest limitations, IRA/HSA deduction eligibility, SSA lump-sum/repayment elections, and unverified basic qualifications. They also reject unknown input keys, unsupported years/statuses, nonfinite or binary-float money, and truthy string acknowledgments.

These cases establish selected calculations and rejection boundaries only. They do not cover every tax credit, form, election, recapture, filing-status exception, split-dependent situation, disaster adjustment, treaty, fiscal-year or amended return. The supported goldens do not include an applicable EITC, NIIT or AMT liability. General completeness still depends on the intake flow obtaining all relevant income, deductions, prior-year facts and unsupported situations. The UI must not convert a taxpayer’s failure to disclose a situation into a claim that its tax is zero.

## Historical baseline scope audit

The original 22 oracles remain frozen and unchanged. Subsequent source inspection identified an input-classification gap for nonqualified commercial annuities. IRS [2025 Form8960 instructions](https://www.irs.gov/instructions/i8960), Line3—Annuities, distinguish exempt qualified-plan distributions from ordinary commercial annuities. Form1099-R Box7 CodeD identifies the taxable amount to include in NIIT income.

A separately saved synthetic probe reproduced the gap at 2026-10-13T03:50:18.848579+00:00 against engine `27086fd7453354a7342428b2e996302a06767c23736bcf07604c0cd5cc009ff8`: Single age67, W2 $200,000, commercial annuity taxable $100,000, all existing qualification flags true. The current shape could not encode a structured pension/annuity distinction. It returned `can_prepare=true`, AGI $300,000, tax $68,335 and net-investment-income screen $0. With no allocable deductions, NIIT would be `min(100000,300000-200000)*3.8%=3800`; an unsupported return must be blocked. The integration and core owners were notified. The supported pension goldens represent domestic qualified-plan distributions; a general claim to support every1099-R is unwarranted. Core added `retirement.qualified_plan_confirmed`, default false, and requires it for any nonzero pension. At the baseline the nonqualified commercial-annuity probe blocked, and both supported qualified-pension cases require the explicit qualification. The final independent retest below verifies this repair. This baseline retest does not claim NIIT computation for annuities; the later structured-annuity extension is described below.

Core subsequently proposed an explicit qualified-dividend holding-period acknowledgment. Root approved an input-only adaptation for the two existing synthetic qualified-dividend cases plus a missing-acknowledgment check. The frozen fixture and all expected amounts remain unchanged. This is a schema qualification change, not a correction to an oracle.

At the 03:53 UTC baseline the AMT trigger was deliberately conservative and was not a Form6251 calculation. The later extension phase below adds actual selected Form6251 worksheets. Ordinary AMT rates applied to preferential gains may block a return whose actual AMT would be zero. A block is not evidence that AMT is owed. General Form2210 estimated-tax penalties remain uncomputed; field38 must stay labeled uncomputed or blank in output and print/PDF.

## Qualification migration and baseline retest

The frozen JSON retains the original input schema for provenance. Directly passing its older qualified-dividend or pension inputs to the current engine produces a required qualification block. The acceptance runner applies only these documented synthetic input confirmations before calculation:

| Case | Input acknowledgment added | Reason |
|---|---|---|
| `mfj_ctc_qualified_dividends` | `eligibility.qualified_dividends_eligible=true` | Payer, holding-period and payment-related tests are assumed satisfied for this synthetic qualified-dividend sample. |
| `itemized_and_qualified_capital_gains` | `eligibility.qualified_dividends_eligible=true` | Same verified synthetic qualification. |
| `senior_social_security` | `retirement.qualified_plan_confirmed=true` | The $20,000 pension is a domestic qualified-plan distribution. |
| `mfj_two_seniors_phaseout_each` | `retirement.qualified_plan_confirmed=true` | The $160,000 pension is a domestic qualified-plan distribution. |

The original blocking tests use the same valid adapted base before applying their adverse condition. This prevents an unrelated new qualification failure from accidentally making a blocking test pass. New tests remove each acknowledgment and require a specific block, then repeat the nonqualified-annuity scope probe. Expected Form1040 amounts are unchanged. The fixture hash remains `bc6401f56c0b9ae7572908a23c6b5159c809723dde4ef9a0ae02c55c905e7d15`.

Baseline independent run: **2026-10-13 03:53:47.761961–03:53:47.830855 UTC**, **70 tests passed**, process exit0. Engine hash immediately before and after the run was identical: `bdb0ae55ba9107c7a403a0945baae8c6e43378a0697c09b3e9f2bf6ec1e73af7`. Acceptance test source SHA-256 was `fef81f0faa5c00c56a2211fa6e7be32cc6f6ac09838b3196a91cce53140d2dda`. Logs and a machine-readable run receipt are saved in the private research workspace; this document records the reproducible command and exact source identity. Later code changes require another run.

`can_prepare=true` means a supported **calculation worksheet** with all required synthetic eligibility confirmations and no detected blocking issue. It does not certify a complete set of IRS forms, eligibility beyond the stated confirmations, a filed return, electronic submission, or TurboTax parity. The existing supported calculations include selected W2/interest/dividend/capital-gain/active-service-business/QBI/qualified-retirement/itemized/CTC/ACTC/AdditionalMedicare situations, not every scenario that can appear on the same form.

At the 03:53 UTC baseline, release boundaries were explicit: general AMT and NIIT were blocked when applicable or detected; nonqualified/foreign/mixed pensions are outside the qualified-pension field; EITC requires review and cannot be waived simply to make a return pass; applicable ACA, education, foreign/state, passive-income, special-gain and carry-in situations remain unsupported. Form2210 penalties are uncomputed even when the worksheet otherwise passes. Native TurboTax behavior, desktop/mobile interactions, local persistence and exported form fidelity require their own integration evidence. This suite is independent IRS-rules validation, not commercial-vendor parity.

The same70 checks also passed when executing the test file by absolute path from a separate working directory, confirming the documented path resolution. The external-directory run log is retained with the research receipts.

## First extension snapshot — independently executed 04:42 UTC

The independent acceptance author implemented four isolated functions in `tax_credits.py` with official2025 IRA, HSA8889, education8863 and Marketplace8962 rules. The separate [credit-module evidence](CREDIT_MODULES.md) records28 frozen expected cases,21 scope guards, boundary/qualification tests,9 literal whole-return integration checks, source receipts and unresolved special worksheets. Original22-return golden bytes and expected values remain unchanged.

The integration owner separately added EITC using the official2025 table, ordinary NIIT with a structured commercial-annuity field, selected Form6251 regular/preferential AMT, ordinary passive real-estate rental loss netting/allowance/carryout, and Form4952 ordinary investment-interest limits. Those extension tests are core-authored; this independent report does not reclassify them as held-out vendor comparisons.

Independent audit and integration review checked deduction order beforeSSA/AGI, finalAGI foreducation/PTC, education capacity beforeCTC, PTC repayment on17/refund on31, HSA20%/6% tax on23, and mixed1099 withholding aggregation before rounding. Review also required the actual transaction-date HSA65 exception, actual married-spouse HSA coverage, explicit distribution/excess-correction qualification, and rejection of ordinary positiveW2 wages with zero/default MedicareBox5. Broader core checks cover childSSN exclusion from the EIC child count, ACTC three-child alternative subtraction ofEIC/excessSS, AMT preferential-rate stacking and verified passive carryover character.

Final independently executed full-suite result: **2026-10-13T04:42:32.934405–04:42:33.046825 UTC**, **176 passed**, exit0. Counts are70 original independent acceptance +70 new independentcredit +13 core +23 extension. Source/fixture hashes immediately before and after the run matched. [Machine-readable receipt](credit_validation_20261013.json):

| Source | SHA256 |
|---|---|
|`tax_engine.py`|`22e00289c7c9079a485d59907620958b8791155f997563da0562f6e46db63eaf`|
|`tax_extended.py`|`63b060088c2ad98c860e6d463a9b9bf33f080bf47e76cd18e962efc1a28daeb0`|
|`tax_credits.py`|`887f95f1b7910214c0afd3ddfb6a8e7548bff9d62df876a0e4a400996668d7e2`|
|`rules_2025.json`|`7ee6b794b8b633c9736a5a160fe4c0512346562025bbbb9d0261a45aa72fd544`|
|Original golden|`bc6401f56c0b9ae7572908a23c6b5159c809723dde4ef9a0ae02c55c905e7d15`|
|Credit golden|`e5a68f152b820f69a4455ce8b34a17ecc094b594018bfb29c6c1f497aff73629`|

Current limitations remain explicit. Foreign/nonresident/part-year situations, special28%/1250 gain worksheets, Form8995A above the simplified threshold, capital/QBI/charity carry-ins, several family/energy/adoption credits, IRA/SSA integrated worksheets, HSA prior-excess/testing failures, PTC shared-policy/marriage/HRA/SE-health iteration, new-asset depreciation, rental disposal/REP/personal use, AMT carryover/8801 and Form2210 penalties are not completed. A submitted unsupported situation blocks; a qualification confirmation is an input assertion, not proof that all undisclosed facts were detected. Native commercial-software parity and completed signed/e-file packets remain unverified. State, desktop/mobile, persistence, OCR, WASM and exports have separate integration owners and must use their own receipts.

## Second extension and classification snapshot — 05:07 UTC

The independent author separately froze Form2441/8880/ScheduleR facts and expected values before executing the new module. [Additional-credit validation](ADDITIONAL_CREDITS_VALIDATION.md) records30 manual module cases,5 whole-input selected-line oracles,20 declared/scope guards and subsequent source-boundary tests. The current dedicated suite has66 tests. Its fixture remains `1f093ac6b39e47fce4314cb1cd6f2317a45e7b1181668fab5ee3d40613c242ef`.

Source review found and repaired three material cross-input issues. Education tuition and materials must be added with cents before rounding the same Form8863 expense line; two literal tests reproduced a$1 credit error and now pass. Positive care expenses cannot be accepted with no provider rows or empty provider identity merely because a confirmation checkbox is set. Known eligible IRA contributions with possible Saver credit and available tax capacity now require completion of the Saver module, rather than silently leaving the credit at zero.

A further independent actual probe exposed a disability-income classification error. A50-year-old with$15,000 employer disability pension before the employer’s minimum retirement age, no children and otherwise qualified EIC facts could enter the pension on5b and obtain `can_prepare=true`,EIC zero. Official1040 instructions and Pub596 require this income on1h as EIC earned income; the published2025 table gives$312. Separate structured disability1099-R inputs now enter `additional_lines.1h`/`1z`, eligible care/EIC/CTC earned income and total income. They exclude FICA/SE and are not automatically treated as IRA-eligible personal-service compensation. Regular pension fields retain income after minimum retirement age. ScheduleR’s separate mandatory-retirement-age test remains distinct.

The new disability fixture was frozen before implementation of its new input fields: `d493ad75a46af2ccf4ea489b6226896f90212bea8498b48f0a722a340e41188c`. Three literal whole-input selected-line cases independently expect$312 refund,$425 refund,and$223 owed; they pass. Seven further checks cover source identity, missing qualification, invalid taxable/gross amounts and after-minimum classification. The adapter adds the verified synthetic early-distribution exception for these employer-plan disability cases; no expected tax/refund amount changed. The initial run correctly blocked without that acknowledgment, and both the failed run and the explicit qualification correction are preserved privately.

Final independent full regression: **2026-10-13T05:07:02.924867–05:07:03.074002 UTC**, **261 tests passed**, exit0. All13 tracked source/test/fixture hashes matched before and after the run. Of261,218 are independently authored acceptance checks:70 original,72 IRA/HSA/education/PTC,66 care/Saver/R and10 disability. The remaining43 are13 core,23 extended and7 additional-module checks written by the core owner. These counts are tests, not product features or commercially verified return types.

| Final tracked calculation source | SHA256 |
|---|---|
|`tax_engine.py`|`8cfacbbd5239cb87139e1c4b61025ef3e363676219502ba26be9862d3b6afeb5`|
|`tax_extended.py`|`63b060088c2ad98c860e6d463a9b9bf33f080bf47e76cd18e962efc1a28daeb0`|
|`tax_credits.py`|`a57cad57ff2b30848cd538e73bd4c9ee8e22e1b106bbb3f93e077ca8b73a3786`|
|`tax_additional.py`|`6b9d2e36964163bb4e0868387286136d09d82ff64b897733e6e24fa7bedbe8c5`|
|`rules_2025.json`|`796652f6627aecc912775fa1712dbaa1a6725363593da19ebd896b558233c7ac`|

The [final machine-readable receipt](validation_20261013T050702Z.json) records exact commands, times, counts and all fixture hashes. The earlier04:42/05:05 receipts remain historical evidence. New source changes require retesting.

The scope remains a set of supported federal calculations and workpapers. Remaining specialist boundaries include Form8995A/complexQBI, capital/special-rate and several prior-year carryovers, IRA/SSA/distribution basis interactions, HSA prior-excess/testing failures, Marketplace shared-policy/marriage/HRA/SE-health iteration, household employee ScheduleH, prior-year care WorksheetA, retirement-credit nonjoint distribution-year allocation, foreign/nonresident returns, new-asset depreciation/complex rental disposal, numerous other family/energy/adoption credits, AMT credit/carryovers and Form2210 penalties. These are not claimed complete. NativeTurboTax parity, complete signed/e-file packets, desktop/mobile, OCR, persistence, PDF/WASM and state-return validation require their own actual integration receipts. This independent tax audit used no taxpayer financial data and no commercial-vendor outputs as goldens.

## Final distribution and qualification retest — 05:12 UTC

One subsequent concrete cross-module omission was corrected: qualified employer-plan disability1099-R gross must also count in the Form8880 distribution window. A synthetic$5,000W2+$15,000 disability income+$2,000 IRA return with the Saver module enabled but no declared distributions now blocks. Entering the actual$15,000 distribution reduces the Saver contribution base to zero. Its earned income is$20,000, above the2025Single/no-child EIC$19,104 limit even though IRA deductions reduceAGI to$18,000; the possible-EIC review screen now checks both limits. No generic ineligible-review bypass was added.

Classified disability now also requires the existing explicit qualified-US-plan confirmation. The test adapter records this already stated synthetic plan fact, without changing any frozen expected amount. A separate missing-plan-confirmation check verifies blocking. The dedicated disability suite now has12 tests; the other independent suites remain70/72/66.

The last independently executed full run was **2026-10-13T05:12:52.586188–05:12:52.734291 UTC**: **264 tests passed**, exit0, all13 tracked source/test/fixture hashes identical before and after. There are220 independently authored acceptance checks and44 core-authored checks; these are test counts, not features. CurrentengineSHA256 is `bcc299054e700efc2db9339f032facc5caea9be770052309b4fa5ee77142f5a3`; creditsSHA remains `a57cad57ff2b30848cd538e73bd4c9ee8e22e1b106bbb3f93e077ca8b73a3786`. The [current final receipt](final_validation_20261013.json) holds the exact complete source identities and counts. The [05:07 receipt](validation_20261013T050702Z.json) is preserved as historical evidence. All four frozen fixtures remain unchanged. The stated specialist, device, filing-packet and commercial-parity limits continue to apply.
