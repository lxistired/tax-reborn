# Preview12 candidate acceptance

This is a candidate built from c90a64d6b7e81f21dca3972ff03b59ffe3978f3e. It is not yet a published release. All return figures, identities and PDFs here are synthetic.

Windows installed/frozen checks17 and native GUI checks17 passed. The native SaveAs birthday PDF has EIC0, refund1000 and the IRS Form1040 line27c checkbox checked. Mac actual edits, normal quit/relaunch and native system PDF save/readback passed with the same fields. DMG payload matches all381 App files.

Android actual birthday example, date edit, Save and process restart passed. The unchanged-signature installed APK matches the candidate. New birthday PDF generation reached the system document picker, but saving that phone-generated file and reading it back have not been accepted. The picker was cancelled and the saved return remains intact. Do not describe this as completed mobile PDF export acceptance.

The whole host suite passed482 tests. Actual Pyodide executed431 tests successfully with one host-only skip. These tests do not establish original TurboTax runtime parity, full .tax compatibility, electronic filing or unsupported tax profiles.
