#!/usr/bin/env python3
"""
Generate interim artifacts: 12 DocumentProfiles (min 3 per class) and extraction_ledger.jsonl.
Run from project root: python scripts/run_interim_artifacts.py
"""
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# 12 documents: 3 per class (A/B/C/D)
INTERIM_DOCS = [
    "CBE ANNUAL REPORT 2023-24.pdf",
    "CBE Annual Report 2018-19.pdf",
    "CBE Annual Report 2016-17.pdf",
    "Audit Report - 2023.pdf",
    "2018_Audited_Financial_Statement_Report.pdf",
    "2020_Audited_Financial_Statement_Report.pdf",
    "fta_performance_survey_final_report_2022.pdf",
    "20191010_Pharmaceutical-Manufacturing-Opportunites-in-Ethiopia_VF.pdf",
    "Security_Vulnerability_Disclosure_Standard_Procedure_1.pdf",
    "tax_expenditure_ethiopia_2021_22.pdf",
    "Consumer Price Index September 2025.pdf",
    "Consumer Price Index July 2025.pdf",
]


def main():
    from src.agents.triage import triage_document
    from src.agents.extractor import ExtractionRouter

    data_dir = project_root / "data"
    profiles_dir = project_root / ".refinery" / "profiles"
    ledger_path = project_root / ".refinery" / "extraction_ledger.jsonl"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    if ledger_path.exists():
        ledger_path.write_text("")

    router = ExtractionRouter(ledger_path=ledger_path)
    for name in INTERIM_DOCS:
        path = data_dir / name
        if not path.exists():
            print("Skip (not found):", name)
            continue
        print("Triage + extract:", name)
        try:
            profile = triage_document(path)
            profile_path = profiles_dir / f"{profile.document_id}.json"
            with open(profile_path, "w") as f:
                json.dump(profile.model_dump(mode="json"), f, indent=2)
            result = router.extract(path, profile)
            print(f"  -> {result.strategy_name}, confidence={result.confidence_score:.2f}")
        except Exception as e:
            print("  Error:", e)
    print("\nProfiles written to .refinery/profiles/")
    print("Ledger appended to .refinery/extraction_ledger.jsonl")


if __name__ == "__main__":
    main()
