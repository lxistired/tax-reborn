# Tax Reborn preview.21 — binary income migration and complete structure-preserving corrections

Windows x64 Setup/portable, Mac ARM64 DMG, Android APK and corresponding source are available in this preview. Maintainer: [@lxistired](https://github.com/lxistired).

From Documents, open **TaxML / binary .tax** and expand the independent binary samples. The income sample contains W-2, 1099-INT and 1099-DIV records. Review every record before adding it: the actual application recalculates a $344 refund, saves the return and keeps the original source. This is an income-migration workflow in the working tax App.

The nested sample includes a nonempty table header, a child form and four forward/back links. **Inspect / edit binary fields** can write a supported numeric correction into a separate binary copy. The writer reloads the complete document and compares every parsed field and supported structure. Windows, Mac and the actual Android phone changed WAGES 1234.56 to 1234.57 through the GUI and system save dialog; their complete 1,545-byte exports have the same SHA-256. Unchanged fields and structures are retained.

## Executed platform checks

| Platform | Actual native workflow | Remaining gate |
| --- | --- | --- |
| Windows x64 | Setup installation, 21 frozen checks, 27 GUI checks, income import/recalculation/save/relaunch, full binary edit and system-save/readback | No original TurboTax execution or original saved-file comparison |
| Mac ARM64 | Native income import/recalculation/save/cold restart, retained source bindings, full binary edit/system-save/readback; all 379 DMG App files match the tested App | Intel Mac not built or physically tested |
| Android | Same-signer update, old return retained, actual three-income review/import/recalculation/save ($344), full nested binary edit/system-save/readback (1,545 bytes identical to Windows/Mac); actual APK worker edit/readback passes | Genuine cold restart remains unverified |

Host validation passes 616 tests; real Pyodide executes 519 passing tests with one skip. [Machine-readable acceptance](../qa/native-preview21/acceptance.json) separates generated, installed and UI-tested results.

## Scope

This is a development preview. The independently generated fixtures are not original TurboTax saved returns. Loading requires an explicit supported stream profile and caller-supplied matching registries; protected and unsupported data is refused. Original TurboTax runtime executions and original saved `.tax` fixtures remain zero. Correcting the source does not run the original calculation engine or update its derived values. Complete `.tax` compatibility, native-engine parity, complete filing coverage and electronic filing have not been established.

The App uses independently written code and official IRS rules. Original vendor binaries, resources, decompiler output, private keys and personal returns are excluded. The source includes OpenTax corresponding source and dependency notices under AGPL-3.0-only. Mac is not notarized; Android uses the original development signer and has no INTERNET permission.
