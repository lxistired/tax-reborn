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

## Preview.4: investment corrections and masked review export

The actual runtime source is `a501082a2c13ee1955b6be94309b1ed6e62c95dc`, version
`2026.10.14-preview.4`, with tax year 2025. Subsequent documentation and QA commits
do not change those package bytes. [Native run 38444768398](https://github.com/lxistired/tax-reborn/actions/runs/38444768398)
completed successfully for Windows and iOS. The current host suite has 367 tests;
349 tests also pass inside the actual Pyodide worker, excluding host-only integration.

| Platform | Actual verification of this version | Boundary |
| --- | --- | --- |
| macOS arm64 | Eleven frozen-executable checks. The real native app opened the synthetic return and saved the new masked Form 1040 review copy through the Cocoa Save panel. The saved PDF equals the source-browser synthetic PDF, retains the $1,425 refund, and passes the selected-identifier scan. | Unsigned and not notarized. This export does not remove all personal information or establish original TurboTax runtime/pixel parity. |
| Windows x64 | Eleven frozen-executable checks; real WebView2 $1,413 → withholding edit → $1,913; save, normal close/relaunch/reopen, and a native Save As ordinary IRS PDF with field readback. Setup and portable ZIP hashes match the downloaded manifest. | Unsigned preview. The new masked-export UI was tested separately in actual desktop Chromium, not by this Windows-native smoke. |
| Android | Same-key replace install and launch verified using REA; package-manager version readback is `2026101404`. The actual phone retains the saved synthetic $1,425 return and four open checks. Eleven selected bundled assets match current source; the APK requests zero permissions. | The previous actual camera/OCR acceptance remains tied to its earlier build. The extraction worker is unchanged. This update did not independently exercise the phone's masked-PDF destination picker. |
| iOS | Simulator and unsigned device targets compiled; 106 bundled assets verified. Actual Simulator WKWebView/WebAssembly calculation, edit, save, terminate/relaunch and reopen passed. Both downloaded ZIP hashes and ten selected assets per ZIP match current source. | The device app is unsigned and requires signing/provisioning. Simulator acceptance does not establish real-iPhone, native Files export or camera behavior. |

Receipts and actual synthetic screenshots are in [`qa/native-preview4`](../qa/native-preview4/).
The independent masked-export acceptance also exercises actual HTTP/SQLite and
Pyodide/IndexedDB UI modes, verifies eight identity/bank fields plus PDF widget
appearances, and proves ordinary data/results remain unchanged. Its leak tests
refuse the export without a normal-PDF fallback. See [masked review scope](MASKED_REVIEW_COPY.md).


## Preview.5: exact income replacement and persistent review

The package runtime source is `332d29c6ba3d50c2d419ee8a44948eb8a665c26f`, version
`2026.10.14-preview.5`, with tax year 2025. [Native run 38452333711](https://github.com/lxistired/tax-reborn/actions/runs/38452333711)
completed successfully for Windows and iOS. The source passed 385 host tests and
359 tests in the real Pyodide worker. Separate independent acceptance exercised
22 actual mobile-layout UI checks across HTTP/SQLite and Pyodide/IndexedDB,
including a real storage transaction abort, same-dialog retry, profile relaunch,
JSON restoration and immutable-history refusal.

| Platform | Actual verification of this version | Boundary |
| --- | --- | --- |
| macOS arm64 | Eleven checks in the actual frozen executable. The packaged native app selected an income CSV through the Cocoa Open panel and confirmed replacement of the exact placeholder ID. Line 2b changed from $1,350 to $1,550; refund changed from $1,263 to $1,239. The unrelated same-payer $350 row, identity and review state remained unchanged; one event was saved. | Unsigned and not notarized. Original TurboTax execution and pixel equivalence remain unverified. |
| Windows x64 | Eleven frozen checks; actual native $1,413 → withholding edit → $1,913; save, normal close/relaunch/reopen and a real PDF Save As with field readback. Setup and portable ZIP hashes match their manifest; selected packaged runtime modules match source. | Unsigned preview. The new income replacement is covered by real source-browser acceptance and the native Mac check; this Windows smoke did not independently exercise its CSV picker. |
| Android | REA same-key replace install and start succeeded. Package manager readback confirms version code `2026101405`; 13 selected bundled assets match source. The actual phone retains the prior saved synthetic $1,425 return and four open checks. The APK requests zero permissions. | New income persistence is tested in real Pyodide/IndexedDB mobile UI. The physical phone's CSV picker and this version's camera workflow were not separately accepted. The previously accepted OCR worker remains unchanged. |
| iOS | Both native targets compiled; 107 bundled assets verified. The real Simulator WKWebView/WebAssembly calculation/edit/save/terminate/relaunch/reopen passed. Downloaded ZIP hashes and seven selected assets per ZIP match source. | Device build is unsigned and needs signing/provisioning. The Simulator check does not verify real-iPhone Files, camera or the new native CSV picker. |

Receipts and actual synthetic screenshots are in [`qa/native-preview5`](../qa/native-preview5/).
See [income preparation and 22 UI checks](INCOME_DOCUMENT_PREPARATION.md) for
stable row identity, unresolved facts, atomic history and stale-revision scope.
Native package acceptance is specific to this source; subsequent documentation
and binary research checkpoints do not change the package runtime.

## Preview.6 actual package acceptance

[Preview.6 downloads](https://github.com/lxistired/tax-reborn/releases/tag/v2026.10.14-preview.6) include the new paper-packet copy/page preflight. Mac ARM and Android runtime sources were frozen at `00a32f1832744b30111f001ffaa17e9f6bded1b1`. Windows was built and tested at `c62060441f96c0d066b61b2a508b421ccc38920c`; the intervening changes add installer test automation without changing those App sources. The package-provenance receipt compares the actual Mac/APK critical source bytes.

- Windows x64 Setup was actually installed on the native Windows runner. The installed executable SHA-256 matches the built executable. Both the packaged executable and the installed executable pass 12 frozen checks including actual serialized packet preflight. The installed native GUI changes withholding from $6500 to $7000 and refund from $1413 to $1913. It saves and reopens that return and exports an actual PDF through Save As. [Installer receipt](../qa/native-preview6/windows-installer-receipt.json) and [GUI receipt](../qa/native-preview6/windows-native-gui-smoke.json) record this scope. [Successful native run](https://github.com/lxistired/tax-reborn/actions/runs/38506762536).
- Mac ARM DMG was checked and mounted read-only. All 360 payload files match the built app. The mounted actual executable passes 12 frozen checks. Native GUI interest changes $100 to $200 and refund $1413 to $1401. Saving and a cold restart preserve $1401. Actual NSSavePanel export produces a 4-page draft packet with all planned page/copy identities verified. [Mac receipt](../qa/native-preview6/macos-native-gui-smoke.json). The DMG remains without Developer ID signing or notarization.
- Android was updated in place with the original certificate. No uninstall or data wipe occurred. The installed base APK hash matches the release APK and version code is 2026101406. The actual phone retains the $1425 synthetic return. Keyboard GUI edit/save changes the synthetic name to P6. Android SAF saves the actual 3-page packet; its extracted PDF has matching planned page/copy identities. A process cold restart restores P6 and $1425. [Phone receipt](../qa/native-preview6/android-native-gui-smoke.json). USB mirror disconnects were recovered during testing. Mouse reliability and camera/OCR were not revalidated in this pass.

The host suite passes 404 checks and real Pyodide passes 378. An additional run using Python/forms/WASM assets extracted from the final APK also passes 378. These are separate scopes. This release updates the requested Windows/Mac/Android packages. It does not add an iOS package or establish original `.tax` compatibility or full TurboTax calculation parity.
