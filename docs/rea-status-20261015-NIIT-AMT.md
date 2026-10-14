# Capital gains, NIIT, AMT and actual paperwork

Preview.16 completes the printed Form8960 component rows for the existing supported investment-income profile. The previous calculation produced the correct tax but omitted capital-gain rows5a–5c, rental rows4a–4b and deduction subtotal9d/10 from the official PDF. These rows now reconcile with totals5d/4c/11. Foreign/entity/disposal adjustments remain unsupported; zero adjustment rows do not establish support for those transactions.

## Independently verified working flow

Eighteen fixed IRS TY2025 synthetic cases cover the 20% capital bracket, the single-filer200000 NIIT boundary, the533400 capital-rate boundary, AMT exemption phaseout and two dividend copies with cents. The App matches both final Form1040 amounts and the selected Form6251/Form8960 worksheet lines. No original vendor code or compiled program is shipped.

Two real HTTP/SQLite returns were saved and reopened using a fresh database connection. JSON export retained the inputs and calculated result. The actual interactive official packets passed canonical field, page-widget, appearance and page-identity checks against independent printed-row oracles. With explicitly entered synthetic filing facts they are ready to print and review; filing_packet_ready and transmission remain false.

| Synthetic facts | Regular tax | AMT | NIIT | Total tax | Refund |
|---|---:|---:|---:|---:|---:|
| Wages5000, interest1000, ordinary dividends1000, capital distributions600000, withholding120000 |84328|0|15466|99794|20206|
| Wages190000, interest1000, ordinary dividends1000, capital distributions800000, withholding250000 |177290|14773|30096|222159|27841|

Amounts are USD, TY2025, single filing status. Synthetic fixtures are in [capital_niit_amt_2025.json](../fixtures/capital_niit_amt_2025.json). [Actual HTTP packet receipts and PDFs](../qa/niit-amt-packet-20261015/) distinguish source-runtime acceptance from native package checks. [Native preview.16 candidate state](../qa/native-preview16/candidate-acceptance-state.json) records generated/install/test/publication separately. Mac passed real native system PDF save and normal relaunch with prior returns retained. Windows passed Setup,18 frozen checks and20 native GUI checks; its positiveAMT/NIIT packet has installed native HTTP and actual installed worker acceptance, with a separate NIIT-specific GUI export still untested. The actual APK worker passed18 cases and two exported packets, but phone installation/UI is unverified while USB is absent. Packages remain unpublished candidates.

Primary arithmetic/printed-row sources: [IRS2025 Form1040 instructions](https://www.irs.gov/pub/irs-prior/i1040gi--2025.pdf), [Form6251](https://www.irs.gov/pub/irs-prior/f6251--2025.pdf), [Form8960](https://www.irs.gov/pub/irs-prior/f8960--2025.pdf). Per-worksheet-line whole-dollar rounding is tested at the capital-rate boundary.

## REA evidence and remaining work

The private reconstruction now links selected original raw1099 copy/summary ownership, annual constants and parent income into the 20% capital, NIIT, positiveAMT, Schedule2 and final refund/owed destinations. Root checked the frozen original-byte windows and independently reran all18 cases. The finite replay still supplies an existing Schedule2 and, when needed, an existing payment voucher, with explicit phase order. Native form creation and automatic event/scheduler execution have not been claimed.

Windows map/template/object-factory resource decoding and native post-restore Date readback received separate original-byte audits. Ordinary persistent-object writing, full.tax compatibility, automatic mapping/constraint qualification and whole native controller execution remain open. Original native executions and validated original saved.tax files are both0. Three REA lanes continue those branches.

Reproduce the App checks:

```sh
python -m unittest discover -s tests -v
node scripts/test_pyodide.cjs
python scripts/verify_niit_packet.py --output-dir qa/niit-amt-packet-20261015
node scripts/test_capital_niit_amt_runtime.cjs
```
