import json
import os

os.environ["CONTRACT_RISK_MOCK_MODEL"] = "false"
os.environ["CONTRACT_RISK_CLASSIFIER"] = "legalpro"
os.environ["CONTRACT_RISK_MODEL_CONFIG"] = "configs/ledgar_sra.yaml"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

from contract_risk_analyzer.api.routes import analyze_clause, analyze_document, health, model_info
from contract_risk_analyzer.api.schemas import ClauseAnalyzeRequest, DocumentAnalyzeRequest
from contract_risk_analyzer.modeling.predict import predict_clauses
from contract_risk_analyzer.preprocessing.chunking import split_into_clauses

print("--- 1. GET /health ---")
print(json.dumps(health(), indent=2))

print("\n--- 2. GET /model/info ---")
print(json.dumps(model_info().model_dump(), indent=2))

print("\n--- 3. POST /analyze/clause (Delaware sentence) ---")
delaware_text = "This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware."
clause_res = analyze_clause(ClauseAnalyzeRequest(text=delaware_text))
print("predicted_label:", clause_res.predicted_label)
print("confidence:", round(clause_res.confidence, 4))
print("risk_flags count:", len(clause_res.risk_flags))
for f in clause_res.risk_flags:
    print(f"  Flag: {f.flag_type} [{f.severity}] - {f.reason}")

print("\n--- 4. POST /analyze/document (data/samples/sample_contract.txt) ---")
with open("data/samples/sample_contract.txt", encoding="utf-8") as f:
    text = f.read()

doc_res = analyze_document(DocumentAnalyzeRequest(document_id="sample-contract-1", text=text))
print("overall_risk_score:", doc_res.overall_risk_score)
print("total_clauses:", doc_res.total_clauses)
print("total_risk_flags:", len(doc_res.risk_flags))
print("severity_breakdown:", doc_res.severity_breakdown)

clauses = split_into_clauses(text, document_id="sample-contract-1")
preds = predict_clauses(clauses, mock=False, backend="legalpro")
print("\nTop 5 Clause Predictions:")
for i, pred in enumerate(preds[:5]):
    print(f"  Clause {i+1} ({pred.clause_id}): '{pred.predicted_label}' (confidence: {round(pred.confidence, 4)})")
