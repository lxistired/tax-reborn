# A saved balance due and an actual paper-payment voucher

Preview.17 adds the official IRS2025 Form1040-V workflow. A supported return with an amount owed must have an explicit payment-method choice before paper preparation is marked complete. Choosing a check or money order adds the full two-page IRS voucher, including the original mailing instructions. Choosing electronic payment does not add a voucher or initiate a payment.

The voucher's printed line3 is the amount actually being sent. The App defaults to Form1040 line37, which excludes the separate line38 estimated-tax penalty. A custom payment amount preserves cents and may differ from the balance due. It does not reduce the calculated balance or create a payment record. The user verifies the amount and method; subsequent UI field edits, record additions/removals and imports clear that confirmation. API callers must submit their own explicit confirmation. Blank, zero, malformed or unconfirmed paper-payment choices remain incomplete. A single check must be less than100million USD.

The voucher retains the taxpayer SSN, joint spouse SSN, legal names and domestic address. Married-filing-separately does not fill the second SSN box. Required identities and address facts remain subject to the existing paper checklist. The included IRS mailing table is retained rather than replacing it with an inferred mailing address.

## Independently expected synthetic results

| Single-filer TY2025 case | Regular tax | AMT | NIIT | Total tax | Withholding | Amount owed |
|---|---:|---:|---:|---:|---:|---:|
| Capital distributions80000, wages5000 |3435|0|0|3435|1000|2435|
| Capital distributions600000, wages5000 |84328|0|15466|99794|1000|98794|
| Capital distributions800000, wages190000 |177290|14773|30096|222159|1000|221159|

All amounts are USD. Each synthetic return includes1000 taxable interest and1000 ordinary dividends and confirms the prior-year-zero-tax estimated-penalty exception. [Fixed independent facts](../fixtures/payment_voucher_2025.json) and the [printed field oracles](../tests/payment_voucher_qa.py) are separate from the renderer. Tests cover a1000.25 partial-payment voucher with an unchanged2435 or221159 amount owed, joint versus separate SSNs, stale paper choice after an income edit, electronic choice and invalid amounts.

The actual HTTP/SQLite flow saves and reopens the return, exports/restores a new backup copy and reads the emitted PDF. The actual pinned Pyodide worker produced six packets, each checked again on the host for canonical fields, page widgets, appearances, two voucher pages and unchanged Form1040 line37. Both full-balance and custom-cents PDFs were rendered and visually inspected. Host577 tests, real Pyodide481 executed tests and the source desktop's19 smoke checks pass. [Source acceptance artifacts](../qa/payment-voucher-20261015/) are synthetic only. Native package installation and GUI acceptance are recorded separately in [candidate17 acceptance](../qa/native-preview17/candidate-acceptance-state.json). The actual Mac bundle passed system PDF save/readback and normal relaunch with its prior9 synthetic returns retained. Its content matches the readonly DMG. Android retained its signer; its119 runtime assets are byte-identical to the already tested package assets, and the changed frontend matches the Mac-tested source. Physical-phone installation/UI remains unverified while USB is absent. Windows passed the final actual Setup installation,19 frozen checks and21 native GUI checks, including custom cents, amount and record-mutation confirmation invalidation, system PDF save/readback and normal relaunch. The same installed worker produced all six voucher PDFs and passed a separate host readback. Candidate packages remain unpublished.

## Relation to the private REA reconstruction

New original-byte evidence extends the F1040V factory through declared read/write transactions and the scalar amount producer. The audited finite bridge joins three original parent-tax reconstructions to voucher amounts2435,98794 and221159. Actual boundary inputs are read before calculated gist fields when the original mode requests that behavior. The original optional TOTALW field is absent in those cases; it was not replaced with a fabricated zero.

Separate initializer evidence closes the selected empty-summary and zero-visible-array path after the NewForm event under explicitly supplied successful field leases. Original local dependency records establish a candidate one-copy section order, and a separate finite reconstruction covers the print flags. These are bounded source mechanisms. They do not establish original automatic queue completion, callback/alias failures, remote/relevancy updates, installment-policy parsing or full original execution. The App uses independently authored code and the current IRS form/payment instructions.

A further byte-audited identity producer joins those three amounts to15 output fields. The complete selected graph covers names, spouse inclusion, domestic/foreign address lines, SSN and supplied mailing lines. Five original value-specific checkbox mappings share one filing-status code input. A lightweight draft parser initially omitted this mapping type; the correction was made before freezing or applying it to the App. The finite model is ASCII-only and includes original display truncation. These are source-reconstruction limits, not IRS rules or App limits. Actual vendor field writes and automatic queue execution remain0. The App retains the full IRS instructions instead of importing a supplied source mailing address.

Windows native-source work separately distinguishes reverse/forward alias directories, successful setter value caches and ordinary canonical field serialization. Cache objects are not assumed to be serializable user data. Metadata and mapping exception catches are separately audited; a thrown mapping exception is not automatically a stored tax-field error. These findings do not unlock unsupported persistent-object or array import.

Original native executions:0. Validated original saved.tax fixtures:0. Complete.tax compatibility and full TurboTax parity remain unverified. No original binary, resource, decompiler output, key or personal return is in this repository. Three REA lanes continue original calculation/resource graphs, file/field loading and native dispatch/metadata production.

Primary sources: [IRS2025 Form1040-V](https://www.irs.gov/pub/irs-prior/f1040v--2025.pdf), [IRS check or money-order guidance](https://www.irs.gov/payments/pay-by-check-or-money-order), [Form1040 instructions](https://www.irs.gov/pub/irs-prior/i1040gi--2025.pdf), [Form6251](https://www.irs.gov/pub/irs-prior/f6251--2025.pdf) and [Form8960](https://www.irs.gov/pub/irs-prior/f8960--2025.pdf).

Reproduce:

```sh
python -m unittest discover -s tests -v
node scripts/test_pyodide.cjs
python scripts/verify_payment_voucher.py
node scripts/test_payment_voucher_runtime.cjs
python scripts/verify_payment_voucher_runtime.py
python desktop.py --smoke-test --smoke-report qa/source-smoke.json
```
