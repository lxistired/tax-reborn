# Tax Reborn development boundaries

Project #000002 reconstructs personal tax preparation workflows for US tax year 2025. Maintain actual calculations and local persistence; do not present unsupported tax situations as a completed return. Product comparison target: TurboTax Desktop and mobile. Original vendor binaries, art, raw decompiler output, and downloaded packages stay in `work/turbotax-re`, outside this source directory.

Use independently written code and official IRS rules. Cite fiscal year and official source for each rule. Keep an explicit blocking validation list for unimplemented tax situations. No electronic filing, payment, expert representation or licensing circumvention is implied.

Parallel work follows the REA skill's independent-question workflow. Before describing a binary artifact or function as newly recovered, compare its source identity with the existing evidence index and report only the new semantic or functional coverage. File owners: tax core worker owns `tax_engine.py`, `rules_2025.json`, `tests/test_engine.py`, `fixtures/tax_cases.json`; app worker owns `web/`; acceptance worker owns `tests/test_acceptance.py`, `fixtures/independent_cases.json`, `docs/validation.md`; root owns server, packaging, private REA analysis, integration and remaining documentation. Coordinate input/output contract before changing it.
