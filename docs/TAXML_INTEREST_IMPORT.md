# Reviewed 2025 1099-INT TaxML migration

Preview.14 extends the current Windows-shaped plaintext TaxML adapter to four explicitly present F1099I scalar inputs. The independently authored App validates the caller's actual XPRF bytes, selected template identity, tax year, entity/copy context, XML headers and supported flags. No vendor resources or original saved return are included.

| Source field | Reviewed document amount | Federal input |
| --- | --- | --- |
| L1 | 1099-INT Box1 interest income | Taxable interest |
| L3 | Box3 U.S. savings-bond and Treasury interest | Added to Box1 in exact cents |
| EXINT | Box8 exempt interest | Separate tax-exempt interest |
| L4 | Box4 federal withholding | 1099 federal withholding |

Original-byte readback independently verified the four kind11/format0 metadata rows and their exact output declarations. The names identify source inputs; derived `TAX` is not substituted for withholding. This evidence establishes a bounded mapping, not original loading, execution or full-return compatibility.

Federal treatment follows the [IRS continuous-use 1099-INT instructions, revision January2024](https://www.irs.gov/instructions/i1099int) and [tax-year2025 Form1040 instructions](https://www.irs.gov/instructions/i1040gi). Cents are combined before the current federal line rounding. Treasury interest remains separately recorded in the import snapshot for review of state exclusions. This import does not populate or certify a state return.

## Actual workflow

1. Open Documents → Inspect TaxML / plaintext .tax. Choose a plaintext XML or explicitly declared plaintext ZIP, its exact caller-owned profile and XPRF carrier.
2. Inspect locally. An unknown field, unsupported sibling, kind/format mismatch, absent box, unused value, active unsupported flag or copy-zero context prevents adding the candidate.
3. Review the four dollar amounts and payer, then confirm the household and supported interest situation. Missing is not zero. Payer entry is manual.
4. Download a corrected XML copy if needed. Only the four amount text spans change; every other source byte is retained and the exported copy is reparsed. The original document is retained as a separate local attachment. No original return recalculation is asserted.
5. Add the reviewed 1099-INT and save. Existing income is retained. `all_income_reported` is cleared; importing one document does not establish a complete return.
6. Reopen the saved return. The receipt and all four reviewed import amounts remain attached by stable record ID. Editing the current aggregate amounts clears review without altering the immutable source snapshot.

Early-withdrawal penalties, investment expenses, foreign tax, private-activity bonds, market discount, bond premiums, nominee allocation, education-related savings-bond exclusions and other source facts are outside this four-box adapter. They must not be silently discarded. Source-receipt and imported-box tampering is rejected on both host and offline persistence paths. A backup carries references and snapshots; the separate attachment itself must be retained or restored separately.

## Evidence states

- Native Python:552 checks passed, including actual HTTP/SQLite save/reopen/backup, edits and atomic tamper rejection.
- Real pinned Pyodide:470 executed regression checks passed; the separate integrated worker/JS harness exercised the new inspector, review validation, exact cents, source immutability, correction and readback.
- Actual browser HTTP/SQLite:[receipt](../qa/taxml/interest-HTTP-browser-acceptance.json), [reopened image](../qa/taxml/interest-HTTP-reopened.png). The existing0.49 record survives addition. Edited Box1=100.24,Box3=40.27,Box8=12.34,Box4=22.45 produces taxable interest141 and refund22 in this synthetic incomplete household.
- Actual browser Pyodide/IndexedDB:[receipt](../qa/taxml/interest-offline-browser-acceptance.json), [reopened image](../qa/taxml/interest-offline-reopened.png), [actual backup](../qa/taxml/interest-offline-backup.json). Box4=23.45 produces refund23; the four-box snapshot survives reload. This exercised the offline API mode while local static HTTP remained available; it is not a new network-disconnection test.
- Preview.14 native candidate status is [recorded separately](../qa/native-preview14/candidate-acceptance-state.json). Mac Cocoa file selection, four-box review/edit/add/save/quit-relaunch, system XML save and original-attachment readback passed. Windows Setup installation,17 frozen checks,17 native GUI regressions and installed actual Pyodide/JS interest checks passed; the new file-picker workflow is still a separate UI acceptance gap. The APK is built with the existing signer and its actual assets passed Pyodide/JS interest checks. The phone remains absent from USB, so the new APK is not installed or accepted on that phone.
- Original TurboTax execution:0. Validated original saved `.tax` fixtures:0. Full `.tax` container, original recalculation and full-product replacement remain unverified.
