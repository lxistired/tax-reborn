# Preview12 candidate acceptance

This is a candidate built from c90a64d6b7e81f21dca3972ff03b59ffe3978f3e. It is not yet a published release. All return figures, identities and PDFs here are synthetic.

Windows installed/frozen checks17 and native GUI checks17 passed. The native SaveAs birthday PDF has EIC0, refund1000 and the IRS Form1040 line27c checkbox checked. Mac actual edits, normal quit/relaunch and native system PDF save/readback passed with the same fields. DMG payload matches all381 App files.

Android actual birthday example, date edit, Save and process restart passed. The unchanged-signature installed APK matches the candidate. The phone-generated birthday PDF was saved through the system picker and read back:30pages, EIC0, refund1000 and Form1040 line27c checked. Both PDF field readback and rendered-page inspection passed.

The whole host suite passed482 tests. Actual Pyodide executed431 tests successfully with one host-only skip. These tests do not establish original TurboTax runtime parity, full .tax compatibility, electronic filing or unsupported tax profiles.


## Android export acceptance completed

On2026-10-14, the actual system Save completed using the numeric keypad confirmation key. The phone-generated PDF was read from its saved destination. It has30pages, EIC0, refund1000 and the expected Form1040 line27c checkbox. The PDF field readback and rendered page both passed. See android-birthday-export-readback.json and android-birthday-form1040-page2.png. No vendor runtime or vendor return fixture was used.
