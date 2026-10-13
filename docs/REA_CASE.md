# REA case: TurboTax Desktop2025 → Tax Reborn #000002

Recorded2026-10-13. Target Mac app version2025.r54.069; the executable is Intelx86_64. Official installer and original resources remain in the private research workspace and are not redistributed with Tax Reborn.

| Question | Observed evidence | Practical limit |
|---|---|---|
| What was actually inspected? | REA6.4.0 artifact inventory, Mach-O/header/signature inspection, selected Interface Builder decoding, topic-JAR inspection, selected JavaScript analysis and Ghidra decompilation of selected native functions; the earlier decoder factory was subsequently identified as media code | Inventory alone does not establish functional parity |
| What workflow definitions are shipped? | 682 topic JARs containing3,722 JSON page definitions across federal/state topics; W2topic has91 pages; web/native bridge includes topic/flow/navigation/save calls | These are vendor-authored definitions; they were not copied into the public app |
| What native UI was decoded? | A provenance-recorded subset of licensing/EasyStep/preview/save/chooser nibs:27 documents,1,749 nodes,777 edges | Static object graphs do not prove rendered pixels or licensed runtime behavior |
| What did the first native decompilation recover? | `_CreateDecoderInterface` at0x89fc4 in zlt.bundle: output-pointer checks, factory call and handle/status return. Follow-up native bodies and `ns_codec::zltCDecoderWrapper` RTTI identify a media-codec chain. | The prior tax-file-decoder attribution was incorrect. This code does not establish a .tax parser or recovered tax algorithm. |
| Was the original financial engine recovered? | A follow-up batch recovered native calculation/queue/reader functions and indexed XPRF resources, but no complete original engine or all tax formulas were recovered | Independent IRS implementation must be described separately |
| What were the JavaScript-analysis limits? | Selected3-file analysis was partial; large bundle semantic analysis exhausted heap, and native `%@` placeholders are not standalone JavaScript | A failed literal save trace is no-match evidence, not evidence the feature does not exist |
| What mobile evidence exists? | Official store material, examined mobile-demo frames, and follow-up REA analysis of a signature-verified historical Android5.10.0 APK:30 Java method bodies | The APK is historical2019 evidence, not current-release/TY2025 parity. Original IPA and a full mobile interview remain unobserved |
| What is independently usable? | Tax Reborn's own tax engine, frontend, local persistence, reviewed import, draft export and state-source integration | Complete paper/electronic filing, all long-tail situations and original pixel parity remain unverified/incomplete |

Original installer SHA256: MacDMG `1ee4cfc005a361db460e5a3afcc1f101fee187bfc856645f8ada07e1811c8511`; WindowsEXE `70d188b3ec9ce99266ca5a382f7a3601417c8a999bb5609eaf98bf4f9fa91e69`. The Windows record inspected the PE package root; it does not establish unpacked Windows runtime coverage.

REA artifact records (local evidence identifiers, not a claim of public artifact hosting): app inventory `ev_02304bff8146060b003b6f90860191b35b8e8a88206c49ad13c30209b6ccf456`; selected native UI `ev_4268ff9118e1bb8d92985ab87b22f157c76ca51bfae42f526418a069f3c1f879`; selected JavaScript `ev_f1dbbd1785f008a09b75704217f106dcb82c376cc25e8b59e8ad276a44870f41`; decoder factory `ev_78961930fe649da817913dae7c1dd3a88c0ec687ddaf050c5ae5cbc6c1b9d122`.

The public source/build must contain neither Intuit's raw resources nor original decompiler output. REA supplied evidence about packaging and workflow boundaries; it did not produce the independent federal formulas or the third-party state corpus.

## Follow-up recorded2026-10-13

REA `inspect_artifact` verified three shipped topic archives for adoption and foreign tax credits. All383 JSON members were matched to REA's child SHA256 inventory. They contain93 page definitions, alongside localization/configuration data. Static module identifiers show employer-adoption assistance and foreign-credit carryback/AMT-adjustment branches; these are broader than the independently implemented adoption-credit and limited passive-foreign-credit calculations. This is a scope comparison, not observed execution of those original branches or recovered formulas.

Retained Evidence: adoption `ev_393e92d3250e6092703784ae63f443c8b4b1f3d79aba3fddb3a3ebb6cd6e9261`; foreign_tax_credit `ev_c53e855c09e98e05d647d251db07c6d8578b315f49385600fb5dd666cb13c77b`; foreigntaxcredit `ev_6c08bad49cb1efaa5df18476f4824ce972295a396342e385723a80c232456721`. Raw original resources remain private.

Independent implementation subsequently added genuine official IRS supporting PDFs, the1040 paper details, bank/designee/checkbox persistence and a paper-preparation checklist. Those formulas and PDF mappings were written independently and tested against official2025 IRS records. They are not REA-generated Intuit source.

REA installed the final Android preview through `install_adb_package` after matching the development signing identity to the previously installed preview. `inspect_adb_package` then verified version2026.10.13-preview.3/code2026101303 and requested_permissions_count0. This is real deployment/version evidence; it does not establish OCR digit accuracy. Existing returns and the earlier camera document were reopened through the actual mobile UI after updating.

## Attribution correction and deeper native analysis — 2026-10-13

The earlier private receipt named `rea-taxfile-decoder-function-fixed.json` is genuine Ghidra output but was assigned the wrong subsystem. Further REA native dossiers follow the factory, virtual table and wrapper initialization to `CreateVppInterface`/`DestroyVppInterface`; original RTTI identifies `ns_codec::zltCDecoderWrapper`, and the Mach-O links VideoToolbox/Metal. These findings support a media-codec attribution. They do not recover .tax serialization or tax formulas. Media dossiers are excluded from the tax-function count.

The tax-file work now targets the original main executable's `MTPDocument`, `TaxDocumentInterface` and `TaxMLParser`. The computation work targets `tke::CalcEngine`, `CalculatedNode`, `DataModel`, `zCalcQueue` and `zpcExpnEvaluator`. These names are analysis candidates until a completed native function dossier confirms their actual body and relationships. A persistent, local REA MCP session keeps the same original binary loaded for bounded follow-up functions. Raw vendor pseudocode remains outside this public source.

The focused native batch subsequently completed:61 distinct original main-executable functions and4 original shell functions, deduplicated by original SHA256 and address. Counts exclude16 media functions and duplicate raw byte-window corroboration. The batch reached the actual `FullOperatorMath`, `BigFixedPoint::Round`, protobuf artifact reader/deserializer, native field-dependency queue, TaxML field builders and request/response handlers. See [the detailed batch report](REA_NATIVE_PROGRESS_20261013.md) for measured results and remaining limits. Original runtime parity is still unverified.

The historical Android batch separately inspected30 actual Java method bodies, one interface declaration and one JNI declaration through REA. Signature verification matched Intuit's first-party app-link certificate. Current mobile release bytes, native OCR bodies and server-side computation/entitlement/persistence remain open. See [Android evidence and limits](REA_ANDROID_STATIC_20261013.md).
