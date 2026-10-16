# Preview 36 — read saved links and stored interest values in the App

Documents now checks an existing saved link against the complete source, owner, saved/current field mapping and destination. It exports a source-bound, read-only audit. The independent included example contains one consistent link and can be opened without original resources.

A second Documents workflow reads one existing interest value from a complete saved source and matching caller-local registries and calculation resources. It builds its own form identity, row map and shared value cache, and reports the amount, Used, Override and Error facts. It distinguishes missing or unused storage from a present zero. It supports the reviewed L1, L3 and EXINT scope; unsupported files and mismatched resources are refused. Original resource files are supplied locally and are never included in the release.

Both workflows retain the current independent IRS return. Changing a source, profile, registry, selected field or current return invalidates the result; late replies cannot restore a stale report. Reports contain the verified source facts and context hashes rather than original calculation-resource payloads.

## Current verification

The source passes 812 host checks and 701 actual Pyodide executions, with two explicit skips. Actual main App file-input, Worker execution, report download, independent complete-source readback and unchanged saved-return checks pass with HTTP/SQLite and Pyodide/IndexedDB. Native Windows, Mac and Android acceptance is being recorded separately; source tests alone do not establish platform acceptance.

## Limits

These are read-only source workflows. They do not recalculate the original final tax, propagate edits through original links, restore the complete original row inventory, or establish original engine parity. The original complete encrypted .tax archive, complete interpreter and native lifecycle remain unfinished. Original licensed runtime executions and original taxpayer fixtures remain zero. Existing independent IRS calculations, forms, source editing and local saved data remain included. Electronic filing, Intel Mac and native iOS acceptance are not claimed.

Maintainer [@lxistired](https://github.com/lxistired). See [the workflow details](SOURCE_VALUE_DIAGNOSTICS.md) and [source validation](../qa/native-preview36/source-validation.json).
