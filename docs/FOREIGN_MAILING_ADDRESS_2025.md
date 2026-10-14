# US and foreign mailing addresses in the actual paper packet

Preview.18 adds an explicit mailing-address format in Personal details. Select US mailing address for state/ZIP rows, or Foreign mailing address for a city, full country name and separate province/state/county and postal rows. The inactive set stays saved but is not printed. Country is required for a foreign mailing address; province and postal code can be empty where not applicable. An empty country or two-letter country code leaves paper preparation incomplete. Old saved records without the selector infer the foreign format from their existing country name, including browser workspace recovery and JSON backup restoration.

This changes the mailing address only. US tax-residency, foreign-income and nonresident eligibility checks remain separate. Editing the format or address clears the paper-payment confirmation, requiring the user to review the amount and method again. It does not change Form1040 tax lines or record a payment.

The address fields follow the [IRS2025 Form1040 instructions, Foreign Address on printed page12](https://www.irs.gov/pub/irs-prior/i1040gi--2025.pdf). The country name is spelled out. The original [IRS2025 Form1040-V](https://www.irs.gov/pub/irs-prior/f1040v--2025.pdf) and its complete mailing instructions remain included.

Synthetic Germany and Canada cases preserve a2435 USD balance due. The Canada postal code `K1A 0B1` retains letters and its space. Actual HTTP/SQLite save, reopen, JSON backup restoration and serialized PDF readback pass. Both packets produced by the real pinned Pyodide worker have14 independently expected canonical fields, page widgets and appearances, four blank US fields and11 reconciled pages. Host585 tests, real Pyodide488 executed tests (one additional test skipped), four actual browser migration cases and21 source desktop checks pass. These source checks do not establish native GUI or physical-phone acceptance. Those states are recorded separately for each candidate.

The private REA work continues separately. Fresh calculation-queue evidence closes an explicitly supplied, one-copy eight-section payment-voucher replay, including dequeue, interpreter and after-batch handling. The actual Windows resource reader uses exact type/resource keys. Type1510 is a distinct record-title attribute; it is not an automatic substitute for type1500. These mechanisms are independently reconstructed and bounded. Original native TurboTax executions and validated original saved.tax fixtures remain0. Full.tax read/write compatibility, complete native scheduling and full TurboTax parity are not established. Original vendor resources, binaries, decompiler outputs, keys and personal data remain private.

Reproduce:

```sh
python -m unittest discover -s tests -v
node scripts/test_pyodide.cjs
node scripts/test_schema_migration.cjs
node scripts/test_foreign_address_runtime.cjs
python scripts/verify_foreign_address_runtime.py
python desktop.py --smoke-test --smoke-report qa/source-smoke.json
```
