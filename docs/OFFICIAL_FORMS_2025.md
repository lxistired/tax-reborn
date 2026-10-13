# Official IRS TY2025 paper preparation

The packet contains the actual public IRS2025 Form1040 template and applicable filled official supporting templates. Original IRS sources and SHA256 hashes are in forms/official-sources-2025.json; printed-line mappings are in forms/official-field-map-2025.json. Template bytes, canonical saved values and rendered widget appearances are checked after serialization. The packet preserves distinct interactive field names for repeated per-person/per-business forms.

The input module Filing details contains explicit digital-asset/home answers, refund routing/account/type, third-party designee and supporting-form source facts. Missing business classifications, expense splits, transaction dates, school/property facts and similar filing information are reported rather than invented. These facts do not replace calculation eligibility checks.

The separate paper checklist reports calculation readiness, missing facts, each actual supporting form, penalty review and signature/original withholding attachment requirements. No signature, IRS transmission or acceptance is fabricated. It uses ready_to_print_and_review only when the supported preparation facts are present. Required Schedule EIC child attachments and more-than-four-dependent continuation sheets remain explicitly blocked until generated. Individual forms can also have explicit missing factual attachments or unmapped lines.

343 independent/calculation/PDF checks passed in desktop CPython and the shipped Pyodide3.13.2 runtime on2026-10-13. The9 new1040 checks cover all five statuses, MFS spouse identity, joint dependent rows/credits, age/blindness, deposit/designee strings with leading zeros, missing-answer status and failed routing validation. Rendered visual review additionally caught and corrected a dependent-row/column mapping error. No prior golden calculation fixture was changed.

Electronic filing is a separate provider integration requiring IRS authorization and approved ATS testing. See https://www.irs.gov/e-file-providers/how-tax-preparation-software-is-approved-for-electronic-filing .
