# Mixed income TaxML migration

Preview20 inspects W-2, 1099-INT and 1099-DIV forms together in one explicitly
declared plaintext XML document or plaintext ZIP document. Each form type has
its own caller-supplied, byte-validated XPRF template binding. A copy number is
scoped to its entity, formset and form type: copy1 on three different form types
does not identify the same source record.

Choose Documents → Inspect TaxML / plaintext .tax, the source, the v2 wire
profile and its exact registry files. Review each candidate separately. After a
successful addition the candidate list returns with that item marked added.
Ownership, employer/payer, missing W-2 Boxes7/10 and interest/dividend eligibility
still require explicit review. Existing records remain separate. Re-uploading
the source does not permit adding the same source form again.

The new profile format is `tax-reborn-taxml-native-windows-profile-v2`. It uses
`templates` instead of the v1 `template`, with at most the three supported income
form types in one internal formset. The shared entity name, XML formset name and
exact headers remain explicit; the internal formset ID is not assumed to equal
the XML formset name. Single-form v1 profiles remain supported.

A corrected XML export edits only the selected form's supported amount leaves.
It preserves the other forms' original bytes and re-inspects the complete output.
Unmapped siblings, unknown objects, aliases, array rows, nondefault flags,
namespace/type mismatches and ambiguous source identities remain blocking.
Protected containers are not decrypted by this workflow.

## Executed source acceptance

The independently authored example is
[`synthetic-mixed-income.xml`](../fixtures/taxml/synthetic-mixed-income.xml),
with its [v2 profile](../fixtures/taxml/synthetic-mixed-income-profile.json) and
the existing synthetic W-2, interest and dividend XPRF files. It contains all
three form types with copy1. It is not a vendor-saved return.

Host592 tests pass. Real pinned Pyodide executes495 tests, with one additional
host-only test skipped. Seven new structural cases verify per-form carrier and
field ownership, profile reordering, copy ambiguity, global rejection and
byte-preserving selected exports. The actual integrated worker also reviews all
three record types, calculates the combined draft and re-inspects corrected XML.

Actual browser HTTP/SQLite and mobile-size Pyodide/IndexedDB tests use file
inputs, review and add all three forms from one attachment, retain an unrelated
interest record, save/reload and restore JSON into a new return. Their synthetic
expected refund is344 USD. Source receipts keep three distinct form paths and
one attachment identity. Re-upload refusal and a real corrected XML download
preserve the other two forms and the saved draft's amounts.
Six prior duplicate-import browser cases also pass.

See [source browser acceptance](../qa/mixed-income-20261015/browser-acceptance.json).
Native installers, physical-phone acceptance and public package availability
must be recorded separately. This document does not establish those states.

## Original reconstruction boundary

The private REA reconstruction has independently checked template source-owner
attachment, scalar/link presence and batched events, typed string conversion and
the selected state/bank/payment-voucher chain against original carrier bytes.
The App implements explicit source selection and reviewed migration independently.
Native execution, complete runtime template precedence, final controller presence,
complete original scheduling and original saved-return acceptance remain open.

Original TurboTax executions and validated original saved.tax fixtures remain0.
This feature does not restore a complete.tax return, recalculate the original
engine or establish full TurboTax compatibility. Original binaries, resource
dictionaries, decompiler output, keys and personal data remain private.
