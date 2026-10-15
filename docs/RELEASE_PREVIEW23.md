# Tax Reborn preview.23 — ordered field sources and existing indexed tables

This preview extends the actual local tax-preparation workflow with two ordered
registry files and explicit derived ValueTable preservation. See the
[step-by-step source workflow and limits](BINARY_EFFECTIVE_REGISTRY.md).

The independent income sample supplies W-2, 1099-INT and 1099-DIV records.
Separate reviews enter them into the working IRS-based calculation and produce
a $344 refund estimate. The source hashes, exact profile and selected visible
and hidden field sources remain attached after saving and reopening.

The indexed-table sample retains a nonzero used value, a present zero, a nonzero
unused value, the saved table boundary, child forms and four links. These table
rows are read only. Correcting the ordinary WAGES scalar to 1234.57 produces a
separate complete 1,584-byte binary, checked by full reparse and comparison.
Unknown present facts block income additions.

Desktop exports now write atomically to the user-selected native save location.
They remain real files after the application closes. Canceling does not report
a saved file and retains the local draft. This fixes an observed Windows
WebView download that disappeared after normal application close. The desktop
transport keeps the existing content security policy; it does not require
dynamic JavaScript evaluation.

The platform acceptance JSON separates the original preview.23 feature tests,
the final desktop transport build, same-signer Android installation, actual UI
checks, cold restarts and complete system-export readback. Host checks pass 648
tests. The actual packaged Mac and Android WebAssembly assets also execute the
binary decode/review/calculation/correction/readback workflow.

## Remaining work

The derived ValueForm D2 field map and D1/DE/DF persistent-object tail have a
separate private source-backed bridge under review for App integration. They
are not included in this preview's public stream profile. Full current-template
remapping, native row reconstruction, raw-source aggregation and the complete
original calculation scheduler remain incomplete.

All acceptance inputs are independently generated. Original TurboTax runtime
executions and validated original saved-return fixtures remain zero. This is
not established as a complete original `.tax` replacement or an electronic
filing product. App tax results use independently written code and official
IRS TY2025 rules; no Intuit executable, resource programs, artwork, keys or
taxpayer data are bundled. The source includes OpenTax corresponding source and
dependency notices under AGPL-3.0-only. Maintainer:
[@lxistired](https://github.com/lxistired).
