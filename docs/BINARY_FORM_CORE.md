# Binary form-core I/O — 2026-10-15

The independent [form-core component](../interop/form_core/) now reads and writes
an actual byte buffer containing a selected modern form header, section index,
field-value hash and compressed string table. The reader obtains the saved
table ID and section positions from the bytes. It does not require the writer's
object or a separate header/index sidecar.

The selected-record layer also reads and writes the actual E0, C8 and D7 tail
maps when subtables, child forms and links are all empty. This completes an
entire record within that explicit profile. Nonempty structures are refused
instead of being discarded. Entity/FormSet containers and whole `.tax` files
are still outside this component.

This is a bounded interoperability component for the ongoing reconstruction.
The supported application workflow remains reviewed plaintext TaxML import.
The component is not exposed as a complete `.tax` importer, is not included in
the current installers, and does not run the original calculation engine.

## What changed

| Area | Verified result | Limit |
|---|---|---|
| Header and sections | C4/CB header, saved table ID and relative C9 offsets are parsed from one byte buffer. | Prepared current table ID, parent lookup and selected stream profile. |
| Field values | Real hash buckets, linked indices and 23-byte wide, noncompact node records are written and read. Numeric payloads and value attributes survive a string edit and another save/load. | At most one buffer with 64 nodes and 128 buckets. Unknown kinds remain raw records. |
| Strings | Raw and F0/mode4 blocks, CRC, table storage and string-handle repair are implemented independently. | One 512-byte string chunk and 64 handles. Only exact kind 7 is interpreted as a string. |
| Selected complete record | Core plus three actual nine-byte empty tail maps can be read, edited, written and read again. | Empty subtables/children/links only. This does not establish universal form compatibility. |
| Compressor | One installed original resource decodes to 3,161 bytes; independent re-encoding reproduces its 403-byte compressed payload exactly. | One resource/profile. Other authored roundtrips do not establish universal native encoder parity. Original payloads stay private. |
| Error handling | Corrupt string CRC returns the source-bound error; truncated or unsupported profiles are refused. Unparsed tail bytes are reported by the consumed length. | Some bounds are deliberately stronger than the native parser. They are component eligibility checks, not invented native error codes. |

The selected profile is version 18 or later, wide indices, noncompact values,
big-endian scalar stream fields, little-endian packed nodes and index arrays,
and processor swap disabled. Successful buffer allocation is modeled; the
component neither allocates vendor memory nor calls a vendor binary.

Nonempty subtables, child forms, links and the higher Entity/FormSet container
remain separate work. A successful core read does not mean the remaining record
or whole `.tax` file was parsed. The core's `consumed` identifies its end and
`whole_form_proven` remains false. The selected-record API separately reports
`entire_selected_form_record_consumed`; this is true only when it consumed the
exact record within the stated empty-tail profile. Whole `.tax` compatibility
always remains false.

## Reproduce the independent I/O checks

From the repository root:

```sh
python3 -m unittest discover -s tests -p test_binary_form_core.py -v
node scripts/verify_binary_form_core.cjs
```

The thirteen acceptance cases use only authored data. They cover byte-only reading,
an edit/write/reload cycle that preserves another numeric field, field
attributes, nonzero stream positions, a compressed 509-byte string, CRC
corruption, truncation, unknown value kinds, an explicitly unparsed tail,
complete selected-record editing and refusal of nonempty child records.
The same cases pass in native Python and real Pyodide WASM Python. The Pyodide
receipt is [saved here](../qa/binary-form-core-pyodide-20261015.json).

The runtime comprises eight independently authored standard-library modules.
Original executables, resources, decompiler output, keys and taxpayer files are
not dependencies. The private REA evidence was independently checked against
original instruction bytes, import bindings and relevant exception metadata;
the public integration changes local Python imports to package-relative imports
without changing the codec logic.

## Calculation reconstruction remains separate

The Windows trace now binds successful normal form creation to its ordinary
field-write class, and follows actual input, constant and calculated-node
dispatch bodies. The current-input reconstruction also separates the typed
input cache from the instance-vector cache. A scalar read does not populate
the instance vector, and multiple cached entries can force scalar fallback.

Those traces do not establish complete engine execution. Concrete mapping,
rendering, global invalidation, dependency order and physical writeback still
have unresolved paths. In particular, the hidden PR1040 and `__POR__` fields
have native integer kind 10. Supplying a Boolean in a finite replay does not
prove their original scalar-to-predicate conversion.

Original native runtime executions: **0**. Validated original saved-return
fixtures: **0**. Complete original `.tax` compatibility and original tax-result
parity remain unverified. The independently implemented IRS tax core is not
expanded merely because a static native trace was recovered.

Installer status is unchanged: preview.12 remains the verified public release.
Preview.20 candidate Windows and Mac checks are recorded separately; its
physical Android installation, data retention and new-flow UI acceptance remain
pending while no USB device is connected. This component update does not claim
a newly built, installed or published application package.
