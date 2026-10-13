# Historical Android W-2 native and GMV findings

Recorded 2026-10-13. Target is the signed historical **TurboTax Android
5.10.0 / 5100**, mirror file date **2019-09-18**. The native findings apply
to its **x86_64** member, not every architecture or the current mobile release.
Original APK SHA256: `af48c979afea68a90e619ee41395aa8753d946b4da77549dc0db7d4498ca5aee`.

## Target identity and count

Actual W-2 JNI functions are in `lib/x86_64/libscanbot-detector.so`.
The original APK member and extracted ELF match: **8,507,632 bytes**, SHA256
`f69dae35966f180c11a398c2eb186424e60b2dc75d8aad227bae13c90301da46`.
Other inspected libraries belong to screen sharing, device-fraud detection or
authentication; they are not counted as recovered W-2 recognition.

REA/Ghidra read **12 distinct functions in the complete original ELF**. The
analysis used base adjustment `0x100000`; all 12 original-address keys are
distinct. Their mappings and 16-byte entry reads matched the original member,
and were independently checked. The export has **36 records**: 12 function
dossiers, 12 mappings and 12 byte reads. A supplemental derived JNI window adds
**0** original functions. Raw entry bytes and decompiler output are private.

| Function role | Original ELF VMA | Ghidra address |
| --- | ---: | ---: |
| JNI processImage | `0x124880` | `0x224880` |
| Scanner processImage | `0xf77c0` | `0x1f77c0` |
| Generic field OCR path | `0xf63e0` | `0x1f63e0` |
| Completion callback | `0x122a10` | `0x222a10` |
| Field-object callback | `0x122a90` | `0x222a90` |
| JNI constructor | `0x124350` | `0x224350` |
| Confidence getter | `0x123470` | `0x223470` |
| Attempt-count getter | `0x123440` | `0x223440` |
| JNI_OnLoad | `0xd1310` | `0x1d1310` |
| Tesseract placeholder | `0xefa10` | `0x1efa10` |
| Regions-only setter | `0xf5bf0` | `0x1f5bf0` |
| Confidence placeholder | `0xefab0` | `0x1efab0` |

## What the bodies establish

The constructor enables **regions-only** mode. The corresponding branch returns
field regions with status 1 and skips generic OCR. The Tesseract-named body
returns an unsupported-build placeholder; its confidence function returns
`0xffffffff`. A Tesseract-looking symbol does not establish a working text
recognizer in this member.

Completion carries a 32-bit status and Java string. The caller gets this string
from its **analytics logger**. Actual W-2 field objects use a **separate
callback**. Common completion status 0 can follow a template-match failure,
so completion alone does not prove correct amounts. Native confidence and
attempt-count fields require independent interpretation and validation.

These findings require an independent replacement to keep detected regions,
candidate text, field mapping and user review separate. Treating a diagnostic
string as tax-field JSON would be an incorrect reconstruction.

## Three additional Java bodies

REA/JADX inspected `GMVTaskManager.runOcr`, `getRawDataJson` and `getTextJson`.
The first orchestrates four candidate rotations and delegates recognition to
internal tasks. The other methods serialize Google Mobile Vision text blocks,
bounding rectangles, corner points and recursive components. These are actual
method bodies: **30 earlier Java bodies + 3 additions = 33**, with two earlier
declarations still excluded. The new export has 9 records, of which only 3 are
bodies and 6 are class inventories.

The inner recognition implementation, model availability and final W-2
box/amount mapping remain open. These Java results do not establish measured
accuracy, complete import parity or server tax calculation.

## Remaining boundary

Original APK/native execution count is **0**. No original package was installed,
and no account, service, activation or purchase protection was bypassed. The
failed import attempts and decompiler warnings are retained in private evidence.
Current-release parity, a complete current mobile tax engine and original pixel
parity remain unverified. Actual Android close-up camera OCR and Activity
recreation of the independent app are also unverified in this report.

See [the historical Android summary](REA_ANDROID_STATIC_20261013.md) for the
server-bound interview/save/purchase routes. Original binaries, resources,
images, JNI bytes and full producer output are excluded from public source.
