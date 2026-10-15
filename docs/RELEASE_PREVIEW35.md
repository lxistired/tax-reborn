# Preview 35 — correct existing stored amount cells in a complete source

Documents now offers a real existing-cell correction workflow. It distinguishes an explicitly present zero amount from unused storage, checks the complete source, registry identity, owner, saved/current field mapping and unique reachable cell, and saves a separate complete corrected source. It changes only that cell's raw amount. Existing tables, child forms, links, Entity/FormSet objects, source-field mapping, flags and all other stored values remain intact.

The included independent example has two FormSets, eight forms, two nonempty tables, two child forms and eight links. The first cell changes 25.00 to 1234.57; a second, explicitly present zero changes to 12.34. The complete saved outputs are 8,458 and 8,460 bytes. Their complete readback checks restore the single raw amount and require the entire document to equal its original snapshot. The verifier does not call the correction API to generate its expected answer.

The separate fixed original-resource policy supports the byte-verified existing FSCHB.INT.AMT kind11/fmt0 cell family, with its own complete registry identities and raw-only bounds. Original resources stay private and must be supplied locally by the user. Public independent example credentials cannot authorize the original-resource policy. Unsupported ownership, override, unused storage, ambiguous hash chains, altered resources, new rows and unsupported values are refused.

## Actual validation

- The source passes 805 host checks and 694 real Pyodide executions, with two explicit skips. Both HTTP/SQLite and 390px Pyodide/IndexedDB pass actual Documents file inputs, complete downloads, independent readback and unchanged current-data/result/metadata persistence and reload. Twelve delayed-response cases are refused. Browser download cancellation is explicitly simulated.
- Windows x64 Setup installs and passes 21 installed frozen checks and 22 native GUI workflows. Both new existing-cell sources are edited, saved through the OS panel and reopened. [Exact CI run](https://github.com/lxistired/tax-reborn/actions/runs/38823376459).
- Mac ARM64 completes both new native source workflows and full-file readback. Its actual 86-module comparison saves and rereads a 124,641-byte wage audit against the complete saved IRS return. All 17 saved returns and 16 preparation records remain identical through normal close/relaunch. Its read-only DMG matches all 817 tested bundle paths.

- A real Android device receives the original-signer update with its original app identity and installation date. Both new cells are edited and system-saved through the actual phone GUI; complete output files match Mac, Windows and both main App browser modes. The installed APK also passes the actual JS/Pyodide two-cell and refusal checks. Its 86-module wage comparison saves and rereads the complete124,641-byte audit. Complete33,114-byte backups preserve all seven sections, the saved$344 estimate and existing data. No wireless-debugging settings change.
- All338 web assets are byte-identical across source, Mac, Android and the Windows portable package.

[Actual acceptance records](../qa/native-preview35/) · Maintainer [@lxistired](https://github.com/lxistired).

## Precise limits

This correction does not run the original setter, propagate a new value through links or dependent fields, recalculate original tax totals, create/delete/reorder rows, or replace the current IRS return. App-owned calculations and source editing remain separate. The original app's complete Load/default/cache/observer/interpreter chain and encrypted archive compatibility remain incomplete. Original licensed program executions and original taxpayer saved-return fixtures remain zero. Four isolated unchanged original machine-code leaves were additionally checked on 6,168 owned CPU-emulator cases; that is separate from execution of the licensed application and does not establish its complete calculation engine.

The app retains independent IRS-rule calculations, supported official forms and existing local data. Complete original `.tax` compatibility, original-engine parity, electronic filing, Intel Mac and native iOS acceptance are not claimed.
