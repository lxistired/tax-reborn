# Ordered registry sources and nonempty ValueTable preservation

Preview.23 extends the binary migration workflow in the working tax App. In
**Documents → Open TaxML / binary .tax**, expand the independent samples.

**Load income sample with two registries** uses separate visible and hidden
field definitions from two explicitly ordered XPRF files. The profile binds the
complete file hashes, directory entries, versions and selected field sources.
Review the W-2, 1099-INT and 1099-DIV records separately before adding them. The
fictional amounts produce a $344 refund estimate in the existing IRS-based tax
engine. Saving and reopening preserves each reviewed source binding. The sample
does not establish that the household is complete or ready to file.

**Load source with indexed table values** contains a derived ValueTable header,
existing indexed values, a child form and four links. The reader retains its
saved last-used record index, a present zero value and a nonzero unused value.
The index is a saved boundary, not a row count. These values are read only;
adding, removing or reordering table rows is unsupported. Unresolved source
facts block adding the income candidate.

Use **Inspect / edit binary fields** to change a supported numeric scalar. The
App writes a separate complete binary copy, reads it again and compares every
other parsed field and represented structure. For the fictional ValueTable
sample, changing WAGES from 1234.56 to 1234.57 produces a 1,584-byte correction.
The same expected complete bytes are used for independent platform acceptance.
The original attachment is retained.

Desktop exports use the operating system's save dialog followed by an atomic
local write and complete byte readback. Canceling the dialog retains the draft.
The exported file is independent of the WebView download lifetime and must
remain readable after the App quits. Android continues to use its system
document provider. A separate platform receipt records installation, actual UI
checks, cold reopening and full exported-file verification.

## Explicit limits

These are independently authored fixtures and a finite selected Entity stream
profile, not original saved TurboTax returns. The owning table factory must be
declared explicitly; schema numbers and trailing bytes are not used to guess it.
Template checksums and carrier identities are caller bindings, not proof of
native compiler state or vendor authenticity.

This preview does not implement the complete derived ValueForm persistent-object
tail, native field remapping, table row reconstruction or original recalculation.
Source correction does not update the original program's computed totals.
Original runtime executions and validated original saved-return fixtures remain
zero. Complete `.tax` compatibility and original-engine parity remain unverified.
The working App calculates its supported tax situations using independently
written code and official IRS TY2025 rules.
