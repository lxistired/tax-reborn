# Investment cost-basis correction

Tax Reborn can review and replace the cost basis of one investment sale, immediately recalculate the independent 2025 federal engine, and retain that correction through saving, reopening and JSON backup restoration. This is available in the desktop API and in the offline browser/mobile worker.

## Original behavior observed through REA

Seven complete methods in the original Desktop 2025 `stocksales.jar` show a scoped correction flow. A proposal identifies a statement, partition and security record. A matching, unapplied proposal replaces an absolute basis amount and marks it applied. The original implementation does not repeatedly subtract a correction amount. The original remote agent, broker connection and end-to-end tax-form binding were not executed or recovered.

The independently written application adopts the absolute replacement and stable target identity. Its stricter validation, local history and conflict checks are our product decisions. They are not attributed to the original software.

## Usable workflow

1. Add an ordinary supported investment sale with proceeds and cost basis.
2. Select **Correct cost basis** for that sale.
3. Enter the corrected basis, review the before/after amounts and confirm the source statement.
4. Apply the correction. Proceeds, separate adjustments and other sales remain unchanged. Tax Reborn recalculates the return and shows the historical correction below the record.
5. Save the return. Reopening or restoring its JSON backup preserves the sale identity and correction history.

Each sale has a local UUID. A correction records a distinct UUID, fingerprints of the before/after sale, the two basis amounts, time and a source note. The preparation metadata stays outside tax formulas. Replaying the same correction is a no-op; stale proposals, reused IDs with a different target or amount, malformed amounts and duplicate record IDs are rejected. An existing saved return without investment metadata receives separate identities even when two sales have identical descriptions.

## Actual acceptance

The independent synthetic 2025 case uses two identical-description short-term sales with USD 1,500 proceeds and USD 1,000 basis each, plus USD 60,000 W-2 wages and USD 6,500 federal withholding. Correcting only the second basis to USD 1,200 changes Form 1040 line 7a from USD 1,000 to USD 800 and the federal refund estimate from USD 1,305 to USD 1,329. The first sale and both proceeds remain unchanged.

Eight new HTTP/SQLite integration tests and eight real browser groups passed. The browser checks use the actual UI, Pyodide worker, IndexedDB, download and JSON restore. The complete Python suite passes 361 tests. See the [acceptance receipt](../qa/basis-correction-acceptance-20261013.json).

The filing-details presentation adapter also keeps paper-form dates and reporting categories separate from calculation records. It restores proceeds and basis fields when paper-fact templates share a collection name. The actual Python and WASM presentation schemas were compared and the final date labels and category dropdown were exercised.

## Limits

There is no remote brokerage import, original agent backend, automatic basis discovery or undo workflow. This feature does not establish original runtime or pixel parity. Unsupported adjustments and special sales remain blocked by the independent tax engine. The synthetic acceptance is a calculation and persistence check, not an accepted filing packet.
