# Reviewed filing-status migration

The binary source inspector can now read the five explicitly bound FINFOWKS
filing-status checkboxes and offer their selection for review. Applying a
reviewed selection changes the current return, recalculates the existing tax
worksheet, and retains an immutable source receipt alongside the saved return.
The original binary file and caller-selected registry remain local attachments.

Try **Documents → Open TaxML / binary .tax → Try independently generated binary
samples → Load filing-status sample → Review filing-status setup**. The sample
selects married filing jointly. It is fictional data, not an original saved
TurboTax return. Its independent formset identifier is deliberately different
from a TPS mapping coordinate; the App resolves the actual supplied registry.

The current binary profile retains the legacy JSON key `template_versions`.
Its per-formset unsigned 32-bit value binds the reconstructed CTFS metadata
checksum field. It is not a tax-year number, a conventional version, or the
SHA-256 of a carrier. The owned examples use the authored number `2025`; that
number does not establish original-template compatibility. Original CTFS
construction also depends on template descriptor names and date/time inputs.
Automatic original-checksum reconstruction remains outside this feature.

The five checkbox facts preserve the distinction between absent, unused,
present unchecked and present checked. A stored nonzero unused value remains
unused. This checkbox conversion ignores the per-value format byte; template
format and per-value format are separate facts. Exactly one canonical selected
checkbox and supported scalar metadata are required. Conflicting selections,
unsupported attributes, diagnostic headers and noncanonical checked values
cannot be applied.

The review screen compares current and source filing status. It requires an
explicit confirmation before applying the change. It clears filing-status
eligibility, head-of-household and surviving-spouse confirmations, income
completeness and paper-payment confirmation. Other income and tax inputs are
retained. The source does not establish eligibility for a filing status.

Saved source history records the prior status, imported status, review time,
source-file hash, registry/profile identity and form path. The profile page can
reopen that source after a reload. A duplicate source cannot add a second setup
receipt. An older client omitting the new history namespace preserves it;
explicit deletion or alteration of saved receipts is rejected. Current filing
status can still be edited normally; the history describes a past import.

Validation includes 621 host tests, real Pyodide
calculation, actual SQLite save/reopen and the offline browser UI with actual
IndexedDB save/reload/source reopening. In a fictional $60,000 wage case, changing
Single to Married Filing Jointly recalculated the existing worksheet's federal
tax from $5,075 to $2,946. This example demonstrates data flow, not tax advice.

Preview22 Windows Setup, Mac ARM64 and original-signer Android packages have
separately completed this native workflow, saving, cold restarting and reopening
their source history. The Android process was force stopped through its system
App info page and relaunched with a different process ID; previous returns and
the data directory were retained. The read-only Mac DMG matches all385 regular
files and73 symlinks in the tested App. Windows acceptance installed the same
Setup bytes produced by the recorded build job.
See `qa/filing-status-20261015/acceptance.json` for explicit evidence states;
publication and anonymous downloads are checked separately after packaging.
There is still no real original saved-return fixture or original-engine runtime
comparison. This feature does not establish complete `.tax` compatibility,
original recalculation parity or electronic filing.

The Android package also places its WebView outside the status bar, navigation
bar, display cutout and on-screen keyboard. Actual Android15 testing exposed a
header button partly covered by the system status bar. Insets are now applied
to the native container, following the
[Android edge-to-edge guidance](https://developer.android.com/develop/ui/views/layout/edge-to-edge).
Native acceptance is recorded separately from build and installation.
