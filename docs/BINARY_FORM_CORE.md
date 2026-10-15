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
| Nonempty records | E0/E1 base headers or explicitly declared derived `ValueTable` headers, recursive C8 children, D7 descriptors, forward/back links and per-form string IDs | Existing indexed values and the derived table's saved last-used record index are preserved. Runtime row allocation, persistent-record UUID objects, row insertion/deletion and native row rebuilding remain unsupported. |
| Values | 23-byte nodes, raw64, separate FV presence/override/computed attributes and linked indices | Unknown types remain raw or are refused. Numeric kinds11/12 use separately verified scales. |
| Capacity | 16,000 hash buckets;2,700 nodes per runtime buffer; multiple buffers;65,535 string slots in16,250-slot blocks; multiple chunks;65,000-byte compression frames | Independent safety budgets; no universal legacy/compact/swap/other-compressor support |
| Source editing | Immutable original, selected numeric edits and complete supported-structure readback | Does not run the original engine or refresh derived source totals. Unknown serialized facts that cannot be retained stop export. |
| Income | Bound W-2,1099-INT and1099-DIV records enter the actual App after review | Unknown present tax facts block additions. No ownership or complete-return inference. |

Stream scalars are big-endian; packed nodes and index arrays are little-endian. Source, profile and registry identities are checked separately. Compression and string packing may normalize storage. Semantic readback is not universal byte parity.

The ordinary native value-form factory builds a derived value table. Its table
reader consumes an additional unsigned16 saved-record boundary for Entity schema
13 or newer; its current writer writes that boundary after the base header.
The v3 profile requires an explicit per-form `table_factories` declaration; the
v1/v2 base-E1 profiles continue to refuse this extra data. Entity schema alone
does not identify the table class: the native form factory selects it. The new
indexed-table sample retains a used amount, a present zero, an unused nonzero
payload, a derived table boundary, one child form and four links during a scalar
source correction. The editor shows the boundary and indexed values as read
only. Unknown present array values block income additions. This does not create
native runtime records, persistent UUID objects or recalculate the boundary.
The original schema comes from the C0 header; it is separate from the tax year
and release number.

Profiles v2/v3 also bind the exact priority order of multiple registry files.
Metadata version selection and visible/hidden field origins are resolved before
loading stored field ordinals. The profile's template checksum remains supplied
by the caller; it is not inferred from the wire or replaced by a metadata version.
The App shows each field block's source identity and retains all selected files
for reopening. No original registry data is bundled with the App.

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
