import os
from pathlib import Path

import fitz  # PyMuPDF

os.environ["CONTRACT_RISK_MOCK_MODEL"] = "false"
os.environ["CONTRACT_RISK_CLASSIFIER"] = "tfidf"
os.environ["CONTRACT_RISK_MODEL_PATH"] = "models/baseline_tfidf.joblib"

from contract_risk_analyzer.api.routes import health, model_info
from contract_risk_analyzer.modeling.predict import analyze_document_text

print("--- HEALTH ---")
print(health())

print("\n--- MODEL INFO ---")
info = model_info()
print(f"model_name: {info.model_name}, active_backend: {info.active_backend}, mock_mode: {info.mock_mode}, loaded: {info.model_loaded}")

files_to_test = [
    Path("data/samples/sample_contract.txt"),
    Path("legal_agreement/Sample_Rental_Agreement_Zero_Risk.pdf"),
    Path("legal_agreement/Sample_Rental_Agreement_Zero_Risk_v2.pdf"),
    Path("legal_agreement/Sample_Rental_Agreement_Low_Risk.pdf"),
    Path("legal_agreement/Sample_SaaS_Agreement_Low_Risk.pdf"),
    Path("legal_agreement/Sample_SaaS_Agreement_Medium_Risk.pdf"),
    Path("legal_agreement/Sample_SaaS_Agreement.pdf"),
]

results = []

for file_path in files_to_test:
    if not file_path.exists():
        continue
    if file_path.suffix.lower() == ".pdf":
        doc = fitz.open(file_path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
    else:
        text = file_path.read_text(encoding="utf-8")

    report = analyze_document_text(text, document_id=file_path.name, mock=False, backend="tfidf")
    
    # Get top 3 categories
    cats = report.category_breakdown or []
    top_3_cats = ", ".join(f"{c['flag_type']} ({c['points']}pts)" for c in cats[:3]) if cats else "None"
    
    results.append({
        "file": file_path.name,
        "clauses": report.total_clauses,
        "flags": len(report.risk_flags),
        "score": report.overall_risk_score,
        "level": report.risk_level or "N/A",
        "top_3_categories": top_3_cats,
    })

print("\n--- RESULTS TABLE ---")
print(f"{'File':<45} | {'Clauses':<7} | {'Flags':<5} | {'Score':<6} | {'Level':<8} | {'Top 3 Categories'}")
print("-" * 115)
for r in results:
    print(f"{r['file']:<45} | {r['clauses']:<7} | {r['flags']:<5} | {r['score']:<6} | {r['level']:<8} | {r['top_3_categories']}")
