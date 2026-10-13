# Native platforms

Tax Reborn uses the same independently written 2025 tax engine and local inputs
across its desktop and mobile shells. This document separates source readiness,
native build, execution checks and signing. No package is a completed tax filing
or evidence of full TurboTax parity.

## Windows

`scripts/build_desktop.py` must run on Windows. It builds the pinned PyInstaller
executable, runs its checks against the **actual frozen executable**, collects
authentic third-party licenses and produces a portable ZIP. With Inno Setup 6 it
also produces a per-user installer that needs no administrator rights.

The manual `Native packages and real platform checks` GitHub Actions workflow
uses the officially supported `windows-2022` standard runner. It runs independent
Python checks, the native build, frozen checks and
`scripts/windows_gui_smoke.ps1`. That GUI check opens the real WebView2 window,
loads the synthetic W-2 household, verifies a $1,413 refund, edits withholding
from $6,500 to $7,000, verifies $1,913, saves and reopens the return after a normal
app close. It saves screenshots and rejects blank captures. A failed GUI check
remains a failure even if an installer exists. The receipts identify actual
runtime versions. These packages are unsigned previews, not SmartScreen-trusted
releases. macOS cannot produce or verify this Windows executable by cross-build.
The next integrated test also opens the actual native Save As dialog for a PDF
export and reads back its saved IRS fields. That check requires the desktop
shell's `ALLOW_DOWNLOADS` setting; API PDF generation alone does not verify the
native download. See the version-specific evidence below.

## Native iOS

The Swift UIKit app under `ios/` embeds the same local HTML interview, Python in
WebAssembly, OCR, state engine and IRS PDF resources in WKWebView. It is a native
app with a local web interface. It requires iOS/iPadOS 16.4 or later.
The bundled runtime's [Pyodide 0.29.3 browser support](https://pyodide.org/en/0.29.3/usage/index.html)
also lists Safari 16.4 as its tested minimum. This does not replace testing this
particular app on each iOS version.

`LoopbackAssetServer` binds **127.0.0.1:18786**. The origin stays identical after
relaunch, so WKWebView's persistent IndexedDB retains returns and attachments.
If another local service occupies the port, startup reports the conflict instead
of switching the origin and hiding existing storage. The server accepts only
GET/HEAD for an explicit bundled asset allowlist. It rejects foreign Host/Origin,
POST, `/api`, traversal, double escaping, body framing and unlisted files. It has
no remote API, directory listing, tax-data route or listener on the LAN.

The `NSAllowsLocalNetworking` ATS declaration allows this private IP origin;
arbitrary web loads remain disabled. Page CSP restricts fetches and workers to
the origin, and the navigation delegate blocks external pages and popups. The
app contains no login, analytics or telemetry SDK. [Apple ATS documentation](https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity/nsallowslocalnetworking)
explains the IP-address declaration, including the iOS 17 change.

The native bridge uses
[WKScriptMessageHandler](https://developer.apple.com/documentation/webkit/wkscriptmessagehandler).
Only a message from the local main frame can invoke it. At document start it
defines the following Promise interface:

```javascript
await window.TaxRebornIOS.saveFile(filename, mime, base64);
// { saved: true, cancelled: false } or { cancelled: true }; rejects on failure

await window.TaxRebornIOS.pickFile({ accept: 'application/json' });
await window.TaxRebornIOS.pickPhoto();
await window.TaxRebornIOS.capturePhoto();
// { cancelled: true } or
// { cancelled: false, file: { name, mime, base64, bytes } }; rejects on failure
```

Exports go through the system Files picker and are reported saved only after
its completion. Temporary export data is removed after save or cancel. Imports
are limited to one user-selected file, 24 MB. Camera access starts only after
the user's action and the system camera permission. Photos use PHPicker without
requesting access to the whole photo library; only the selected image is read.
[Apple's Photos picker sample](https://developer.apple.com/documentation/PhotoKit/selecting-photos-and-videos-in-ios)
describes this permission model. Image imports are reencoded as JPEG without
adding location metadata. The native Add document menu dispatches
`tax-reborn-native-document` with the same file result for the web attachment and
review flow. Selecting a document never commits extracted tax amounts.

## iOS build and verification

These commands require an **already installed full Xcode** and its SDKs. The
script never downloads Xcode/SDKs, accepts license terms, signs into an account,
downloads provisioning profiles, or changes the user's selected Xcode.

```sh
# Prepare a reproducible project and all bundled assets without needing Xcode.
python3 scripts/build_ios.py --prepare-only --work-dir build/ios

# Build on a Mac with full Xcode and an existing iOS Simulator runtime.
python3 scripts/build_ios.py --run-ui-tests --output-dir dist/ios
```

Open `build/ios/project/TaxReborn.xcodeproj` in Xcode for local editing. The
generator has no third-party project dependency. It first builds a Simulator app,
then an **unsigned device app**. The XCUI test uses the actual Simulator WKWebView
and WebAssembly engine to check $1,413 → edit → $1,913 → save → terminate →
relaunch → reopen. Its screenshots are attached to `ios-ui-smoke.xcresult`.
`simulator_gui_tested` becomes true only after Xcode returns success for this
test. A successful Simulator test does not claim real-device validation.

The CI workflow uses the officially supported `macos-15` standard runner and
only its existing Xcode/Simulator runtime. GitHub's
[runner documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job)
states that standard public-repository runners are free. The workflow refuses
private repositories, uses read-only repository permission, starts only by
manual dispatch and contains no signing token. Artifact upload preserves failed
check evidence too. Publishing a GitHub release is a separate action.

## iPhone installation and distribution

A Simulator app cannot run on an iPhone. An unsigned device `.app.zip` also
cannot be installed on an ordinary iPhone. These names and manifests preserve
that distinction; the build does not create a misleading unsigned `.ipa`.

Local device testing requires the user to configure signing in Xcode. Apple's
[developer account overview](https://developer.apple.com/help/account/basics/about-your-developer-account)
says a free Personal Team can test on personal devices, with periodic
reprovisioning and seven-day profile limits. App Store/TestFlight distribution
requires appropriate Developer Program membership and provisioning. A developer
with an already configured team can use `--team-id TEAMID` without automatic
profile downloads, then use Xcode's normal signed device/archive workflow. This
project does not install unsigned packages, borrow a certificate, or enroll or
charge an Apple developer account.

## Verified baseline preview.2 — 2026-10-13

Both native CI runs completed successfully using **2026.10.13-preview.2**. Their
downloaded artifact sizes and SHA256 hashes were independently checked against
the generated manifests. These results describe this baseline, not the later
preview.3 tax modules and expanded official paper-form packet.

| Platform | Actual build and execution | Remaining evidence boundary |
| --- | --- | --- |
| Windows x64 | [CI run 38361714557](https://github.com/lxistired/tax-reborn/actions/runs/38361714557) built a 55 MB installer and 68 MB portable ZIP. All ten checks ran against the frozen executable. The real WebView2 GUI calculated $1,413, changed withholding to $7,000, calculated $1,913, saved and retained $1,913 after normal close/relaunch/reopen. | This successful baseline did not test native GUI file downloads. Its hosted-screen capture clipped part of the default window; the next driver maximizes the actual window and aligns its own DPI coordinates. It is an unsigned Windows preview. |
| Native iOS | [CI run 38361300928](https://github.com/lxistired/tax-reborn/actions/runs/38361300928) used Xcode 16.4 / SDK 18.5 and a real iOS **26.2 Simulator**. Simulator and device-target Swift builds succeeded. The actual WKWebView/WebAssembly GUI calculated $1,413, entered exactly $7,000 withholding, calculated $1,913, saved, terminated, relaunched and reopened the persistent $1,913 return. Bundled asset hashes were verified. | Simulator execution is not real-iPhone testing. The device-target app remains unsigned and requires matching signing/provisioning before installation. Native Files export and photo/camera flows were not part of this baseline XCUI check. |

Receipts, checked scope and actual screenshots are stored in
[`qa/native-preview2`](../qa/native-preview2/). The Windows frozen and GUI receipts
are distinct. The iOS manifest explicitly records `device_signed: false` and
`real_device_tested: false`. The shared loopback-server/request-parser code also
compiled and passed 24 real Network.framework checks on the author's Mac; that
is additional server evidence, not an iPhone installation claim.

## Integrated preview.3

The source now includes new tax modules and an expanded official IRS paper-form
packet. The native evidence below comes from builds of **2026.10.13-preview.3**,
not from transferring preview.2's status.

| Platform | Actual build and execution | Remaining evidence boundary |
| --- | --- | --- |
| Native iOS | [CI run 38363853694](https://github.com/lxistired/tax-reborn/actions/runs/38363853694) built both Swift targets with 103 verified bundled assets. The actual Simulator WKWebView/WebAssembly app calculated $1,413, accepted $7,000 withholding, calculated $1,913, saved and retained $1,913 after termination/relaunch/reopen. Both downloaded app ZIP sizes and SHA256 hashes matched their build manifest. | The device build is unsigned. Real-iPhone execution, native Files export and the camera/photo chooser have not been verified by this Simulator calculation test. |
| Windows x64 | [CI run 38366650831](https://github.com/lxistired/tax-reborn/actions/runs/38366650831) passed 343 Python checks, eleven frozen executable checks and the real $1,413 → $1,913 GUI calculation/save/relaunch/reopen flow. The actual screenshot shows a native Save As dialog for the PDF. | The added export test failed because the system picker exposes its filename as a Pane rather than the Edit control expected by the driver. The corrected dialog driver still needs a successful run that saves the actual PDF and reads back its IRS fields. This run is not a passed native-download check. |

Preview.3 iOS receipts, downloaded-artifact verification and actual synthetic
screenshots are stored in [`qa/native-preview3`](../qa/native-preview3/). The
Windows native-download check remains unverified until its actual saved-file and
field readback pass. iOS signing and real-device status remain separate from the
successful native builds and Simulator execution.

## Final preview.3 native checks

GitHub Actions38368688144 (source566a68d) completed successfully for Windows and iOS. Windows passed343 tax/PDF tests,11 frozen checks, actual1413→7000→1913 edit/save/relaunch, and a real native Save As download with subsequent official IRS field readback. Both Windows Setup and portableZIP artifacts match the recorded bytes/SHA256.

Both iOS Simulator and unsigned iphoneos apps compiled and matched their manifest. Actual WKWebView/WASM1413→7000→1913 and save/terminate/relaunch/reopen passed. iOS device signing, real-iPhone acceptance, and native Files/camera operations are separate from this successful Simulator calculation test.

MacARM preview.3 also used an actual Cocoa Save dialog to save a4page1040+ScheduleB paper-preparation PDF; local readback verified1413 and Single status. Android was updated topreview.3 using the same private development signing identity aspreview.2, retaining saved returns and the existing camera photograph. The fuzzy-photo retest returned an explicit low-confidence/manual-entry prompt instead of filling the previous incorrect60000 withholding candidate. Clear near-camera amount acceptance is recorded separately.

## W-2 identity and workspace-recovery batch

Current application source 2b2b7af passed353 Python checks, including10 real HTTP/SQLite metadata checks. [Windows run38388852637](https://github.com/lxistired/tax-reborn/actions/runs/38388852637) passed11 actual frozen-program checks and the actual1413→7000 withholding→1913 native GUI/save/relaunch/PDF flow; downloaded Setup and portableZIP hashes matched their manifest.

The iOS job in that run failed its old relaunch-page expectation. The retained W-2 page, saved state, owner,7000 withholding and1913 result were visible in the failure artifact. The corrected test was committed asdbb68cf and [iOS run38392321586](https://github.com/lxistired/tax-reborn/actions/runs/38392321586) passed actual native calculation, restored W-2 workspace and explicit saved-return reopening. Both appZIP hashes matched their manifest. The device app is still unsigned, and no real-iPhone Files/camera test is claimed.

The current local MacARM DMG includes return_metadata.py and cache14. Its11 actual frozen-program checks passed. The Android APK also carries cache14 and matches the validated frontend assets; REA installed it with replace using the existing private signer and confirmed zero requested permissions. Device-data clearing was not performed. Clear near-photo OCR and actual Android Activity recreation remain unverified. Records for this batch are inqa/native-w2metadata-20261013 andqa/android-w2metadata-deployment-20261013.json; earlier native receipts remain tied to their earlier source commits.

## Camera OCR recovery and texture batch

Application source c8c4960 includes cache16 and a controlled OCR worker. A failed or timed-out load/recognition terminates the worker; retry creates a fresh one. Large images use a temporary full-frame proportional downsample and local threshold, while small/narrow images keep the original. The stored attachment is untouched; amount parsing and the confidence gate are unchanged.

The actual existing synthetic W-2 camera photo produced correct Box1-6 candidates on the Android phone:60000.00,6500.00,60000.00,3720.00,60000.00,870.00. After source review, adding and saving, the actual app displayed1425. Process force-stop/relaunch restored the W-2 page, amounts and Reviewed state; opening the same saved return from the list retained1425. Four return checks remained open, so this is not a complete tax-return claim. Camera-time Activity recreation is a separate unverified case. See [phone receipt](../qa/android-camera-ocr-accepted-20261013.json).

The new MacARM DMG passed11 checks in its actual frozen executable. [Native run38407957597](https://github.com/lxistired/tax-reborn/actions/runs/38407957597) completed successfully for Windows and iOS from source c8c4960. Artifact readback and package hashes are recorded inqa/native-ocr-final-20261013. The iOS device app remains unsigned; no actual iPhone camera/Files test is claimed.
