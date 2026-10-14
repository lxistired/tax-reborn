# Dividend migration and original final-summary dependencies

The App adds a working six-box1099-DIV plaintext TaxML migration. Native Mac and an actual browser worker have completed file selection, review, edits, corrected XML download, addition, calculation, save and reopen. Source receipts and reviewed snapshots survive editing; editing current amounts clears review. The original source remains a separate attachment. See [the exact supported workflow](TAXML_DIVIDEND_IMPORT.md).

Original F1099D metadata and mapping bytes independently bind Boxes1a/1b/2a/2b/2d/4 to L1B/QDIV/L1C/L2C/L1CTX/L2. The App uses independently authored code and official IRS rules. Vendor carriers, decompiler output and original calculation programs stay private.

The private REA work has now joined these bounded source paths:

- Raw interest, dividends and capital distributions through investment-income, taxable-income and capital-tax calculations; raw INT/DIV withholding is summed in cents before whole-dollar payment fields.
- Separate BDIV and TEMPGD record identities, selected source metadata association and same-UUID writes. Manual owner/factory context and scheduling remain explicit.
- The original final-summary mapping distinguishes overpayment L66, refund L67A, estimated-tax application L68 and amount owed L69. Earlier zero-application profiles that stopped at L66 established overpayment. They did not by themselves establish final refund execution.
- Complete final-summary programs now produce refund565 on the selected wages5000/interest1000/ordinary-dividends1000/capital-distributions60000/withholding1000 profile. The corresponding ordinary source tax is435. A separate80000 distribution profile produces3435 tax and2435 owed when its voucher already exists.
- The original STATUS13006 program produces DOSUMMARY from the presence of one of FINFOWKS.FS1–FS5 before final summary. The finite replay supplies filing facts and phase order explicitly; DOSUMMARY is no longer injected into that profile. Automatic form creation and complete controller execution remain open.

The independent [IRS capital fixtures](../fixtures/capital_fifteen_final_summary_2025.json) and [App check](../scripts/verify_capital_final_summary_2025.py) cover14 supported cases, including nonzero15% capital tax, unused deductions, whole-dollar boundaries, payments, refund and owed branches. They are independently authored facts and expected amounts. They contain no original compiled programs. The actual frozen Mac HTTP engine passed the same14 checks. Input/result preparation acceptance, native UI acceptance and original-program acceptance are separate evidence states.

Original byte audits also closed the selected Windows scalar/cache/setter/load-context and record-home branches, with distinct metadata, value header and loading mode. A RowUUID body codec does not establish that the ordinary saver writes it: the original ordinary traversal excludes that object type. Historical Date restoration also separates retained text from final used presence and separates a cleared return error from a successful field write. The App continues to refuse unsupported arrays, PO references and active flags, and independently validates dates.

Original-program executions and validated original saved .tax fixtures remain zero. These are original-byte-driven finite graph/VM and native-call models. They do not establish universal .tax compatibility, native original execution, pixel parity, electronic filing or a complete substitute. Three REA lanes continue on higher-income NIIT/AMT, form factories, object ownership/serialization and post-restore readback/error mapping.

Native preview15 packages and changed-flow status are recorded in [the candidate acceptance state](../qa/native-preview15/candidate-acceptance-state.json). Generated, installed, tested, published and anonymous download/hash verification are recorded separately. The previously verified public installer release remains preview12 until the new package release gates pass.
