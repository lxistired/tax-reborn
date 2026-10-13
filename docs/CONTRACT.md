# Shared API contract

This is a historical interface summary. The current exact input schema, eligibility gates, row templates and capability limits are returned by GET `/api/schema`; do not use the shortened example below to infer qualification or set missing source values to zero.

`tax_engine.calculate_return(data)` returns JSON-compatible data or raises `ValueError` for structurally invalid inputs. `tax_engine.default_return()` returns a blank valid shape. `tax_engine.demo_returns()` returns named synthetic return inputs. All submitted money uses decimal strings in USD; calculated fields are whole-dollar IRS values. Tax year must be 2025. Engine result has `tax_year`, `currency`, `filing_status`, `lines` (Form 1040 keys `1a`, `2a`, `2b`, `3a`, `3b`, `4a`, `4b`, `5a`, `5b`, `6a`, `6b`, `7a`, `8`, `9`, `10`, `11a`, `11b`, `12e`, `13a`, `13b`, `14`, `15`, `16`, `17`, `18`, `19`, `20`, `21`, `22`, `23`, `24`, `25a`, `25b`, `25c`, `25d`, `26`, `27a`, `28`, `29`, `30`, `31`, `32`, `33`, `34`, `35a`, `36`, `37`, `38`), `summary` with `agi`, `taxable_income`, `total_tax`, `payments`, `refund`, `amount_owed`, `deduction_type`, `effective_rate`, `schedules`, `trace` list of `{label, amount, source}`, `warnings` list of human-readable strings, `blocking_issues` list of human-readable strings, `can_prepare` boolean. Additional fields allowed.

Input shape:
```
{
 "tax_year":2025,
 "name":"Synthetic Household", "filing_status":"single|mfj|mfs|hoh|qss",
 "taxpayer":{"age":35,"blind":false,"can_be_claimed":false,"valid_ssn":true},
 "spouse":{"age":35,"blind":false,"valid_ssn":true},
 "dependents":[{"name":"Child","age":8,"qualifying_child":true,"valid_ssn":true}],
 "w2":[{"employer":"Example","wages":"60000","federal_withholding":"6500","social_security_wages":"60000","medicare_wages":"60000","social_security_withholding":"3720"}],
 "interest":[{"payer":"Bank","taxable":"100","tax_exempt":"0","federal_withholding":"0"}],
 "dividends":[{"payer":"Broker","ordinary":"100","qualified":"50","capital_gain_distributions":"0","federal_withholding":"0"}],
 "capital_gains":[{"description":"Stock","term":"short|long","proceeds":"1000","cost_basis":"800","adjustment":"0"}],
 "businesses":[{"name":"Consulting","revenue":"10000","expenses":"2000","owner":"taxpayer|spouse"}],
 "retirement":{"ira_gross":"0","ira_taxable":"0","pension_gross":"0","pension_taxable":"0","social_security":"0","federal_withholding":"0"},
 "other_income":{"unemployment":"0","other":"0","federal_withholding":"0"},
 "adjustments":{"student_loan_interest":"0","ira_deduction":"0","hsa_deduction":"0","self_employed_health_insurance":"0"},
 "itemized":{"medical":"0","state_local_tax":"0","mortgage_interest":"0","charity":"0","investment_interest":"0"},
 "schedule_1a":{"qualified_tips":"0","qualified_overtime":"0","qualified_car_loan_interest":"0","eligibility_confirmed":false},
 "payments":{"estimated":"0","prior_year_credit":"0"},
 "unsupported":[], "notes":""
}
```
Engine must document any changes to this contract and notify app/root/acceptance workers promptly. IRA/HSA/medical/mortgage deduction eligibility not established by a submitted number must be flagged or explicitly acknowledged; don't silently assume it.

Server API:
- GET `/api/schema` -> `{default_return, demos, capabilities}`
- POST `/api/calculate` with return input -> engine result
- GET `/api/returns` -> `{returns:[{id,name,updated_at,summary}]}`
- GET `/api/returns/{id}` -> `{id,data,result,updated_at}`
- POST `/api/returns` with `{id?:string,data:input}` -> same saved object
- DELETE `/api/returns/{id}` -> `{ok:true}`
- GET `/api/returns/{id}/export.json` -> downloadable input + result
- GET `/api/returns/{id}/worksheet.html` -> downloadable print worksheet (not a filed return)
- GET `/api/health` -> version/platform/scope.

No external CDN or runtime cloud calls. Persistent saves go to private user application data outside source. The mobile layout must retain calculation, save, document list, review and export controls. Use responsive CSS plus PWA manifest/service worker for mobile browser install; don't claim native IPA/APK builds if absent. Desktop pywebview shell and Mac .app packaging owned by root.

## Extensions added2026-10-13

`default_return` now contains identity, EITC, NIIT, AMT, rentals, IRA, HSA, education, Marketplace, care, saver and elderly-credit objects. UI fields and repeat-row templates are machine-readable in capabilities. These modules flow through the same actual computation and saved return; a disabled module with monetary data is blocked.

The48 original1040 numeric keys remain stable. `additional_lines` holds `1e` taxable dependent-care benefits and `1z` total wages; the latter is1a+1e. `not_computed_lines` identifies uncomputed line38. `schedules` contains actual detailed workpapers. `form_readiness` independently reports missing identity and an incomplete filing packet. `can_prepare` reports supported arithmetic eligibility, not permission to sign/mail/file.

Additional endpoints:

- GET `/api/returns/{id}/form1040.pdf`: interactive official2025 Form1040 numerical/identity draft plus calculation workpapers.
- GET `/api/returns/{id}/states`: saved state inputs, separate from federal input.
- POST same path with `{jurisdiction,input}`: saves a state input copy. Tax year and31-state schema validation are performed by the pinned local state worker before UI submission.
- `export.json` includes these state inputs; restores create a new UUID, recalculate with current rules and report partial state restore failures. It does not contain local document attachments.

Offline mode uses the same Python modules in Pyodide3.13.2 and on-device IndexedDB. Its local worker provides PDF generation/text extraction, without a loopback tax API. Image extraction uses bundled local Tesseract; every candidate requires review. `Offline availability` separately checks cached engine/PDF/OCR/state assets. APKassets are bundled and have no INTERNET permission; physical Android and nativeiOS status must be recorded separately.
