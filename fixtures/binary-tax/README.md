# Independently authored binary examples

These sample files contain invented people, employers, income amounts, string
records and form graphs. They include no original saved tax return, vendor
resource, license data or activation material. The complete requests include
the three caller-owned synthetic XPRF registries from `fixtures/taxml` and an
explicit binary profile. They do not require an installed tax product.

`income-request.json` and `income.taxbin` contain one W-2, one 1099-INT and one
1099-DIV. Their income boxes match the independently authored
`synthetic-mixed-income.xml`. After a reviewer supplies the requested owner,
payer, scope and eligibility facts, the App calculates a $344 refund. Importing
these records does not establish that a return is complete or ready to file.

`nested-request.json` and `nested.taxbin` add a zero-valued child 1099-INT, one
nonempty table header and four resolved links, including forward and backward
references. The table record is supported header metadata; it does not claim
unrecovered table-row semantics. The child attachment is an invented structural
test association. All income totals remain the same as the first example.

`unused-zero-request.json` and `unused-zero.taxbin` keep a nonzero wages payload
whose Used flag is clear, next to explicit present zero withholding. Wages stay
missing and cannot be reviewed or edited as an ordinary amount. Blank is never
silently converted to zero.

Run `python3 scripts/create_binary_fixture.py` to reproduce these files. The
generator constructs each document and packed value itself; it reads only the
three independently authored registries. `manifest.json` binds the generated
binary and full request bytes with SHA-256. `tests/test_binary_tax_app.py`
exercises actual inspection, one-field corrections, income export, rereading,
structure retention, hash checks, and the App's own calculation result.

Corrected binary copies retain supported parsed structures. They do not execute
the original tax engine, recalculate original derived fields, demonstrate
original-program acceptance, or establish compatibility with all saved returns.
