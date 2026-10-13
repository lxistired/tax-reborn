# Interest and dividend preparation: preview.5

Tax Reborn now keeps a stable UUID for each current 1099-INT and 1099-DIV row.
Review status, unresolved source facts and prior-year placeholders are local
preparation metadata, separate from federal calculation inputs. The tax engine
and its existing reference fixtures are unchanged.

## Working UI and persistence

Each interest/dividend card shows its ID, a source-review checkbox, an explicit
prior-year-placeholder checkbox and unresolved-field choices. Changing payer or
amounts clears only that document's review. Zero is a valid amount; a missing
source fact is recorded separately. Reviewing a document does not clear its
missing facts. The review summary is rebuilt from current rows, so a deleted
document cannot leave a phantom reviewed entry.

CSV import previews source rows and mappings. For interest/dividends, it can
replace only explicitly checked placeholder IDs. Same-payer rows with other IDs
remain unchanged. A failed parse, invalid amount, stale proposal or failed save
does not change the current rows. Reviewed new rows, selected removals and their
audit receipt are saved together in one SQLite or IndexedDB transaction.

The receipt retains the replaced rows and their metadata, the exact removed and
result IDs, an import event ID and an immutable payload fingerprint. An exact
event replay is a no-op; conflicting use of the event ID is rejected. Once saved,
history cannot be silently cleared or rewritten by a later save. The import
also submits the last saved return revision: an intervening update from another
workspace is rejected before either storage transaction writes.

The normal save/reopen and JSON backup/restore flows include this metadata.
Restoration creates a new return, while stable document IDs and local history
remain available inside that copy. A placeholder is still included in the
estimate until replaced or removed. The header and source-review card explicitly
report its unresolved source status. Preparation checks do not certify a filing.

## Actual example and checks

The root's actual UI case starts with two interest rows from the same synthetic
bank: $1,000 and $350. It marks the first row as a placeholder, selects that ID
in the CSV dialog and imports $1,200. The saved 1040 line 2b becomes $1,550. The
other row, including its raw value and UUID, remains unchanged. The real estimate
changes from a $1,263 refund to $1,239 in this synthetic W-2 demo. Those refund
values belong to this fixture, not the separate unit-test fixture.

[Actual UI/API readback](../qa/income-preparation-20261014/root-actual-ui-replacement.json)
and [saved rows screenshot](../qa/income-preparation-20261014/root-actual-saved-rows.png)
record that run. Ten new pure-module tests and eight real HTTP/SQLite tests
cover identity, migration, review invalidation, missing facts, typed validation,
replacement, replay/conflict/staleness, audit integrity, backup and concurrent
revision refusal. The complete suite passes 385 host tests; 359 pass in the
actual Pyodide runtime, excluding the 26 host-only integration tests.

[Independent UI acceptance](../qa/income-preparation-20261014/independent-ui-acceptance-run-2026-10-13T19-11-17-843Z.json)
passes 22 checks, eleven each in actual HTTP/SQLite and Pyodide/IndexedDB mobile
layouts. It exercises real CSV selection, one-shot save failures and retries,
private browser-profile close/reopen, actual JSON download/restore, review and
unresolved-state separation, deletion summaries, INT/DIV replacement and eight
persistence tampering refusals. Its synthetic fixture has different withholding
from the root example, so its $2,739 refund is not substituted for $1,239 above.
The actual packaged Mac app also selected the CSV through the Cocoa Open panel,
completed the same exact-ID replacement, recalculated and saved; see [native
receipt](../qa/native-preview5/macos-native-income-replacement.json).

## Original evidence and implementation boundary

The packaged original topic code separates per-instance review snapshots from
completeness, and contains selected old-shell processing after a successful
import. The review handler is registered only under the original online/Web
predicate. Manual-entry processing does not itself delete an old income row.
The NEC deduplication route is restricted to a TTO offering; its actual remote
topic algorithm was not present in the studied local topic bodies.

Our UUID selection, fingerprints, immutable event protocol, atomic local save
and explicit source-check UI are independently implemented safeguards. They do
not claim the original desktop automatically performs this exact flow. There
is no broker connection, automatic prior-year import, recovered NEC duplicate
algorithm, per-owner INT/DIV input or original-program runtime comparison.
