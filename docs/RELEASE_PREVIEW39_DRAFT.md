# Tax Reborn Preview.39 — unpublished experimental-preview candidate

**Status on 2026-10-17:** this is a release-staging record, not a published release. There is no Preview.39 tag, release page, uploaded asset, or anonymous public-download readback. Preview.38 remains the current public prerelease.

## Candidate scope

The candidate base is runtime commit `2eb2f4963b1e9ffe85867ec3ba839436055edeee`. It adds a local default-encrypted import route for **owned fictional Type0 fixtures**. A caller may select a local compatibility configuration, or use the packaged fictional configuration for the matching public sample. The route inventories archive members, requires an acknowledgement before reading supported candidates, retains the encrypted source, and keeps the selected documents in local storage.

The supported route is deliberately narrow:

- Empty identity and no `security` element are the only accepted protection shape.
- Identity-protected and password/security-protected sources are refused before document creation.
- A malformed configuration or source produces a safe local error and must not change persisted documents.
- A failed manual public configuration can be cleared by selecting the packaged fictional configuration for the matching sample.

This does not establish compatibility with an original taxpayer archive, an original program run, all tax years, all container variants, original calculation results, export/write compatibility, or electronic filing. The project has no original 2025 encrypted-taxpayer fixture. ZIP64 input is not implemented in this candidate.

## Evidence retained for approval review

The Windows focused native check used the already-produced production artifact from workflow run `38902890753` (producing source `c2adffa8595fa7e5030f0ff340832d802fc2686e`). The later focused acceptance run `38909312854` reused that exact package; it did not rebuild a Preview.39 package. In the visible user path, the packaged fictional source was opened, acknowledged, reviewed, a W-2 was added and changed to $60,000 wages / $5,000 withholding, then saved and reopened. The visible reopened result showed $75 owed. The final Windows receipt is private and is bound to the production artifact and its screenshots.

The browser regression ran the same candidate runtime in both HTTP/SQLite and actual Pyodide/IndexedDB modes. It checks four refusals, a wrong-manual-config error with unchanged saved document hashes, packaged-preset recovery, inventory, acknowledgement, reader output, W-2 edit, save, and reopen. Its receipt is private. These checks use owned fictional fixtures and public fictional configuration values only.

Cache-63 Mac and Android packages were generated and their package/signing identities were recorded. Their final evidence is an **inventory increment** for this encrypted-source route: Mac reopened the saved source and showed its inventory; Android reopened the saved source, selected the public profile and ordered carriers, and showed the reader structure. Neither record is a new complete native import/edit/save/reopen chain for Preview.39. No platform package is staged for release here.

## Publication gates still open

A future release requires all of the following after explicit approval:

1. freeze an exact candidate source commit and Source ZIP;
2. build new platform artifacts from that source, rather than re-labeling the older Windows production artifact;
3. bind each package's embedded runtime to that source and rerun only the appropriate platform acceptance;
4. upload assets, perform anonymous full-download hash/CRC readback, and record those results; and
5. obtain release approval.

Until then, the local Source ZIP and asset manifest are staging materials only. They do not represent a public Preview.39 download.

## Safety and product boundary

No vendor key, vendor binary, decompiler output, personal tax return, or private compatibility material belongs in the public source or release assets. The app remains an independent US tax-year-2025 preparation preview. Electronic filing, payment, professional representation, and IRS acceptance are unavailable.
