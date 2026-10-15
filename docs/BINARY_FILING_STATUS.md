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

Validation for this source candidate includes 621 host tests, real Pyodide
calculation, actual SQLite save/reopen and the offline browser UI with actual
IndexedDB save/reload/source reopening. In a fictional $60,000 wage case, changing
Single to Married Filing Jointly recalculated the existing worksheet's federal
tax from $5,075 to $2,946. This example demonstrates data flow, not tax advice.

Preview22 is a source/build candidate. The last published installers remain
preview21 until the new packages have separately completed native acceptance.
See `qa/filing-status-20261015/acceptance.json` for the explicit evidence states.
There is still no real original saved-return fixture or original-engine runtime
comparison. This feature does not establish complete `.tax` compatibility,
original recalculation parity or electronic filing.
