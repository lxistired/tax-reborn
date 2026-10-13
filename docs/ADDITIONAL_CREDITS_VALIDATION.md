# Independent 2025 dependent-care, Saver and elderly/disability credit validation

The engine now implements selected Form 2441, Form 8880 and ScheduleR calculations. This document records independent synthetic expected amounts and rejection tests. It does not establish commercial-vendor parity, a complete signed filing packet or electronic filing.

## Oracle freeze and independent method

The acceptance author read official 2025 IRS forms and instructions, then saved literal manual arithmetic before importing or calling the new calculation functions. The fixture contains **30 module cases**, **5 complete-return partial-line oracles**, and **20 qualification/scope guards**. The literal module cases compare payable nonrefundable credits, and where relevant taxable dependent-care benefits; additional checks test whole-dollar integer outputs, input immutability, tax-capacity limits and primary-source traces.

First freeze: **2026-10-13T04:48:31.439139+00:00**. Before execution, three additional whole-return cases and the guard-purpose list were added at **2026-10-13T04:49:22.871783+00:00**. The original 30 module amounts and two earlier whole-return amounts remained unchanged. Final fixtureSHA256: `1f093ac6b39e47fce4314cb1cd6f2317a45e7b1181668fab5ee3d40613c242ef`. Its previous snapshotSHA is recorded in the fixture. Neither earlier frozen fixture was edited.

Input adapters use only the new default schema to encode the stated synthetic facts. They use eligible providers, valid identities, verified expenses/coverage and declared distribution history. Expected tax amounts are never read from product demonstrations, rule tables or execution outputs. The initial whole-return adapter produced excess decimal places in synthetic payroll fields and put the cash-charity acknowledgment in the wrong section. The adapter now formats payroll dollars to two decimals and places `charity_cash_only` in `itemized`. Expected values were unchanged. Failed logs remain retained privately.

## Manually calculated checks

All dollar values below are tax year 2025 USD.

| Form and synthetic situation | Independent expected calculation |
|---|---|
|2441, one qualifying child,AGI$15,000,$4,500 gross care|$3,000 base×35%=$1,050. AtAGI$15,001 the rate is34% and credit$1,020.|
|2441, one child,AGI$43,000/$43,001|$3,000×21%=$630; next dollar moves to20%=$600.|
|2441,MFJ,two people,$8,000 expenses,spouse earnings$2,000|The smaller of$6,000/$30,000/$2,000 is$2,000;20% gives$400.|
|2441,two people,$10,000 gross care,$5,000FSA exclusion|Remaining$6,000 expense ceiling is$1,000;20% credit$200.|
|2441,one child,$5,000 benefits,$4,000 incurred expenses|Exclusion$4,000,taxable benefits$1,000,no remaining credit ceiling.|
|2441,two people,$5,000 benefits,spouse earnings$3,000,$6,000 care|Exclusion$3,000,taxable benefits$2,000,credit base$3,000 and20% credit$600.|
|2441,nonworking full-time-student spouse,one child,5verified months|Deemed earnings$250/month×5=$1,250;20% credit$250.|
|8880,Single,$2,000 contribution|AGI$23,750 gives$1,000;23,751 gives$400;25,500 gives$400;25,501 gives$200;39,500 gives$200;39,501 gives zero.|
|8880,MFJ,$2,000 each|AGI$47,500 gives$2,000;47,501 gives$800;51,001 gives$400.|
|8880,QSS,AGI$30,000,$2,000 contribution|QSS uses theSingle/MFS table column:10%=$200.|
|8880,MFJ,$2,000 each,$100+$400 distributions|Assuming joint returns for both distribution years,$500 reduces both columns;$1,500+$1,500 at50% gives$1,500.|
|ScheduleR,Single65+,AGI$10,000,nontaxableSSA$1,000|$5,000−$1,000−half($10,000−$7,500)=$2,750;15%=$412.50→$413.|
|ScheduleR,MFJ both65+,AGI$18,000,nontaxableSSA$2,000|$7,500−$2,000−half($18,000−$10,000)=$1,500;15%=$225.|
|ScheduleR,Single under65,qualifying taxable disability$3,000,AGI$10,000|Initial base capped at$3,000;subtract$1,250;15%=$262.50→$263.|

The five main return cases establish the actual credit order and output-line mapping:

| Synthetic return | Key independent expected result |
|---|---|
|Single$60,000W2,$6,500withholding,eligible child and care|Tabletax$5,075−care$600−CTC$2,200=tax$2,275;refund$4,225.|
|Same return plus$4,000 eligibleAOTC expenses|Nonrefundablecare/education$2,100;CTC$2,200;tax$775;payments$7,500including refundableAOTC$1,000;refund$6,725.|
|Single$30,000W2,$2,000withholding,$2,000 eligible employer-plan savings|Taxableincome$14,250;officialtabletax$1,475;Saver$200;tax$1,275;refund$725.|
|Single$30,000W2,$7,000 deductibleIRA,$2,000withholding|AGI$23,000;taxableincome$7,250;officialtabletax$728;50%-rateSaver tentative$1,000 limited to$728;tax zero;refund$2,000.|
|Single65+,taxableinterest$10,000,SSA$1,000,$100 forced itemized charity and$6,000 senior deduction|Taxableincome$3,900;officialtabletax$393;ScheduleR tentative$413 capped at$393;tax zero;refund$500withholding.|

These are five full synthetic inputs with exact selected1040 line expectations. They do not compare every48 field, unlike the original 22 whole-return oracle suite. The wording deliberately distinguishes the two levels of evidence.

## Qualifications and special worksheets

Form 2441 requires actual provider records plus work-related expenses, qualifying-person/residency/TIN facts and no duplicate benefit. Gross qualified expenses include FSA payments; the engine subtracts excluded benefits exactly once. The married-income limit is per spouse. Student/disability deemed income uses12 verified monthly actual records and the250/500 monthly floor; only one spouse can receive deemed earnings in a month. An age13 child requires expenses from before the birthday or qualifying disability. Household employees require unimplemented ScheduleH and block. Prior-year expenses/FSA carry-in, self-employed benefit programs and missing-provider-TIN due-diligence statements require separate worksheets and block.

Form 8880 verifies eligible contribution types, age, dependency and full-time-student status. Its distribution window spans after 2022 through the2025 return’s filing due date including extensions. The simplified MFJ pooling blocks if a relevant distribution year was not jointly filed. Known current-year qualifying-plan/IRA amounts must be included or explicitly classified under formal exclusions. Credit capacity is calculated after care, elderly/disability and education credits; it does not reduce Social Security or Medicare taxes.

ScheduleR verifies age or permanent-total disability retirement, taxable disability before mandatory retirement age, a physician’s statement and all applicable nontaxable pension/benefit amounts. The claimed taxable disability amount cannot exceed taxable income actually included in the return. MFS requires spouses to have lived apart for the entire year. The nonrefundable credit is constrained by remaining income-tax capacity.

Independent review found that a provider-identity acknowledgment could originally replace an empty provider list or a row with empty identity fields. Two saved failing tests proved `can_compute=true`; the core now blocks those cases. A follow-up invalid-type test requires `ValueError` rather than an uncaught string-method exception. Additional independent rounding checks verify householdW2Box10$1,000.49+$1,000.49→2441line12$2,001;with$1,500 excluded benefits the taxable1040line1e is$501 andAGI$90,501.

## Sources and receipts

The independent author used [2025 Form 2441](https://www.irs.gov/pub/irs-prior/f2441--2025.pdf), [2441 instructions](https://www.irs.gov/instructions/i2441), [2025 Form 8880 and its instructions](https://www.irs.gov/pub/irs-prior/f8880--2025.pdf), [2025 ScheduleR](https://www.irs.gov/pub/irs-prior/f1040sr--2025.pdf), [ScheduleR instructions](https://www.irs.gov/instructions/i1040sr) and the [2025 Tax Table](https://www.irs.gov/publications/p1040). No runtime network is required. PDF snapshots are retained in private research storage; the source directory contains independent synthetic fixtures and metadata.

| Snapshot | Retrieved UTC | SHA256 |
|---|---|---|
| [f2441_2025.pdf](https://www.irs.gov/pub/irs-prior/f2441--2025.pdf) | 2026-10-13T04:46:38.979206+00:00 | `6c3c2d19163fa4c4de829abf9a89b43f08b4f4f3cb169740fc7da43e914269ce` |
| [f8880_2025.pdf](https://www.irs.gov/pub/irs-prior/f8880--2025.pdf) | 2026-10-13T04:46:40.648767+00:00 | `ba2b28770bc82d318ab0b884e56a572771030ce1a3ec80d85bafd2eea3a2778e` |
| [f1040sr_2025.pdf](https://www.irs.gov/pub/irs-prior/f1040sr--2025.pdf) | 2026-10-13T04:46:42.840452+00:00 | `9b1acf56189a88a347d38936e0792552f7466040494b73bf779af17734620b79` |
| [i2441_2025.pdf](https://www.irs.gov/pub/irs-prior/i2441--2025.pdf) | 2026-10-13T04:46:45.896722+00:00 | `86f0669e78b1dc00bfb99e956673d4fccee9e40d6c44d53623dd08e62567fd39` |
| [i1040sr_2025.pdf](https://www.irs.gov/pub/irs-prior/i1040sr--2025.pdf) | 2026-10-13T04:46:47.589679+00:00 | `7194fa66613b2ea28fa9ed67992cc06178892b7eb461013574ea1fb239f3ff3e` |

## Reproduction and evidence boundary

From the delivery directory:

```sh
python3 -m unittest discover -s tests -p test_additional_acceptance.py -v
python3 -m unittest discover -s tests -v
```

Final dated execution and exact source identities are recorded in the current extension section of [validation.md](validation.md). These backend checks do not establish desktop/mobile, OCR, persistence, exported IRS packet fidelity, WASM execution, state-return support or licensedTurboTax parity. Those results must have separate actual integration receipts.

## 05:07 snapshot and disability classification repair

The final independently executed full suite ran**2026-10-13T05:07:02.924867–05:07:03.074002 UTC**: **261 tests passed**, exit0, all13 tracked hashes stable. The dedicated care/Saver/R suite has**66 tests**; a separate disability suite has**10**. Source identities and counts are in the [final receipt](validation_20261013T050702Z.json). CoreSHA256 is `8cfacbbd5239cb87139e1c4b61025ef3e363676219502ba26be9862d3b6afeb5`; additional-moduleSHA256 is `6b9d2e36964163bb4e0868387286136d09d82ff64b897733e6e24fa7bedbe8c5`.

A real cross-module probe found that taxable disability1099-R before the employer’s minimum retirement age could be misclassified as regularpension5b, silently omitting$312 EIC on a$15,000 single-age50 return. The [1040 instructions](https://www.irs.gov/instructions/i1040gi) require1h classification, and [Pub596](https://www.irs.gov/publications/p596) treats these benefits as EIC earned income until minimum retirement age. The new structured inputs now compute1h/1z and relevant credits while excluding FICA/SE. They require verified source amounts, minimum-retirement-age timing and the applicable early-distribution exception. IRA compensation is not inferred merely from the EIC earned-income classification. Regularpension after minimum age remains5b; ScheduleR’s mandatory retirement age is a separate eligibility fact.

Three new literal scenarios, recorded before the new input implementation, return$312,$425 and$223 owed respectively; all pass. The high-wage case combines$230,000 actual Medicare wages with$30,000 disability1h; AdditionalMedicare tax remains$270, proving the disability is not treated as Medicare wages. The frozen fixtureSHA is `d493ad75a46af2ccf4ea489b6226896f90212bea8498b48f0a722a340e41188c`. The input adapter’s early-distribution exception confirmation was documented after an initial qualification block, without changing any expected amount.

A concrete Saver omission review also checks that$30,000 wages+$7,000 IRA with the Saver module disabled cannot be accepted as a completed supported calculation. Completing the actual contribution/distribution/eligibility facts produces the previously frozen$728 credit and zero tax. No generic reviewed-ineligible checkbox bypass was added.

## Final distribution and qualification retest — 05:12 UTC

One subsequent concrete cross-module omission was corrected: qualified employer-plan disability1099-R gross must also count in the Form8880 distribution window. A synthetic$5,000W2+$15,000 disability income+$2,000 IRA return with the Saver module enabled but no declared distributions now blocks. Entering the actual$15,000 distribution reduces the Saver contribution base to zero. Its earned income is$20,000, above the2025Single/no-child EIC$19,104 limit even though IRA deductions reduceAGI to$18,000; the possible-EIC review screen now checks both limits. No generic ineligible-review bypass was added.

Classified disability now also requires the existing explicit qualified-US-plan confirmation. The test adapter records this already stated synthetic plan fact, without changing any frozen expected amount. A separate missing-plan-confirmation check verifies blocking. The dedicated disability suite now has12 tests; the other independent suites remain70/72/66.

The last independently executed full run was **2026-10-13T05:12:52.586188–05:12:52.734291 UTC**: **264 tests passed**, exit0, all13 tracked source/test/fixture hashes identical before and after. There are220 independently authored acceptance checks and44 core-authored checks; these are test counts, not features. CurrentengineSHA256 is `bcc299054e700efc2db9339f032facc5caea9be770052309b4fa5ee77142f5a3`; creditsSHA remains `a57cad57ff2b30848cd538e73bd4c9ee8e22e1b106bbb3f93e077ca8b73a3786`. The [current final receipt](final_validation_20261013.json) holds the exact complete source identities and counts. The [05:07 receipt](validation_20261013T050702Z.json) is preserved as historical evidence. All four frozen fixtures remain unchanged. The stated specialist, device, filing-packet and commercial-parity limits continue to apply.
