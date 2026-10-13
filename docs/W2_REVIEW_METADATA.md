# Local W-2 identity and review state

Each W-2 has a stable local record identity, a taxpayer/spouse owner, and a separate source-document review state. Ownership remains in the federal input because it affects calculations. Identity, review and source links remain outside federal input. This change does not change IRS rules, tax amounts or filing readiness.

The desktop SQLite API and the Android/PWA IndexedDB adapter accept and return this top-level preparation object alongside `data`, `result` and `states`:

```json
{
  "metadata": {
    "version": 1,
    "w2_records": [
      {
        "record_id": "local UUIDv4",
        "row_fingerprint": "SHA256 of current normalized W-2 values",
        "reviewed": false,
        "reviewed_at": null,
        "reviewed_fingerprint": null,
        "source_document": null
      }
    ]
  }
}
```

`w2_records` follows the current order of `data.w2`, while each `record_id` stays with its own W-2 through edits, deletion of other rows, saving and reopening. The frontend uses the identity for expanded-row state and review controls. It does not display the identity to the user. Clients that reorder or delete records must make the same change to the metadata array.

A review fingerprint includes all W-2 fields and the owner. The eight monetary input fields are normalized to cents before hashing, so `60000` and `60000.00` describe the same reviewed amount. The desktop and browser implementations are checked against each other, including Unicode employer names and negative zero. An actual amount, employer or owner change clears that record's review. Other W-2 records keep their state. Review controls do not prevent export or change tax calculations.

Manual entry has an explicit per-W-2 checkbox. CSV import adds unreviewed W-2s for individual checking. Confirming the OCR candidate dialog adds a reviewed W-2, its checked-value fingerprint, and a local source reference containing `document_id`, `return_id`, `name` and `method`. No document bytes, filesystem paths or external service URLs enter this metadata. A source document is opened only when its stored return identity matches the current return and the IndexedDB document belongs to that return.

Desktop preparation metadata uses a separate `preparation_metadata` table. Reading an old return creates unreviewed metadata without changing its federal data, result or saved timestamp. Missing metadata never implies review. Legacy API clients that omit metadata can retain identities only for unique, unchanged value matches; ambiguous duplicate rows remain unreviewed. Current frontend saves always send explicit record identities, including for identical W-2s.

Workspace checkpoints and JSON exports include metadata. Restoring a backup into a new return keeps W-2 identities and valid review fingerprints. Source references retain their original return identity for explanation, but attachments are not copied. The restored UI shows “Source attachment not restored” and cannot use an old return's attachment as the new return's source. The original return remains intact.

The calculation endpoints and worker receive only `data`. Preparation metadata is validated by the local storage layer, not inserted into a tax-engine row. Invalid metadata rejects a save before either data or metadata is committed. Deleting a return deletes its separate preparation record too.

Validation is recorded in `qa/w2-metadata-validation-20261013.json`:

- 10 actual loopback HTTP/SQLite tests cover legacy migration, independent equal records, reorder/delete/add, owner/value changes, JSON export/restore, atomic rejection and deletion.
- 9 isolated headless browser tests cover actual controls, save/reload checkpoints, source links, backup restoration, cross-language fingerprints, and the real offline worker with IndexedDB persistence.
- 353 Python checks pass, including existing frozen oracle integrity checks. No tax oracle or formula was changed.

The browser OCR test uses a synthetic extraction result to verify the confirmation and source-link contract. It does not claim OCR accuracy, camera behavior, a phone installation, original-product runtime parity or electronic filing.
