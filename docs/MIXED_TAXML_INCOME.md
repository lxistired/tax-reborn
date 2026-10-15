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
Six prior duplicate-import browser cases also pass. A delayed automatic-focus
regression confirms that a modal does not move focus away from an input the user
has already selected.

See [source browser acceptance](../qa/mixed-income-20261015/browser-acceptance.json).
The actual Mac Preview20 app also passes the system-file-picker mixed import,
saving and normal quit/relaunch. Its prior13 synthetic returns remain unchanged,
and the readonly DMG matches424 entries in the tested app. Windows installer
and installed-runtime results, Android packaged-worker results, physical-phone
acceptance and public downloads are recorded separately in
[candidate20 acceptance](../qa/native-preview20/candidate-acceptance-state.json).
Windows Setup installation,21 frozen checks and23 existing native GUI checks
pass. Its actual installed JS/Pyodide worker passes the new mixed-income flow;
the same existing Preview20 package now also passes the separate actual native
[mixed-form GUI run](https://github.com/lxistired/tax-reborn/actions/runs/38664116326).
Three XPRF registries are selected through the system Open dialog, all three
income candidates are individually reviewed, and saved source paths/amounts
survive normal close/relaunch. A repeated add is refused, and system Save As
exports byte-exact selected interest corrections while W-2/DIV and the saved
draft remain unchanged. The exported file also survives normal App close.
See [root readback](../qa/native-preview20/windows-mixed/root-readback.json)
and [actual reopened screenshot](../qa/native-preview20/windows-mixed/windows-native-mixed-reopened-344.png).
Android retains
the original signer and its120 extracted assets and actual JS/Pyodide mixed flow
pass. Its physical installation, data retention and GUI remain pending while
USB is absent. All four candidate packages are generated and hash-verified;
they are not a published GitHub Release. Preview12 remains the public installer.

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
