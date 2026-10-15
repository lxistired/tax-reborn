# Binary tax-data workflow — 2026-10-15

The App now inspects supported binary streams, reviews income records, calculates them with its independent IRS engine, and exports a separately corrected binary source. This extends plaintext TaxML. Complete original `.tax` compatibility and original-engine parity remain unverified.

## Use in the App

Open **Documents → Open TaxML / binary .tax**. Choose your source, explicit 2025 binary profile and matching XPRF registries. Declare **Binary tax data — supported profile**. Unsupported or protected input is refused.

For a reproducible test, expand **Try independently generated binary samples**. The income sample has fictional W-2, 1099-INT and 1099-DIV records. Review each owner, employer/payer, amount and scope, then add each record. These use the actual decode/review/calculation/save pipeline. The default synthetic household produces a $344 refund. Income completeness still needs separate confirmation. These are independently generated samples, not original TurboTax files.

The nested sample has a nonempty E1 table header, a child form and four forward/back links. **Inspect / edit binary fields** shows the stored fields and relationships. Numeric corrections create a separate `.taxbin` copy. The complete supported document is read again and compared before export. The original stays attached. Profiles and registries stay attached locally: **View source document → Inspect / correct source** reopens without selecting them again. Attachments are separate from return JSON backups.

## Structures and boundaries

| Area | Implemented behavior | Boundary |
|---|---|---|
| Document | C0 entity, multiple DC formsets, C7/C8 indices and ordinary form records | Platform 7, schema 18, release-format95–100, swap disabled, unstreamed values, explicit template versions |
| Nonempty records | E0/E1 headers, recursive C8 children, D7 descriptors, forward/back links and per-form string IDs | Native table callbacks/controller execution remain unobserved. The independent nonempty-table writer follows recovered reader grammar; current native StoreTables itself writes empty E0. |
| Values | 23-byte nodes, raw64, separate FV presence/override/computed attributes and linked indices | Unknown types remain raw or are refused. Numeric kinds11/12 use separately verified scales. |
| Capacity | 16,000 hash buckets;2,700 nodes per runtime buffer; multiple buffers;65,535 string slots in16,250-slot blocks; multiple chunks;65,000-byte compression frames | Independent safety budgets; no universal legacy/compact/swap/other-compressor support |
| Source editing | Immutable original, selected numeric edits and complete supported-structure readback | Does not run the original engine or refresh derived source totals. Unknown serialized facts that cannot be retained stop export. |
| Income | Bound W-2,1099-INT and1099-DIV records enter the actual App after review | Unknown present tax facts block additions. No ownership or complete-return inference. |

Stream scalars are big-endian; packed nodes and index arrays are little-endian. Source, profile and registry identities are checked separately. Compression and string packing may normalize storage. Semantic readback is not universal byte parity.

## Reproduce

```sh
python3 scripts/create_binary_fixture.py
python3 scripts/build_worker.py
python3 -m unittest discover -s tests -p 'test_binary*.py' -v
node scripts/test_binary_runtime.cjs
```

The worker test uses real Pyodide WebAssembly, shipped decoding code and the App's reviewed-record JavaScript. It checks three income types, the344 USD calculation, source receipts, recursive editing, full readback and retained facts. Native GUI/package acceptance is recorded separately. Canonical independent modules are under `interop/form_core`; the worker builder generates packaged `web/interop` and offline manifests. Vendor binaries/resources/decompiler output/keys/personal data remain private.

## Original calculation work

REA work continues on typed input/cache behavior, mapping to field instances, numeric factories, output commits, FV attributes, ChangedEvent dispatch and global recalculation order. Static bindings and bounded independent helpers do not establish execution of the entire original engine. App tax results still use independently written IRS rules.

Original native runtime executions: **0**. Validated original saved-return fixtures: **0**. Complete `.tax` compatibility and original-result parity remain unverified. Generation, installation, actual UI acceptance, upload and public download are separate evidence states.
