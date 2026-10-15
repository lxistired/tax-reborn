# Arrays from the same selected registry

Binary profile v5 keeps the explicit selected effective templates, ordered
SHA-verified carrier files, expected source checksum, and per-template form/table
factories from v4. It obtains array definitions from the selected carrier bytes.
It does not accept `compiled_arrays` in the profile. Profiles v1–v4 keep their
existing contracts, including v4's explicit caller-supplied array lists.

`Registry.from_effective_xprf(..., load_array_payloads=True)` validates every
complete carrier directory/frame/SHA before the independent registry receives
any resource. One immutable effective registry supplies both current fields and
arrays. The existing79 selected-primary check runs before array lookup. Each
selected template uses the first present2000 and2001 resources in its ordered
DataHomes independently; the two blocks can come from different files and RIDs.

The source report is available at
`inspection.registry_binding.selected_array_templates`. Every block records
presence/authoritative absence, carrier SHA, RID, metadata type, payload byte
count/SHA/cursor, and every descriptor's exact encoded ID and eight metadata
bytes. Byte27 remains uninterpreted and retained; it is not set to zero. The
entire canonical profile and ordered carrier identities remain bound by the
existing source receipt. There is no new user assertion about array contents.

The selected subset is the source-proven modern Mac little-endian attribute
payload format. An empty byte payload, truncated record, trailing payload, index
wrap, wrong selected primary or mismatched source tail is refused. A present
U16zero is a valid empty block and stops fallback. An absent block is a complete
empty list only because the supplied resource directory is complete. A source
node requiring array-shape recovery against the actual definitions is refused
by v5; native recovery callbacks are not simulated.

The App still preserves source ordinals. A saved field number104 can bind to
current number4 only through the full D2 field ID. Exact current kind/format,
Used, Override, complete Hash reachability and all existing source-scope edit
guards remain in force. Known scalar amount edits preserve tables, children,
links, D2 and object bodies. Unknown used arrays block income review; array row
creation/deletion and unknown object movement remain unsupported.

The owned `auto-array-income` sample has visible2000/RID1 in one file and
hidden2001/RID3 in another. Their byte27 values2 and1 survive the source report.
The sample has four complete derived forms, a ValueTable, a child, four links
and four typed FormUUID tails. Editing WAGES1234.56 to1234.57 yields2906 bytes
with SHA179560f55862259878bdb45f8efe076e25c841d4425055618a579a2befa58b25.
The complete readback preserves both array source reports and every unrelated
represented section. `auto-array-used` and `auto-array-opaque` exercise the same
conservative boundaries as their v4 counterparts.

The UI button is **Load automatic table sample**. Its inspection has
**Automatic table definitions · 2** with separate attached-file provenance.
No original resources, saved taxpayer files or decompiler output are included.
No native current registry/cache, FixupFields, missing-field/row/UUID creation,
original validation events or original recalculation runs. Arbitrary outer
containers and original saved `.tax` compatibility remain unverified.
