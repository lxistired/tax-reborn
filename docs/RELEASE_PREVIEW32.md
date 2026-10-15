# Preview32 — source-derived interest adjustments

The main App now offers **Compare proposed interest adjustments** after source inspection. It calculates nine supported source temporary fields and their bounded adjustment path through Schedule B L4 and Form1040 L8A. Loaded fields, a calculated baseline using saved ADJUST, and proposed amounts are displayed separately. The independent IRS return and source remain unchanged.

An owned $12.34 accrued-interest case changes the calculated L4/L8A baseline $1,822.68/$1,823 to the proposed $1,810.34/$1,810. A current L8A override remains in effect. Any existing Used ADJUST, including zero, is refused. Unsupported native blank deletion and temporary Override cases remain refused; retained temporary operands stay identified. The original saved-adjustment comparison remains available.

Android now accepts all URIs when its system picker returns ClipData without a single data URI. The local calculation picker explicitly accepts binary resources. Saved inspected source attachments have an **Open source** action that reopens their source, explicit profile and bound registry files.

## Actual validation

- Mac ARM64 and a real Android device selected the owned source, seven complete registries and two complete local original resources, ran the new projection, and saved the full 693,329-byte audit through their system dialogs. Those files match the actual HTTP/SQLite and Pyodide/IndexedDB App audits byte for byte. These are synthetic source cases, not licensed-original runtime or original taxpayer-file comparisons.
- Mac normal quit/relaunch retained all 17 saved returns and 16 preparation records. Android retained its original signer/install identity and an identical complete 33,114-byte, seven-section return backup, including the existing $344 refund estimate.
- Windows x64 Setup installed successfully. The installed executable passed 21 smoke checks, 17 actual native GUI workflows, and the 146-module source reader's eight owned invalid-resource/session/recovery checks. **The new positive original-resource case was not supplied to Windows CI.** All 325 web assets match Mac, Android and source.
- 754 host tests and 643 actual Pyodide tests passed; two explicit skips remain. Independent review covered source pairing, confirmation, stale replies, real File/digest waits, refusal recovery and one actual source parse per action. The original comparison's complete 1,036,476-byte audit remains unchanged.

[Machine-readable acceptance](../qa/native-preview32/acceptance.json) · [Workflow and limitations](SOURCE_INTEREST_COMPARISON.md) · [Maintainer @lxistired](https://github.com/lxistired)

## Scope still open

These are finite read-only source projections. Complete native output conversion/write/reload, current inventory/UUID mapping, the dependency queue, the remaining tax sequence and full original .tax compatibility remain unverified. Original resources and private audits are not distributed. The main return uses independently written IRS rules; e-file is unavailable. Windows x64, Mac ARM64 and Android packages are supplied. No new iOS package or Intel Mac native acceptance is claimed.
