# Tax Reborn 2026.10.13-preview.2

The working application targets US tax year 2025. This is an independent tax-preparation preview researched with REA against shipped TurboTax desktop resources and official mobile demonstrations. It is not a verified full TurboTax replacement or an established pixel-identical reconstruction. It does not bypass Intuit activation.

## Executed verification

- Federal engine: 264 tests passed, including 220 independently derived acceptance cases and 44 core cases. The same 264 tests passed in the bundled Python/WebAssembly runtime. Frozen source hashes are recorded in `final_validation_20261013.json` and match the final packaged tax modules.
- Mac ARM64: a real `.app` and DMG were built. Ten checks passed in the actual frozen executable. The GUI created and saved a synthetic return. Changing W2 withholding from $6,500 to $7,000 increased its refund from $1,413 to $1,913. The preview.2 GUI reopened that saved return after quitting the earlier build.
- Android 15 physical device: preview.1 was manually installed by the user. Its packaged engine calculated the same $1,413 refund; GUI editing withholding produced $1,913; saving, force-stopping, starting again and reopening retained that amount. The Android system document picker saved a 25-page PDF draft, and its actual Form1040 fields were read back and visually rendered. Preview.2 was installed as an update and its installed version was independently read back; its GUI reopened the existing $1,913 return. Both APKs request no INTERNET permission. Phone camera capture and on-device OCR recognition were not separately completed in this acceptance pass.
- Offline browser: the local HTTP server was stopped, then the page was cold-reloaded. The federal engine loaded, saved inputs were reopened and changed, and a PDF draft downloaded. After correcting the bundled worker/cache path and asynchronous document button handling, a further cold reload recognized all seven populated W2 fields in a synthetic image. Readable-PDF extraction preserved the sample's cents. JSON export and restore created a new UUID, preserved the original return and recalculated the $7,154 MFJ refund.
- State integration: 31 full-year-resident composers are available from the pinned AGPL OpenTax source. Eight adapter checks and 196 upstream state tests passed. An Illinois GUI example calculated $2,834 tax and a $166 refund on $3,000 withholding, then reopened with those inputs. This does not establish independent validation of every state.

## Preview.2 repair

The document-extraction button previously read `event.currentTarget` after an `await`, when DOM event dispatch had already cleared it. That secondary exception concealed extraction errors and left the button disabled. The repaired handler retains the button before awaiting and restores it in `finally`. The static offline cache version is now `tax-reborn-ui-2025-preview-9`.

## Remaining delivery boundaries

The app supports real federal arithmetic, eligibility checks, local records and preparation exports. Its coverage is described in `coverage-20261013.json`, the source schema and per-return blocking issues. Identity presence is not identity verification. Supporting schedules are calculation workpapers; the complete signed set of official filing forms, Form2210 penalties, electronic filing, payment and IRS acceptance are not implemented. Foreign/K1/farm and other listed complex situations remain blocked.

The Mac build is ARM64 and is not Developer-ID signed or notarized. Android uses a local development signature, not a store release. Windows packaging scripts exist, but a native Windows build and GUI test have not been executed. No native iOS application has been built. The responsive PWA is a separate delivery. Tax Reborn source and downloads are local at this checkpoint; no public Tax Reborn GitHub release is claimed.

The complete Tax Reborn source distribution is AGPL-3.0-only and includes OpenTax corresponding source and authentic third-party notices. Ledger Reborn #000001 remains a separate MIT project. All acceptance data and screenshots in this source tree are synthetic.
