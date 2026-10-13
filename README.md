# Tax Reborn · Project #000002

A local, working US personal-tax preparation preview, researched against TurboTax Desktop2025 and its official mobile demonstrations. It calculates actual 2025 federal taxes, stores separate returns, imports reviewed documents and CSV records, prepares state calculation drafts and exports preparation records. Maintained by [@lxistired](https://github.com/lxistired).

This is independent source code. The completed REA wave-3 checkpoint includes 430 original desktop main-function dossiers, 4 native shell bodies, 41 desktop JVM methods, 18 native printing/PDF preparation functions, plus 38 Java method bodies and 12 original ELF function dossiers in a signature-verified historical 2019 Android APK. These are static evidence counts, not recovered paid-feature or tax-formula counts. Further batches continue; see [the checkpoint and remaining scope](docs/REA_WAVE3_CHECKPOINT_20261013.md). Federal tax formulas were independently implemented from IRS rules. The state worker integrates the pinned open-source Invaro OpenTax engine. No Intuit account, licensed vendor binary, vendor artwork, hosted tax API or remote inference is required by the application.

**Status: functional development preview; a complete TurboTax substitute and filing packet have not been established.** Supported arithmetic, complete paperwork and submission are separate checks. Unsupported situations are reported in the return instead of silently marked complete. Electronic filing, tax payment, expert representation and IRS acceptance are unavailable. The calculation year is2025, not2026.

## Working workflows

- Five filing statuses; taxpayer/dependent eligibility and optional local identity details.
- W2 wages/withholding, interest, dividends, ordinary brokerage sales and loss carryovers, qualified dividends, sole-proprietor business/SE/QBI, ordinary retirement and Social Security.
- Standard or supported itemized deductions, Schedule1-A tips/overtime/car-interest/senior deductions and estimated payments.
- EITC with the official2025 IRS table; NIIT, AMT and ordinary passive rental worksheets; IRA/HSA contributions, education credits and Marketplace1095-A reconciliation.
- Form2441 dependent-care credit and W2 Box10 employer benefits; Form8880 Saver credit; ScheduleR elderly/disabled credit; qualified employer disability before minimum retirement age reported on Form1040 line1h. Each module requires explicit eligibility facts and blocks unsupported variants.
- Multi-return local saving and reopening. Desktop uses private SQLite outside the application bundle; the offline/mobile mode uses on-device IndexedDB. JSON backup restores to a new copy; CSV import appends records for individual review. Every W-2 has a stable local identity and separate review state; changing its actual values clears only that record's review. Local source links, saving/reopening and JSON backup restoration are tested.
- Reviewed investment cost-basis corrections: replace the selected lot's absolute basis, recalculate actual tax and retain its stable identity and history through save/reopen and JSON backup. Repeated corrections and stale/conflicting proposals are checked. See [the original contract, working feature and acceptance](docs/INVESTMENT_BASIS_CORRECTIONS.md).
- Local image OCR and text-PDF W2 extraction. The existing synthetic camera-photo workflow passed actual Android extraction, review, saving and reopening; see [camera checks and limits](docs/OCR_CAMERA_ACCEPTANCE_20261013.md). The user reviews every candidate before it enters the return. Scanned PDFs require an image or manual entry. Attachments are stored separately and are not part of the JSON backup.
- 31 full-year-resident state draft composers, with state adjustments, notes, missing situations and rule proofs. This is an open-source integration, not a claimed recovery of Intuit's state engine. Part-year/nonresident returns and other states are not covered by this interface.
- Computed Form1040 lines, detailed workpapers, JSON/HTML export and an interactive official IRS2025 Form1040 PDF draft. Entered identities, filing-status/dependent/age/blindness choices, refund accounts and designees are filled and read back locally. The separate official paper packet includes applicable supporting forms and reports missing facts. Taxpayers sign on paper and attach required original withholding documents.

The live source of truth is `/api/schema` → `capabilities.coverage` and the returned `blocking_issues` / `form_readiness`. Inspect [coverage-20261013.json](docs/coverage-20261013.json), [validation](docs/validation.md), [credit validation](docs/CREDIT_MODULES.md) and [REA evidence](docs/REA_CASE.md).

## Run and build

Use Python3.12+; desktop build pins are in requirements-desktop.txt. Development server: `python server.py --port 8782`. Native window: `python desktop.py`. Open `http://127.0.0.1:8782/?offline=1` to exercise the mobile engine and on-device storage. Use synthetic examples for testing.

- Federal tests: `python -m unittest discover -s tests -v`.
- Packaged API test: `python desktop.py --smoke-test --smoke-report qa/api-smoke.json`.
- Federal calculation and form tests in real WebAssembly: `node scripts/test_pyodide.cjs`. The 10 W-2 and 8 investment host HTTP/SQLite integration checks run in native Python; separate real browser checks cover on-device preparation metadata and persistence.
- State adapter: `node scripts/test_state_bridge.cjs`. The upstream196 state tests are separate from our federal acceptance and our limited independent state examples.
- macOS/Windows native build: `python scripts/build_desktop.py --work-dir <temporary-path> --output-dir dist/expanded`. Build on the target OS; macOS cannot cross-compile a verified Windows installer.
- Android build: `python scripts/build_android.py --sdk <existing-SDK> --java-home <JDK> --work-dir <private-build-path> --output-dir dist/expanded`. Development signed, API26+, target35, no INTERNET permission. Camera and document save/open actions are initiated by the user. Native iOS Simulator and unsigned device builds have been produced; Simulator calculation/save/relaunch passed. Real-iPhone Files/camera acceptance and signed distribution remain open.
- Pinned state source rebuild: `python scripts/build_state.py --work-dir <temporary-path>`.

No private signing keystore, original vendor artifact or user return should enter this repository. QA artifacts contain only synthetic returns and source-based expected values. A local MacDMG is not notarized; an Android development APK is not a store release. Actual build hashes and executed checks are in the corresponding `dist/expanded/build-manifest-*` and `qa/` files.

## License and attribution

Tax Reborn #000002 is AGPL-3.0-only because its state worker incorporates Invaro OpenTax. The original independent-code MIT notice is retained, together with authentic dependency notices and OpenTax corresponding source under `vendor/`. The separate [Ledger Reborn #000001](https://github.com/lxistired/ledger-reborn) project remains MIT. This project is not affiliated with Intuit, TurboTax or the IRS.

Native previews and source downloads: [native build artifacts](https://github.com/lxistired/tax-reborn/actions/workflows/native-build.yml). Maintainer: [@lxistired](https://github.com/lxistired). See [REA evidence and limits](docs/REA_CASE.md), [official paper forms](docs/OFFICIAL_FORMS_2025.md), and [actual platform checks](docs/PLATFORMS.md). Android preview updates must reuse the original private development signing keystore; the key is never included in the public source. The iOS device app is unsigned and needs your own Xcode signing identity.

The latest source batch passes 361 Python checks and 8 new actual browser groups for basis correction, persistence and paper-fact isolation. The earlier W-2 batch has its own 9 browser checks. See [basis acceptance](qa/basis-correction-acceptance-20261013.json), [native analysis](docs/REA_NATIVE_PROGRESS_20261013.md), [historical Android evidence](docs/REA_ANDROID_STATIC_20261013.md) and [W-2 review metadata](docs/W2_REVIEW_METADATA.md). Native receipts are tied to their recorded source/build; a newer source change requires a new package check.
