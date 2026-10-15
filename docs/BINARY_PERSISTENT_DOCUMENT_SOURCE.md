# Complete saved-document objects: explicit v6 source profile

The independently written editor now retains the Entity persistent-object list and the separate per-FormSet attribute lists while correcting existing supported fields. These are additional scopes around the already supported ValueForm tails, indexed tables, child forms and links. The editor reads the entire selected Entity, writes a separate corrected copy, reloads it and compares all represented values and structures before allowing a download.

The v6 profile explicitly declares `entity_factory: value_entity` and one `formset_factories` entry for every selected FormSet. It uses the same effective registry to resolve current fields and arrays. Missing factories, duplicate declarations and unexpected object tails are refused. Profiles v1-v5 retain their previous base Entity/FormSet behavior.

Supported raw bodies are FormSet UUID148 and stored metadata151, plus Entity UUID147, legacy length-framed identifier146 and metadata14B versions3/4. Their complete source framing, ordered rows, repeated paths, bodies, capacity and unused relative offset slots are retained. Only absolute stream positions may change. Other classes and unmodeled metadata versions remain opaque; moving them stops export. Adding or editing objects, creating fields and rows, and native metadata migration are not implemented.

Stored metadata is displayed as saved source content. It does not supply active native calculation values, overwrite the current IRS return, execute native setters, or establish current UUID ownership. A separate comparison regression deliberately supplies a stored metadata row named F1040/L39 with an extreme amount and verifies that the approved calculation still derives its actual source-bound result.

Use Documents → Open TaxML / binary .tax → Try independently generated binary samples → Load saved document objects. The fictional sample binds four independently authored registry files and contains two FormSets, eight forms, nonempty tables, child forms, eight links, all eight saved-form tails, three Entity objects and two objects in each FormSet. Correcting the first FW2 WAGES from1234.56 to1234.57 writes an8110-byte complete copy. The other FormSet's wages remain unchanged. This is a source correction; derived source totals are not recalculated.

Source sample SHA-256: `0eae561c6a1056cf6dcbdbf008d433b5ac9eb8a9f977381689d2c9a31c80ea03`.

Corrected copy SHA-256: `c5bdc13fb5bdd8cb435e4e2eaad2fdb21077b5024a28e89e8b1bbcbc0e30ba26`.

Original licensed runtime executions and original taxpayer fixtures remain zero. The supported selected Entity stream is not evidence of complete original .tax container compatibility, complete original recalculation, e-filing or universal native acceptance. No vendor binaries, resources, art or decompiler output are part of this source implementation.
