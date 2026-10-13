# Local camera extraction: actual checks, 2026-10-13

An existing phone-camera photograph of a **synthetic 2025 W-2** now completes
extraction, source review, saving and reopening on the Android phone. The
original photograph and complete OCR text remain in the private work directory.

| Box | Candidate observed in the actual phone UI, USD |
| --- | ---: |
| 1 Wages | 60,000.00 |
| 2 Federal withholding | 6,500.00 |
| 3 Social Security wages | 60,000.00 |
| 4 Social Security withholding | 3,720.00 |
| 5 Medicare wages | 60,000.00 |
| 6 Medicare withholding | 870.00 |

None of these amounts was manually filled. The employer name was entered from
the photograph. After reviewing the owner and source amounts, the record was
added as Reviewed and saved. The actual return showed a $1,425 estimate with
four checks still open. Force-stopping and relaunching the app retained the W-2
page, amounts and Reviewed state. Explicitly opening the same saved return from
the list retained the $1,425 estimate. This is preparation, not a filed return.

## Why the previous attempt failed

The full 3072×4096 photograph contained a dense screen pixel pattern. Actual OCR
at that resolution returned low confidence and no amount candidates. A simple
downsample improved speed but still dropped a zero from one amount, so that
variant was rejected.

The integrated implementation creates a temporary full-frame OCR copy. Large
images keep their proportions, use a maximum edge of 1600 pixels, then apply a
31-pixel local Sauvola threshold. Small images and narrow images that would lose
too much short-edge detail keep their original input. No field crop, expected
amount, substitute text or remote OCR service is used. The stored attachment
bytes are untouched.

The production extractor was independently rerun against the exact private
photo: 1.326 seconds, confidence83, W-2/year2025 and all six amounts correct.
Those timings are desktop headless measurements, not measured phone timings.
Actual-worker checks also passed on a small image, a landscape image and a
narrow image. The amount parser and confidence gate are unchanged; eight
existing safety-boundary checks remain passed. One known photo is not a general
OCR accuracy benchmark.

## Failure and retry

The application now owns the OCR Worker before initialization. If language
loading, initialization or recognition fails or times out, it terminates that
worker, clears pending work and creates a new worker on retry. Failure and
timeout recovery were tested against the real pinned worker, not an OCR stub.
Concurrent requests are serialized.

The Android update reused the installed app's private development signer and
retained its returns and photograph. It requests no permissions and has no
INTERNET permission. Camera-time Android Activity recreation, general photo
accuracy and real-iPhone camera/Files flows remain separate unverified cases.

The [machine-readable receipt](../qa/android-camera-ocr-accepted-20261013.json)
records the exact application/APK identity and check boundaries. Screenshots
show independently written app UI and synthetic amounts.
