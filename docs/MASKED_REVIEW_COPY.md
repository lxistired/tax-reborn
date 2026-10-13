# Masked Form 1040 review copy

Preview 4 includes a working **Download masked review copy** action in Save & export. It produces a three-page PDF: a scope cover and two official IRS tax-year-2025 Form 1040 pages with an explicit review-only banner. It masks taxpayer/spouse/dependent SSN/ITIN fields and refund routing/account fields. Names, addresses, contact details and tax amounts remain visible.

The original print-engine CIL supplied the field-value masking and replacement contract. Our source is independently written. Its field whitelist, fresh-template construction and refusal checks are our implementation choices. Original Java formatter/Unicode behavior and complete original PII classification have not been duplicated.

The export builds from a blank IRS template. It never edits or reuses an already-filled PDF, and it leaves saved input, preparation metadata, results and normal exports unchanged. After writing, it verifies canonical AcroForm values, widgets and appearances. It checks selected identifiers against output fields, metadata, extracted text and decoded streams. A selected identifier appearing in an unmasked text field causes export refusal. Errors produce no ordinary-PDF fallback.

Six new PDF tests pass. The full Python suite passes 367 tests, and the real Pyodide federal/form suite passes 349; 18 host HTTP/SQLite tests remain separate from the WASM count. Independent real-browser tests actually click the action in HTTP/SQLite and Pyodide/IndexedDB modes, inspect all eight selected fields and 221 other values, save/reload, and test three refusal cases in each mode. The synthetic case retains USD 9,298 federal tax and USD 20,702 refund after export. It is not a filed return.

Both modes download byte-identical PDF output. The independent inspector checks 2,501 PDF objects, 329 decoded streams, raw bytes, fields, metadata and extracted text, with Poppler as an additional text reader. See [the exact acceptance scope and receipt](../qa/masked-review-20261014/independent-browser-acceptance.json).

This is a Form 1040 review copy. It does not remove every kind of PII or mask attachments, JSON backups, supporting forms, names, addresses, contact details or financial amounts. It is not a filing packet. Native package receipts and camera tests are separate from these browser checks.
