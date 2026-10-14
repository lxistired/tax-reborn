# Reviewed TaxML W-2 import

Preview.7 adds a working local document-to-W-2 workflow. It consumes actual
selected file bytes, creates a reviewed W-2 record, recalculates the return and
retains its source receipt through saving, reopening and JSON backup.

Use Documents → **Inspect TaxML / plaintext .tax**. Select a plaintext XML
document or an explicitly declared plaintext ZIP, an explicit wire-profile JSON
and its matching caller-owned XPRF registry files. Review the selected profile,
then inspect. The profile binds the root QName, namespace context, exact carrier
SHA-256 and resource identity; the document cannot select that profile itself.

Check the employer and all amounts against the original W-2. Choose taxpayer or
spouse explicitly. Missing amounts remain blank. Boxes 1–6 must be decoded from
the selected source; missing Boxes 7 and 10 require explicit values, including
zero only when verified. Present source fields with unsupported semantic types,
unknown facts and ambiguous form copies block addition. Adding a reviewed W-2
appends a record; it does not replace prior W-2 records.

The employer is read from `CA` and continuation `CA2`, not the separate `NAME`
caption field. Source amounts retain cents. Review does not assert household
eligibility or that all income has been reported. Ordinary edits clear review
for the affected record while retaining its source identity. A retained record's
source receipt cannot be silently rewritten or removed.

For a reproducible demonstration, use the independently constructed files in
[`fixtures/taxml`](../fixtures/taxml): `synthetic-w2.xml`,
`synthetic-wire-profile.json`, and `synthetic-w2.xprf`. A corresponding declared
plaintext ZIP is `synthetic-w2-plaintext.tax`. The missing-box fixture must be
rejected. These files contain no taxpayer records or original vendor resources.

The executed browser workflow produced a $483 refund from its first synthetic
W-2; appending the same statement from the ZIP preserved the first record and
produced $7,872 owed. It remained blocked for unconfirmed eligibility facts.
The selected source download matched its original SHA-256. The stage's actual
UI receipts and screenshots are under [`qa/taxml`](../qa/taxml). Version-specific
native receipts record checks against the final installed builds.

The 421 host checks include HTTP/SQLite save, reopen, backup, immutability,
amount/type binding and rejection cases. The existing 378 Pyodide federal/form
checks are separate from 25 checks through the actual worker and JS metadata
contracts. These counts do not establish original application parity.

This feature does not decrypt encrypted `.tax` files, import a whole return,
write an original `.tax` file, execute TurboTax or establish original saved-file
compatibility. The selected scalar/file contracts were researched with REA and
implemented independently. No vendor registry, formula program, keys or binary
is distributed. [Wave 7 evidence and remaining work](REA_WAVE7_20261014.md)
explains those limits.
