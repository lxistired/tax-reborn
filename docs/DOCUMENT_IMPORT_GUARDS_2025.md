# Reviewed source imports for tax year 2025

Preview19 prevents a repeated source import from silently counting the same income twice. The existing record remains editable, with its original source receipt retained.

For OCR, a W-2 already linked to the same local attachment cannot be added again. For reviewed TaxML W-2, 1099-INT and 1099-DIV imports, the source-file SHA256, archive member and source form path identify the source form. Re-uploading the same file under a new attachment ID, or choosing another wire profile for that same source form, does not create a second income record. Separate source form paths and archive members remain independent. Identical amounts entered manually are not treated as duplicate evidence. This is a source-identity guard; it does not claim to detect the same paper form photographed twice into different attachments or exported into different files.

OCR extraction and reviewed insertion retain the open return's revision. Editing that return while extraction or asynchronous fingerprinting runs cancels the stale insertion. Closing the review window while fingerprinting also prevents a later invisible addition. Adding a reviewed OCR W-2 clears the earlier income-completeness confirmation, so the user must review the updated income collection. Existing W-2 values and their identities are retained.

## Executed source acceptance

- Thirteen browser checks exercise real HTTP/SQLite and IndexedDB persistence, source viewing, review metadata, JSON backup restoration, duplicate OCR rejection, changes during extraction/commit, and closing a pending review. The extractor is synthetic and checks the review workflow; this is not camera or OCR-accuracy evidence.
- Six actual browser cases inspect independently authored TaxML through the actual Pyodide worker, add and save one W-2, 1099-INT or 1099-DIV, then re-upload its source. Both HTTP/SQLite and browser Pyodide/IndexedDB retain one record and unchanged tax totals after save and reload.
- The actual worker/runtime checks cover re-uploaded source identity, changed wire profiles, independent form paths/archive members, immutable receipts, reviewed amounts and corrected XML readback.

Receipts and screenshots: [document import acceptance](../qa/document-import-guard-20261015/), [W-2 browser checks](../qa/w2-review-browser-tests.json), and [actual TaxML worker](../qa/taxml/runtime-receipt.json). Native package generation and platform execution are recorded separately; these source checks do not establish physical Android acceptance or original TurboTax compatibility.

## REA evidence and independent implementation

Private original-binary analysis now distinguishes display text, field-used flags, overwrite guards, conversion, a setter request and final stored presence. Selected original AutoFill code retains nonempty existing display text unless a specific drop-assigned flag or force path applies. It can also return after discarding a local setter error. The independent App reports rejected insertion rather than reproducing that silent-error behavior. Source-import identity and revision guards above are independently authored product decisions informed by this distinction; they are not recovered TurboTax algorithms.

The separately audited binary branches establish the actual payment-voucher mailing producer, native checkbox-member assignment to a group base and a distinct group-field change event, selected AutoFill descriptor layout, and template-attribute payload acquisition/release/purge/reload. Finite source replays still supply successful ordinary callbacks and selected current-input facts. Original runtime execution and original saved-return fixtures remain zero. Complete `.tax` read/write, global calculation scheduling, final field-presence verification and original-result parity remain open. Vendor binaries, private resource literals and decompiler output are excluded from this repository.
