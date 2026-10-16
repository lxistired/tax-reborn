# Preview 36 — candidate acceptance and publication plan

Preview 36 adds two read-only Documents workflows. The saved-link audit checks an existing link against the complete source, owner, saved/current field mapping and destination. The stored-interest workflow reads one existing value from a complete saved source and matching caller-local registries and calculation resources. It reports amount, `Used`, `Override` and `Error` facts, distinguishes a present zero from missing or unused storage, and supports the reviewed L1, L3 and EXINT scope.

The workflows are source-bound. A changed source, profile, registry, selected field or current return invalidates the result. Reports retain verified source facts and context hashes without shipping original resource payloads. They do not recalculate the original final tax, propagate edits through original links, reconstruct the complete original row inventory or establish original engine parity.

## Candidate verification

The runtime candidate is commit `03ce23e85535ccd4140bc9369806b0600b8d0434` (`2026.10.16-preview.36`, UI cache `tax-reborn-ui-2025-preview-56`). The final reviewed source commit also includes the QA and documentation files described below. The runtime passed 812 host checks and 701 actual Pyodide executions, with two explicit skips. The fresh main App passed file input, worker execution, report download, independent complete-source readback and unchanged saved-return checks in both HTTP/SQLite and Pyodide/IndexedDB modes.

The native candidate also passed the recorded Mac ARM64, Windows x64 and Android workflows. Mac and Android used complete caller-local `fdidt`/`fdittx` resources and seven registries in a real GUI positive run, then independently read back the 31,638-byte source-value report and the 3,708-byte stored-link audit. Mac normal close/reopen retained 17 returns and 16 metadata rows. Windows passed 21 installed frozen checks and 23 native GUI workflows, including real stored-link system save/readback; its original-resource MC positive check remains false and its sourceMC evidence is limited to the kernel and invalid-resource/tamper refusals. Android passed the installed original-signer APK check, both GUI file-selection/worker/system-save workflows and one byte-equal 33,114-byte seven-section backup before/after pair. The normal Android GUI reopen check retained the $344 result; it did not generate a second full backup. The 371 files in the tested candidate App web payload are byte-identical across the Mac, Windows and Android packages.

These native results are recorded in the public-safe summary [native acceptance](../qa/native-preview36/acceptance.json). Full reports, device backups, screenshots that contain private return state, and detailed private receipts remain outside the source tree. The Windows source-value boundary is explicit: its positive checks cover the independent kernel and invalid-resource/tamper refusals; they do not establish a positive original-resource run. No platform result establishes original-engine parity.

## Publication gate

The public release remains Preview 35. Preview 36 has not been uploaded, tagged or published. The exact source-sync policy is [source-sync-allowlist.json](../qa/native-preview36/source-sync-allowlist.json), and the nine planned release assets are [release-assets-plan.json](../qa/native-preview36/release-assets-plan.json).

Before publication, the source ZIP must be generated from the exact tracked blobs at the final reviewed source commit, with per-file CRCs and full-file hashes. The extracted App must repeat the two storage-mode workflow and independent readback checks. The final eight preceding assets and the source ZIP must then produce `SHA256SUMS.txt`. Only after publication may all nine release URLs be fetched anonymously and compared byte for byte with the tested files; the release is complete only when all nine public GETs pass. No private receipt, original resource, vendor binary, signing key, device backup or real taxpayer fixture may enter the public assets.

## Boundaries

Original licensed runtime executions and original taxpayer fixtures remain zero. Complete original `.tax` compatibility, complete original calculation parity, electronic filing, payment, expert representation and IRS acceptance remain unavailable or unverified. The calculation year is 2025. This is a functional development preview, not a complete TurboTax substitute or filing packet.

Maintainer [@lxistired](https://github.com/lxistired). See [the workflow details](SOURCE_VALUE_DIAGNOSTICS.md) and [source validation](../qa/native-preview36/source-validation.json).
