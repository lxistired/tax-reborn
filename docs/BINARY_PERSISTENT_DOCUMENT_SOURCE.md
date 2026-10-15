# Complete saved-document objects: explicit v6 source profile

The independently written editor now retains the Entity persistent-object list and the separate per-FormSet attribute lists while correcting existing supported fields. These are additional scopes around the already supported ValueForm tails, indexed tables, child forms and links. The editor reads the entire selected Entity, writes a separate corrected copy, reloads it and compares all represented values and structures before allowing a download.

The v6 profile explicitly declares `entity_factory: value_entity` and one `formset_factories` entry for every selected FormSet. It uses the same effective registry to resolve current fields and arrays. Missing factories, duplicate declarations and unexpected object tails are refused. Profiles v1-v5 retain their previous base Entity/FormSet behavior.

Supported raw bodies are FormSet UUID148, stored metadata151 and complete nonempty version1 instance maps14F, plus Entity UUID147, legacy length-framed identifier146 and metadata14B versions3/4. Their complete source framing, ordered rows, repeated metadata paths, bodies, capacity and unused relative offset slots are retained. Only absolute stream positions may change, with the same stored owner retained. Other classes and unmodeled versions remain opaque; moving them stops export. Adding or editing objects, creating fields and rows, and native metadata migration are not implemented.

Stored metadata is displayed as saved source content. It does not supply active native calculation values, overwrite the current IRS return, execute native setters, or establish current UUID ownership. A separate comparison regression deliberately supplies a stored metadata row named F1040/L39 with an extreme amount and verifies that the approved calculation still derives its actual source-bound result.

Use Documents → Open TaxML / binary .tax → Try independently generated binary samples → Load saved document objects. The fictional sample binds four independently authored registry files and contains two FormSets, eight forms, nonempty tables, child forms, eight links, all eight saved-form tails, three Entity objects and two objects in each FormSet. Correcting the first FW2 WAGES from1234.56 to1234.57 writes an8110-byte complete copy. The other FormSet's wages remain unchanged. This is a source correction; derived source totals are not recalculated.

Source sample SHA-256: `0eae561c6a1056cf6dcbdbf008d433b5ac9eb8a9f977381689d2c9a31c80ea03`.

Corrected copy SHA-256: `c5bdc13fb5bdd8cb435e4e2eaad2fdb21077b5024a28e89e8b1bbcbc0e30ba26`.

Original licensed runtime executions and original taxpayer fixtures remain zero. The supported selected Entity stream is not evidence of complete original .tax container compatibility, complete original recalculation, e-filing or universal native acceptance. No vendor binaries, resources, art or decompiler output are part of this source implementation.

The additional **Load stored instance-map sample** contains one independently
authored type14F body in each FormSet, six stored TPS-address/MEF-path byte pairs in
total, both stored0F and compressedF0/mode4 framing, and the same complete tables,
child forms, links and persistent scopes. The source is8,358 bytes; correcting
the first WAGES field writes8,360 bytes with SHA256
`da0b62b035b3f1332719b9f38428c98eea6d7c0fd48e6f8ee0ae4d6777711a54`.
Every persistent layer moves by two bytes while every original body remains
exact. The UI displays the stored pair count, without using it as an active
native cache or asserting UUID ownership.

The type14F reader checks the complete version/count/blob length, all0F/F0 blocks
and CRCs, every TAB/LF row and both unique key domains. Known nonempty version1
corruption stops inspection. Empty-count and unknown-version bodies retain
their previous opaque behavior and cannot move. A missing or empty stored
body does not prove an empty native cache: native Load cleanup and legacy14D
transfer are separate, unexecuted operations.
