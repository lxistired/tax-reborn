# Selected derived ValueForm source preservation

The v4 binary profile adds explicit derived ValueForm factories, saved D2 field
identities and all three persistent-object groups to the existing complete
selected Entity reader. It retains the source ordinal and exposes the current
effective field ordinal separately. Numeric edits use the exact full field ID.
It does not run native FixupFields, SetValue, validation events or recalculation.

Profiles v1–v3 keep their format/factory rules. Every profile now validates the
complete Hash topology before `_context` returns any document. The shared pure
`interop/form_core/hash_structure_reference.py` traverses every bucket to NULL,
including next links after a matching field. Cycles, dangling references, wrong
buckets, repeated indices/keys and orphan allocations are refused. Source bytes
are neither repaired nor deleted. Income, filing-status setup, editing and
calculation adapters cannot treat orphan storage as a current value.

V4 keeps ordered XPRF registry validation from v2. It adds `form_factories` for
every selected template, each declaring base_form/value_form and its table kind.
Each ValueForm also requires `compiled_arrays`, with explicit complete visible
and hidden descriptor lists. Current field kind/format/attributes come from the
selected validated effective registry. Array-list population remains caller
supplied; table headers, attributes alone, source D2 and missing lists are not
substitutes. Exact current full-ID membership is required; prefix aliases and
native template conversion/recovery remain unsupported.

Legacy `template_versions` is an explicit U32 expected source checksum. It is
not a tax-year version, not inferred from the imported file, and not automatic
native compiler cache verification. The selected derived wire profile remains
platform7/schema18/release100/share0/swapfalse. Unsupported outer containers and
classes are refused or retained under strict read/write limits.

The existing source-bound amount codec admits scalar kinds11/12. Source kind,
format and shape must agree with current metadata, Used must be set and Override
must be clear before editing. The App changes raw scalar bits only; all source
keys, presence/error flags, tables, children, links, D2 and object bytes stay
bound to their loaded scope. Used/raw0 is distinct from unused/raw!=0. Unknown
used arrays and untyped persistent objects block income review. Array insertion,
deletion, field creation and graph edits remain unsupported.

Only the previously source-proven canonical zccPersistentFormUUID body receives
automatic movement/StringTable-ID permission. Unknown object movement remains
blocked and v4 exposes no class allowlist. Opaque bytes remain inspectable; they
do not establish a native current object. Whole-document readback includes each
tail's exact source bytes and every represented header/node/reference. Runtime
tail positions may change only where the typed body contract permits it.

The independent generic83 raw-kind13 helper's optional exponent edit had used
the wrong dataclass field name. This candidate changes `exponent` to
`exponent_byte` in that helper and includes a regression that writes/reads the
actual byte. Existing frozen83 files remain unchanged. App monetary editing
continues to use the separate kind11/12 amount codec.

`BINARY_DERIVED_FIXTURE_CONTRACT.json` binds the exact owned input/output bytes
and renderer/API fields used for native package acceptance. `derived-income`
supports reviewed W-2/INT/DIV amounts plus a zero child; its existing allocated
array nodes are unused, not claimed as native used rows. `derived-array` includes
Used row1, present zero row3 and unused nonzero row4 and deliberately blocks income
review. `derived-opaque` shows all three nonempty groups and refuses their movement.
No original program, saved taxpayer return, resource or decompiler output is
included. Whole-tax and original-engine acceptance remain unverified.
