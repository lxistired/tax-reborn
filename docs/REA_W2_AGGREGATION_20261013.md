# Original W-2 aggregation: bounded resource execution

Recorded 2026-10-13 against TurboTax Desktop 2025.r54.069, Intel x86_64. Original
main SHA256: `731a15d96fad8f5b1873688e71be801f63b20140301915a17af87f8e65bca8ee`.
This own-word report contains no original code, instruction payload or vendor
resource. Those materials and exact offsets/hashes remain in private evidence.

## Scope and counting

The earlier full-target batch remains **61 distinct main-executable functions
plus 4 shell/bridge functions**. This follow-up used **13 derived native
anchors** from source-matched byte windows; it adds **0** full-original main
dossiers. They retain byte-equality and location provenance but do not carry
the same whole-file analysis context. Media functions remain excluded.

The original resource path was parsed into selected instructions and executed
by an independently written, restricted interpreter on **7 synthetic fixtures**.
All 7 passed. This was genuine local execution of selected parsed resource
instructions, not merely a symbol inventory. Original TurboTax runtime runs
remain **0**, and the probe does not reproduce the complete original VM.

## Observed local mechanism

The selected compiled section iterates W-2 copies. It converts each wage to a
zero-decimal local money value, then accumulates separate owner totals. Ordinary
wages enter the owner total; a positive nonqualified-plan amount has a separate
subtraction branch. Statutory and inmate wages enter other totals.

The owner predicate checks whether the spouse marker has a value. Both spouse
and filing-status markers present select slot 2; spouse marker alone selects
slot 0, which skips this path; otherwise it selects slot 1. The selected code
then copies the two totals to taxpayer/spouse summaries. Another section adds
both or copies the taxpayer total according to the filing-status marker. Exact
`HasValue` semantics and the complete filing-status mapping remain open. The
synthetic fixtures supply owner-slot and filing-status branch preconditions;
they do not execute the complete `HasValue`/`FS2` marker predicates.

Native arithmetic evidence connects addition dispatch to the fixed-point
implementation already inspected in the original full Mach-O. A shipped
precision table gives money type 11 two decimal places and type 12 zero.
The inspected integer conversion rounds half units away from zero, including
negative half units. The fixtures cover document-level rounding, owner subtotal
selection, the positive plan adjustment and negative rounding.

## Candidate discrepancy, not a final tax result

| Synthetic W-2 wages | Reconstructed local subtotal | Current independent app: sum cents, then round |
| --- | ---: | ---: |
| $1,000.49 + $1,000.49, taxpayer | $2,000 | $2,001 |
| $60,000.49 + $20,000.49, taxpayer | $80,000 | $80,001 |
| $10,000.50 + $10,000.50, taxpayer | $20,002 | $20,001 |

These are differences between a selected legacy subtotal and the independent
app's current policy. They are not demonstrated differences in original Form
1040 output. The link to TKE `W2Summary.TotalTotalWages`, later processing and
original runtime outputs remain unverified. **The IRS tax core and frozen
expectations were not changed in response to this candidate finding.**

The probe excludes blank/sentinel values, overflow, exceptions and unselected
special-wage paths. Further validation requires exact legacy-to-TKE binding,
the remaining branches and original outputs from the same fixtures. No
activation, account or paid-service protections were bypassed.

## Independent implementation and validation

Tax Reborn separately implements W-2 stable identities, owner persistence,
per-record review, local source references and backup restoration. That work
passed 353 Python checks and 9 actual browser checks. Review is a preparation
state, not a certification or filing result. The restricted original-resource
probe and those application checks are separate kinds of evidence. See
[the reconstruction summary](REA_NATIVE_PROGRESS_20261013.md).
