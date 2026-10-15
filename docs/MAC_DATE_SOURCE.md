# Existing date fields in a source copy

The explicit `tax-reborn-taxml-native-mac-profile-v3` profile adds inspection
and correction of existing ordinary date, day and month fields. It uses the
same complete caller-owned XPRF registration as the envelope, full field ID,
kind, current ordinal and CID names. Earlier v1/v2 profiles continue to refuse
date fields. Selected forms remain W-2, 1099-INT and 1099-DIV.

Open **Documents → Inspect / correct source** with plaintext Mac TaxML or an
explicitly cleartext persistence container, its v3 profile and complete registry
files. Choose **Inspect / edit date fields**, select the exact stored entity,
form/file copy and field, enter the required text and confirm the correction.
Download the corrected copy. The original source remains attached. Saved source
bindings are retained when reopening the App.

| Stored kind | Accepted source text | Calendar boundary |
|---|---|---|
| Date, 4 | `MM/DD/YYYY` | Gregorian years 1900–9999; no automatic ISO conversion |
| Day, 5 | `MM-DD` | Month/day only; February 29 allowed using the native 1984 sentinel |
| Month, 6 | `YYYY-MM` | Years 1900–9999; a native internal day of 1 does not add a stored day |

Each correction binds the complete source/profile/field receipt and changes
one existing text span. It reparses all fields, stored entity/copy identities
and field/value attributes. Container correction additionally verifies CRCs,
retains the original Manifest and copies every unselected local record exactly.
Unknown manifest metadata makes the source read only. Used-false fields,
taint/unknown value flags, unbound fields, nonordinary compiled formats and
attributes are refused. Changing the selected field or closing the dialog while
a calculation response is pending prevents a stale download.

Dates do not enter money amounts, income review, household ages or the current
IRS calculation. Existing current return inputs, result and saved data remain
unchanged. The in-App sample is independently generated fictional data with
two entities, seven form copies, nine dates and 53 total fields.

This operation edits serialized source text. It does not execute the original
program's LoadValue, current StringTable allocation, SetValue, callbacks or
recalculation. The original format-0 date output can retain its source string;
that does not prove inbound native date acceptance. Original runtime executions
and original taxpayer fixtures remain zero. Encrypted original `.tax` files,
native current inventory and complete compatibility remain unverified.
