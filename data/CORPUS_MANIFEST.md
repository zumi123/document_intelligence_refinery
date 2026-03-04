# Data corpus — Document Intelligence Refinery

The `data/` folder contains the provided document set for pipeline validation. The challenge requires processing **at least four document classes** with **minimum 3 documents per class** for interim artifacts (profiles, ledger) and final deliverables.

## Corpus location

- **Path**: `data/` (project root)
- **Format**: PDFs

## Document classes (challenge mapping)

Use these for “minimum 3 per class” and for class-specific testing/demos.

| Class | Description | Example files in `data/` |
|-------|-------------|---------------------------|
| **A** | Annual Financial Report (native digital) | `CBE ANNUAL REPORT 2023-24.pdf`, `CBE Annual Report 2018-19.pdf`, `CBE Annual Report 2017-18.pdf`, … |
| **B** | Scanned government/legal (image-based) | `Audit Report - 2023.pdf`, `2018_Audited_Financial_Statement_Report.pdf`, `2019_Audited_Financial_Statement_Report.pdf`, … |
| **C** | Technical assessment report (mixed) | `fta_performance_survey_final_report_2022.pdf` |
| **D** | Structured data / table-heavy | `tax_expenditure_ethiopia_2021_22.pdf`, `Consumer Price Index September 2025.pdf`, … |

## Suggested subsets for development

- **Triage + extraction testing (12 docs for interim)**:  
  Pick ≥3 from each class, e.g.  
  - A: `CBE ANNUAL REPORT 2023-24.pdf`, `CBE Annual Report 2018-19.pdf`, `CBE Annual Report 2016-17.pdf`  
  - B: `Audit Report - 2023.pdf`, `2018_Audited_Financial_Statement_Report.pdf`, `2020_Audited_Financial_Statement_Report.pdf`  
  - C: `fta_performance_survey_final_report_2022.pdf` (+ 2 more mixed/technical if available)  
  - D: `tax_expenditure_ethiopia_2021_22.pdf`, `Consumer Price Index September 2025.pdf`, `Consumer Price Index July 2025.pdf`

- **Demo / video**: Use a document **not** used for tuning (or one outside the corpus), as per the demo protocol.

## File count

Run from project root:

```bash
find data -maxdepth 1 -name "*.pdf" | wc -l
```

There are 50+ PDFs in `data/`; use the classes above to select the required minimum per class.
