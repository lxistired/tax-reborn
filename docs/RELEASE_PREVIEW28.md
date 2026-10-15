# Preview.28: complete saved-document object preservation

The App now corrects existing supported numeric fields while retaining the separate Entity and per-FormSet persistent-object lists, all ValueForm tails, nonempty indexed tables, child forms and links. An explicit v6 source profile supplies every factory; no object-tail guessing is performed. Stored metadata remains read-only source content and never supplies active calculation values.

The fictional end-to-end source has two FormSets, eight forms, eight links, three Entity objects and two objects per FormSet. The first FW2 wage correction1234.56→1234.57 produces the same complete8110-byte file on actual Windows, Mac and Android. The second FormSet wages remain1234.56. Exact raw object bodies and repeated metadata rows survive the shift. Unknown classes and unmodeled versions block relocation.

[Feature scope and workflow](BINARY_PERSISTENT_DOCUMENT_SOURCE.md) · [Platform acceptance](../qa/native-preview28/acceptance.json) · [Actual Windows run](https://github.com/lxistired/tax-reborn/actions/runs/38741378611).

Validation:720host checks;609actual Pyodide executions with2explicit skips. Independent review adds48host and48actual WebAssembly inputs, plus11old-profile complete JSON baselines. Actual Chrome desktop and390px workflows save/reload four reviewed income records and refund344. Windows passes14focused native GUI checks and21installed frozen checks. Mac normal quit/reopen and complete SQLite input readback pass; the readonly DMG equals the tested App across610file/symlink paths. Android preserves its signing identity, installation and existing current input; its new system-saved complete JSON backup independently recalculates to the same saved344. All158web source assets match the Windows portable, Mac App and pulled installed Android APK.

Native production commit:10da24d5e465ed7e79b8c5862a0b76a477b1efe9. Documentation/acceptance receipts may be committed later without changing compiled runtime bytes. Packaging manifests retain their generation-time status; the acceptance record captures later actual platform tests. Publication and complete anonymous downloads are separate final checks.

The selected Entity profile does not establish general original .tax container compatibility. Original licensed runtime executions and original taxpayer fixtures remain zero. Native object factories, metadata cleanup/migration, original global recalculation, e-filing and full pixel parity remain unverified. Mac release is Apple Silicon; Intel Mac and iOS are not added by this version.
