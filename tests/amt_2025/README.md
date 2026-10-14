# IRS 2025 AMT regression cases

This offline check runs Tax Reborn's standard-deduction configuration, ordinary or qualified-dividend regular tax, and alternative minimum tax against 825 synthetic expected cases. Expected values were calculated independently from IRS primary worksheets. App output was never the oracle.

Run from the repository root, after placing these files together in `tests/amt_2025/`:

```sh
python3 tests/amt_2025/check_amt_2025.py --app-root .
```

The result is machine-readable JSON. A failure exits with status 1 and prints the case inputs, expected amounts and actual amounts. No network, account, license, proprietary program, tax archive or private analysis workspace is required.

The suite covers 300 ordinary AMT cases and 525 qualified-dividend AMT cases across single, joint, married-separate, head-of-household and qualifying-surviving-spouse statuses. It includes exemption phaseout, the married-separate AMTI increment, 26%/28% AMT brackets and 0%/15%/20% qualified-dividend transitions. Inputs and outputs are whole USD dollars; written form and worksheet lines are rounded to whole dollars.

The input boundary is synthetic AGI, an already eligible qualified-dividend amount and an already quantified additional ISO adjustment. Standard deduction, under age 65, no blindness/dependents and a resident federal return are explicit case assumptions. This check isolates the supported worksheets. It does not validate raw securities or option basis, foreign exclusions/credits, 25%/28% capital gains, itemized/QBI/Schedule 1-A deductions, other AMT preferences, a complete return or e-filing.

Primary sources:

- [IRS 2025 Form 6251](https://www.irs.gov/pub/irs-pdf/f6251.pdf), Parts I–III.
- [IRS 2025 Instructions for Form 6251](https://www.irs.gov/pub/irs-pdf/i6251.pdf), AMTI adjustment, exemption phaseout and rates.
- [IRS 2025 Instructions for Form 1040](https://www.irs.gov/pub/irs-pdf/i1040gi.pdf), standard deduction, tax table/computation worksheet and qualified dividends.

A separate private reverse-engineering investigation also evaluated complete original compiled resource programs against these independent IRS expectations. Those programs, tables and native bodies are excluded here. Original vendor runtime execution count is zero.
