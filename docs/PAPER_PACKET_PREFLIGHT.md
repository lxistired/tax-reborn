# Paper-preparation packet preflight

The source now checks required output copies and pages before returning an IRS
TY2025 paper-preparation PDF. This implements an independently authored assembly
check suggested by the printing study in [REA wave6](REA_WAVE6_20261014.md).
No vendor code, original templates or raw decompiler output were copied.

Previously, field-value and appearance readback could succeed after an unfilled
physical template page disappeared. For example, the second page of a Schedule C
can contain no filled fields in the supported simple-business case. The remaining
filled first-page fields alone do not establish a complete rendered copy.

The application now makes its expected plan before rendering. Supporting-form
applicability still comes from `official_form_specs()` and the existing IRS-driven
calculation/input model. Each planned copy identifies the public IRS form ID,
taxpayer or spouse, a positive copy index, the pinned template SHA256, and every
physical page currently selected from that template. This release selects all
physical template pages; selective/shared-page binding is not implemented.

`official_forms.py` checks each actual serialized form, the merged supporting
packet and the final paper-preparation packet. The final packet includes separately
identified preparation-checklist pages and the two Form1040 pages. Its manifest is
embedded in PDF metadata, and page identities survive PDF serialization and merge.
Duplicate copy identities, unsupported owners, page gaps, wrong copy/owner/page
identities, output-count mismatches and empty required output raise `ValueError`.
A cached successful renderer report cannot override actual PDF readback.

`forms.packet_status()` exposes `supporting_packet_manifest` and
`supporting_packet_preflight`. The PDF endpoint response contract remains bytes.
The existing calculation, filled field/widget appearance checks, missing-facts
list, signature requirements and local persistence remain in place.

This is an assembly check for the current supported paper-preparation model.
It does not establish complete IRS form applicability, original TurboTax output
parity, `.tax` import compatibility or electronic filing. Page identities are
assembly metadata, not a cryptographic proof of every page's printed content.
`filing_packet_ready`, `electronic_filing` and `transmitted` remain false.

## Validation

`tests/test_packet_preflight.py` contains 19 synthetic boundary/integration tests.
They include actual serialized loss of a required unfilled page, spouse pages
substituted with taxpayer-copy identities despite unchanged total page count,
duplicate/reordered page identities, false renderer Success, stale successful
readback, and final checklist-page loss after export assembly. All 19 pass.
The prior 20 official-form and paper-packet checks also pass. The complete host
suite passes 404 checks with Python 3.14.5 and pypdf 6.10.0. The complete real
Pyodide suite passes 378 checks with Python 3.13.2. Independent acceptance adds
14 serialized-PDF probes and separate Pyodide export cases. Root also checks
actual HTTP/SQLite save and export for simple and business synthetic returns.
[Root HTTP receipt](../qa/packet-preflight-20261014/root-http-receipt.json)
records unchanged saved returns and preserved standalone Form 1040 fields.

Run with the project's PDF-capable Python environment:

```sh
python -m unittest tests.test_packet_preflight tests.test_official_forms tests.test_paper_packet
```

This source change does not alter the previously published preview.5 package
bytes. A subsequent packaged release needs its own build and platform receipts.
