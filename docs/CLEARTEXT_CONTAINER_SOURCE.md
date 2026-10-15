# Complete, explicitly cleartext container corrections

The App can now inspect a selected cleartext ZIP32 container, review its supported TaxML income forms and save a corrected **complete archive**. It preserves the original manifest bytes, other stored documents, unreferenced members, archive and member comments, timestamps and all unselected local ZIP records. Only the selected TaxML payload and the required CRC, lengths and local-record positions change. Every member is reopened and checked before export.

The original PersistenceContainer constructor defaults to encryption. This feature requires an explicitly selected **cleartext** source and does not decrypt default original files. Manifest security or unbound identity contexts, encrypted data, ambiguous TaxML documents and unsupported ZIP variants are refused. Original program executions and original taxpayer-file fixtures remain zero. General original `.tax` compatibility and original calculation parity are not established.

## Use it

1. In Documents, choose **Open TaxML / binary .tax**.
2. Open the independently generated samples and choose **Load plaintext container sample**. For your own supported source, select the file, its explicit TaxML profile, its caller-owned XPRF carriers and **Cleartext container — preserve complete archive**.
3. Check the selected TaxML member and stored-document report. Other payloads are preserved source content; they do not become active tax data.
4. Review a supported W-2, 1099-INT or 1099-DIV. Adding a reviewed record uses the existing IRS calculation and local-save workflow.
5. To correct source amounts, confirm the source review and choose **Download corrected container**. The system saves a separate `.zip` copy. Source tax totals are not recalculated. The original attachment and current App return remain unchanged by source export.

The built-in archive contains one independently authored TaxML document, one stored-only experience XML document, one unknown stored-only document and one unreferenced member, plus the manifest. Its TaxML uses the existing source-bound Windows XML shape with `OwnedSet`, `OWNED`, checksum `1` and version `owned`; these values are explicitly unregistered. This is not proof of native Mac factory acceptance or an original saved return.

## Source and integrity boundaries

Private REA evidence binds the original manifest namespace, filename, document type/key fields, five item-type URIs and actual read/save dispatch. Type0 is TaxML; raw C0 Entity bytes must not be relabeled as that document type. Raw original code and resources remain outside the repository. The shipped parser and writer are independently written.

The finite profile accepts single-disk ZIP32, stored or raw-deflate members and complete supported data descriptors. It validates every local record, central record, name, size, descriptor and CRC, including unreferenced data. ZIP64, SFX prefixes, padding, unsupported flags, malformed extras and ambiguous directory structures are refused. Unknown extra metadata remains stored but cannot authorize editing that member or moving opaque positions. No-op returns the exact source bytes.

Manifest editing is authorized separately from raw archive preservation. Unmodeled root/document attributes, extra metadata, CFP/version fields, relationships or structure text block both review and correction. Inspection can retain and display this source, but cannot grant write permission from unknown metadata. Comments, processing instructions, whitespace and the selected known empty security/identity contexts remain permitted.

The manifest is strict UTF-8. NUL, other declared encodings, DTD/entity syntax, wrong namespaces, nonempty security/identity contexts, case collisions and ambiguous type/key bindings are refused. Selecting a document requires one exact bound TaxML type. Unknown document types never receive TaxML editing permission.

## Validation state

The source candidate passes 727 host checks and 616 actual Pyodide executions, with two explicit skips. Actual Chrome desktop HTTP/SQLite and 390px Pyodide/IndexedDB flows open the complete source, review all three income types, retain the existing income record, recalculate the fictional $344 refund, save/reload, restore JSON, refuse duplicate imports and download/read back the complete corrected container. The built-in sample entry also passes in both modes.

Those browser flows change selected interest100.23→101.24 and save the same1,584-byte archive. The separate actual dedicated worker changes W-2 wages1234.56→1234.57 and returns1,590bytes, SHA-256 `93c85dcbe28a57703ccd2bc25e939f05780e21eae17cfeef172ba534e071b7cf`. Both preserve all four unselected local ZIP records and the other complete XML form sections. Source editing leaves the current return unchanged. The separate source-comparison worker still passes actual main-App desktop/mobile checks.

Native Windows, Mac and Android installation/system-save acceptance is recorded separately. A source/browser result does not establish those platform states or public package availability.
