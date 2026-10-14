# Six-box 1099-DIV migration into a local draft

Documents → Inspect TaxML offers a supported F1099D candidate from declared plaintext XML and a caller-owned, hash-bound XPRF registry/profile. Review the original document, enter the payer and confirm the household, qualified-dividend eligibility and supported situation. Adding a candidate retains existing interest, dividend and W-2 records. Income completeness remains unconfirmed.

| Source box | Bound field | Local fact |
| --- | --- | --- |
| 1a | L1B | Ordinary dividends |
| 1b | QDIV | Qualified dividends, included in Box1a |
| 2a | L1C | Capital gain distributions |
| 2b | L2C | Unrecaptured section1250 gain, included in Box2a |
| 2d | L1CTX | Collectibles gain, included in Box2a |
| 4 | L2 | Federal withholding |

The six fields are scalar kind11/default-format amounts. XML text expresses dollars. The 39-byte metadata rows and corresponding original mapping tokens were independently checked against the original resource bytes in the private evidence directory. F1099D withholding is L2; F1099I withholding is L4. Adjusted-qualified fields are not substituted for Box1b.

All six amounts must be explicitly present, nonnegative, have at most two decimal places and stay within the supported limit. Box1b cannot exceed Box1a. Boxes2b+2d cannot exceed Box2a. Missing values never establish zero. Unsupported siblings, arrays, active value flags, unknown fields and copy-zero cases block import. This workflow excludes QSBS exclusions, FIRPTA, nondividend/199A distributions, investment expenses, foreign tax, liquidation, exempt-interest/private-activity dividends and nominee allocations. Such facts require a separate supported workflow.

Each added record has a stable local identifier, reviewed fingerprint, original-source receipt and immutable six-box snapshot. Editing current amounts clears review and retains the imported snapshot. HTTP/SQLite and browser metadata reject changes to the saved receipt or snapshot. Original attachments remain separate from a JSON backup and must be exported separately.

Download corrected XML changes only the six selected value text spans in a separate plaintext copy. It reparses that copy, retains other source bytes and leaves the original attached. It does not execute the original engine, rebuild encrypted .tax containers, update template checksums or establish original-program loadability.

The `fixtures/taxml/synthetic-native-dividend-*` inputs are independently authored. Host HTTP/SQLite tests and the actual pinned Pyodide/JS worker verify migration, subset-safe income calculation, joint INT/DIV withholding rounding, tamper rejection, corrected XML and review invalidation. The example with interest1000, ordinary dividends1200.31+0.49 and capital distributions1000.25 yields total income3201; Boxes2b/2d are not added again. Withholding200.49+0.49 yields201.

Original saved-return fixtures and native original-program executions remain zero. Native-package build, installation, changed-flow testing, publication and public readback are recorded separately in the candidate acceptance receipt.
