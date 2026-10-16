# Tax Reborn preview.38

Preview.38 is published as a prerelease at [v2026.10.16-preview.38](https://github.com/lxistired/tax-reborn/releases/tag/v2026.10.16-preview.38). The release tag points to source commit `af3a89341c64d0dc3b1bfb510101a7f6790f684d`. The packaged web runtime is bound to the same reviewed source; the platform build manifests record each package's platform-specific identity.

## Workflow

The release adds a complete source-copy workflow for the binary archive structures currently supported by the App. A user can inspect a local source, create a separate normalized copy, save it, select that saved file, and run an independent whole-document readback. Creating a source copy does not recalculate the current return. Existing tax preparation, local saving, calculations, and exports remain available.

The supported scope includes ordinary scalar and declared array values, supported group and string references, field registration changes, parent references, and stored links. Ambiguous or unsupported inputs are refused. The workflow preserves unsupported content only when the reader can establish the required structure.

## Release checks

The Windows build passed 812 host checks. The Setup installer was installed and its installed worker saved and freshly read back owned scalar and array fixtures.

The macOS arm64 and Android packages completed the interface flow through system file saving, physical-file reselection, and independent readback. Existing saved return data was checked separately. The Android update retained the existing signing identity; the desktop packages are not commercially code-signed or notarized.

The final Source ZIP was extracted and exercised in HTTP/SQLite and Pyodide/IndexedDB modes. Four malformed-input cases were refused without a download and without changing the current return. Packaged web assets and included source files were checked against the release source commit. `SHA256SUMS.txt` covers the eight accompanying artifacts.

The [public download readback](../qa/native-preview38/public-download-readback.json) records a no-authentication full GET for all nine assets. The nine files total 398,364,980 bytes. The Source ZIP is 142,655,438 bytes and contains 2,509 tracked Git blobs with verified payload hashes and CRCs.

## Boundaries

These checks use independently authored synthetic fixtures. Full compatibility with original saved TurboTax `.tax` files and equivalence to the original calculation engine remain unverified and incomplete. No licensed original-app execution or real original-taxpayer-file comparison is claimed. Electronic filing is unavailable. Preview.39 work is excluded from this release.

Matching caller-local resources, private test receipts, private backups, signing material, vendor resources, decompiler output, and personal data are outside the public source and release assets.
