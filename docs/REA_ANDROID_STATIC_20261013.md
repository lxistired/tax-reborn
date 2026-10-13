# Original TurboTax Android: historical static evidence

The acquired APK is the original, signed **TurboTax Android 5.10.0 / 5100**,
with a historical mirror file date of **2019-09-18**. It is **not evidence of
the current 2026 mobile release**, current prices, or tax-year 2025 behavior.

The original bytes are 79,404,033 bytes, SHA-256
`af48c979afea68a90e619ee41395aa8753d946b4da77549dc0db7d4498ca5aee`.
Android SDK 35 apksigner verified its v1 signature and certificate
SHA-256 `f39f8155d0fe3da8b94eeeee87739bca008b04ec078d3a37b0f1335a3c49f87f`.
That exactly matches the independently fetched first-party Intuit
`assetlinks.json` signer for `com.intuit.turbotax.mobile`. The apksigner log
retains warnings for some unsigned META-INF entries. No application code was
executed or installed, and no account or backend was accessed.

Actual REA 6.4.0 Android tooling used the pinned official
JADX headless MCP 0.7.1 JAR, Java 21, one worker and a 2 GiB heap. Package
inspection confirms min SDK 21, target SDK 28, five DEX files and 18,286 total
decompiler class rows. The saved index contains **32 method observations**:
**30 decompiled method bodies**, one interface declaration, and one native
declaration without a recovered native body. Five incoming static reference
queries were saved. These counts do not include failed queries or inventory
as recovered functions. Display method signatures have unknown exact DEX
descriptors; static references have unknown DEX offsets and source lines.

## What the inspected code establishes

- **Local W-2 capture/scanning adapter.** Scanbot frame processing calls
  `W2Scanner.processImage` through JNI with image bytes, polygon and dimensions.
  Completion passes a status integer and string through the callback. The actual
  native OCR body, status meanings, returned data schema and measured accuracy
  remain unresolved.
- **OCR result handed to a web layer.** `W2CharacterScanController` reads the
  image result from an Intent and builds a `TTUApp.imageUpload` JavaScript call.
  This establishes an adapter route, not an independently recovered backend
  import implementation.
- **Document payload.** The capture/selector UI returns original bytes as a
  newline-free Base64 value plus `name`, `type` and byte `size`. It calls the
  document-capture callback; the inspected method itself does not directly make
  a network request.
- **Topic and save paths call a server.** `JobService` sends fields plus tax
  year, device form, language, offering and schema versions to the session's
  web server via `ServiceBroker`. The request requires session and routing
  information. The server response is handed to the flow loader or triggers
  a save-completion listener. The listener is a notification, not independently
  validated durable persistence.
- **Paid purchase is a service integration.** The provider requests a dynamic
  SKU token from a configured service, parses `dynamic_price_token` and
  `intuit_tid`, and passes a dynamic SKU into Google Play Billing. Purchase,
  cancellation and error receipt paths are present. The server's entitlement
  acceptance and current paid SKU/function matrix have not been recovered.
- **Refund/PDF/Live/amend actions are client dispatch routes.** A refund event
  loads an incoming refund payload into client state. PDF, Live upgrade,
  expert handoff, amend and reject handling dispatch events. These route names
  do not prove the paid service or tax calculation is contained in this APK.

The conclusion supported by this inspected slice is a hybrid mobile client with
local capture adapters and server-bound interview/save/purchase paths. It does
not prove that every calculation in the package is remote, and it does not
recover a complete original mobile tax engine.

## Reconstruction boundary

An independent replacement can implement document capture and reviewed field
entry, topic/save orchestration with its own backend, purchase/error states,
and PDF/refund dispatch around an independent calculator. Exact original
mobile parity remains open because current release bytes, original runtime
fixtures, native OCR, web handlers and server-side tax computation are absent.

`android-static-reconstruction-contract.json` maps 23 specific observations to
full REA Evidence IDs and their original JSON records. The complete evidence
export retains all producer observations. `mobile_contract_probe.py` validates
ten synthetic contract cases without network or vendor execution. Those are
tests of the independent model, not original TurboTax differential tests.

Keep the original APK, decompiled text and complete producer evidence private.
This own-word summary and independently written code are the public boundary.
