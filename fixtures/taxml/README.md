# Independently authored TaxML examples

All examples are synthetic and contain no actual taxpayer data. They are not original saved returns. Original-program executions and original-program acceptance are zero.

The `synthetic-modern-windows-*` example uses the source-bound current Windows XML shape with an independently authored XPRF carrier. `OwnedSet`, the `OWNED` subtype, checksum `1` and implementation version `owned` are unregistered example values, not original template registrations. The explicit profile binds the XML formset name separately from the XPRF internal formset identity.

In Documents → Inspect TaxML, choose the XML, declare Plaintext TaxML XML, choose the matching wire-profile JSON and XPRF, and acknowledge the profile. Review the six dollar amounts, enter the employer and owner, and explicitly establish Boxes 7 and 10. Add the W-2 to a local draft, or download a corrected XML copy containing only Boxes 1–6 edits.

Corrected XML keeps the original source as an attachment. It does not recalculate the source return, rebuild encrypted containers, update template checksums, or establish original-program loadability. Unknown fields, ambiguous copies and unresolved flags block candidates and export.

The App example uses copyNum1/fileCopyNum1. Original field serialization can encode copyNum0, but the loader has a separate IsMulticopy guard. The App refuses copy0 until the actual factory binding is verified. Pure shape-reader tests and historical copy0 synthetic tests do not establish original acceptance.

The `synthetic-native-interest-*` specimens are independently authored four-box F1099I XML/XPRF inputs. Select the matching XML, profile and carrier. Review Boxes1,3,8,4, enter the payer and explicitly confirm the supported interest situation. The local record stores taxable Box1+Box3, exempt Box8 and withheld Box4, while retaining the reviewed four boxes separately. These specimens are not original TurboTax saved returns.

The `synthetic-native-dividend-*` inputs exercise six F1099D boxes:1a,1b,2a,2b,2d,4. Choose the XML, matching profile and caller-owned XPRF, review the payer, qualified eligibility and supported situation. The reviewed snapshot is retained separately from current editable amounts. Boxes2b/2d are included in Box2a, and withholding uses L2. These are owned synthetic inputs, not original saved returns. See [the migration contract](../../docs/TAXML_DIVIDEND_IMPORT.md).
