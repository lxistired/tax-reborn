# Complete selected saved-form records

The v4 binary profile extends the working source editor to the selected modern
ValueForm record. It reads the base form, indexed table headers, child forms,
links, saved field identities and all three persistent-object groups from one
complete Entity buffer. The explicit source profile selects the form class;
trailing bytes and a schema number are not used to guess it.

From **Documents → Open TaxML / binary .tax**, expand the independent samples:

- **Load complete saved-form sample** contains four forms, one child, a nonempty
  table, four links, saved field maps and typed saved UUID objects. Its original
  WAGES field number is 104 while the supplied current definition uses 4. The
  editor binds the full field ID and preserves the original saved number.
- **Load saved-form array sample** additionally carries a used indexed amount,
  a present zero and a nonzero unused amount. Their bytes and saved table
  boundary are retained. Unknown present array facts block income additions.
- **Load preserved-object sample** includes nonempty form, record and value
  object groups. Uninterpreted bodies remain inspectable and retained; they
  block income review and relocation when their semantics are unknown.

Use **Inspect / edit binary fields** for a supported numeric correction. In the
complete-form sample, changing WAGES from 1234.56 to 1234.57 writes a separate
2,906-byte file. Four UUID-bearing tails move by 2 bytes. Their saved maps,
UUID bodies, table, child, links and every other parsed fact stay unchanged.
The complete file is read again before export. The original remains attached.

The reader distinguishes allocated storage from a field reachable through the
actual hash chains. All binary profiles validate every complete chain before
income review, filing-status setup or source correction. Unreachable records,
wrong buckets, cycles, invalid links and duplicate keys stop the finite source
profile. This fixes the preview.23 disconnected-node import issue. The guard
does not repair or drop source data, and does not establish that all native
hash variants are supported.

## What this preserves

The selected derived tail includes the D2 field map and the D1/DE/DF form,
record and value object maps. Each object retains its class, attachment and
bounded body. A source-checked canonical FormUUID body has no file-offset or
string-table reference and may move. Unknown object bodies require their
original location and identity namespace; movement is refused otherwise.

The supplied current metadata must bind each saved full ID, kind, format and
explicit array context. A current field number is separate from its saved
number. Correcting a scalar does not execute native FixupFields, generate new
records, run events or refresh original derived tax totals.

## Remaining boundaries

This profile selects platform 7 / schema 18 / release 100 / share 0 with the reconstructed
byte order and compression. Other containers, classes and variants are refused.
The sample files and registries are independently authored. Actual original
runtime executions and original saved-return fixtures remain zero. Complete
`.tax` compatibility, original-engine parity and electronic filing remain
unverified or unavailable.

Reviewed income continues into the App's independent IRS TY2025 calculation.
The original-program research and comparison evaluator are separate from that
working tax core. Vendor executables, program resources, decompiler output,
keys and personal returns are excluded from the App and source archive.
