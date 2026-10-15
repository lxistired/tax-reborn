# Preserved saved value notes and destination references

The explicit v4/v5 ValueForm reader recognizes two additional saved value
object bodies. A validated body can remain byte-for-byte unchanged when a
scalar correction moves the form's saved tail. Every instance is checked in
the shared document loader before inspection, income review or editing.

`ztbPersistentValueTag` stores version 1, a U16 length and raw text bytes. The
reader requires an exact complete body and rejects embedded NUL text. It
preserves high-bit bytes without assuming UTF-8. The native empty Store writes
only its version, while its version-1 Load also expects a length. This reader
accepts a complete four-byte version/zero-length source and copies those four
bytes unchanged. It refuses the ambiguous two-byte form and does not claim
native writer parity. No body text editing or native object creation is added.

`zcvPersistentRecordOrder` stores a marker, 15 raw FormSetID bytes, a destination
ID and two U16 indices. It is a **value object in group 2**. Its name does not
make it a record-row serializer. Bytes after a FormSetID NUL, full ID padding
and original short/legacy ID encodings are retained. The destination reference
is displayed for inspection; native destination resolution is not executed.

The existing form UUID reader remains unchanged. Unknown record/value objects
remain visible as preserved opaque bytes, block income review and block an
export that would move them. A known class with a malformed body is refused;
a valid first instance cannot grant permission to a malformed later instance.

Source/current field identity, saved checksums, explicit form/table factories,
automatic array suppliers, complete hash-chain validation and Used/Override
guards keep their existing contracts. The correction uses a full field ID and
preserves the source ordinal. It changes only the selected source scalar.
Original calculation, callback execution, new field/row creation, unknown
object relocation and general `.tax` compatibility remain outside this scope.

The `Load saved value-note sample` example uses fictional data and independently
generated carriers. Its four forms include ValueTables, a child, four links,
form UUIDs and both value-object types. The exact input/output expectations are
in `BINARY_TYPED_VALUE_FIXTURE_CONTRACT.json`. The existing read-only source
comparison includes the new parser dependency in its checked runtime manifest;
its calculation profile and authority rules are unchanged.
