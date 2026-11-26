import json
import os
from pathlib import Path

os.environ["CONTRACT_RISK_MOCK_MODEL"] = "false"
os.environ["HF_HUB_OFFLINE"] = "1"

from fastapi.testclient import TestClient

from contract_risk_analyzer.api.main import app

client = TestClient(app)

print("=== 1. GET /health ===")
r_health = client.get("/health")
print(f"Status: {r_health.status_code}")
print(json.dumps(r_health.json(), indent=2))

print("\n=== 2. GET /model/info ===")
r_info = client.get("/model/info")
print(f"Status: {r_info.status_code}")
print(json.dumps(r_info.json(), indent=2))

print("\n=== 3. POST /analyze/clause (Delaware sentence) ===")
delaware_text = "This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware."
r_clause = client.post("/analyze/clause", json={"text": delaware_text})
print(f"Status: {r_clause.status_code}")
clause_data = r_clause.json()
print(f"Predicted Label: {clause_data['predicted_label']}")
print(f"Confidence: {clause_data['confidence']}")
print(f"Top-k Labels: {clause_data['top_k_labels']}")
print(f"Risk Flags: {len(clause_data['risk_flags'])}")

print("\n=== 4. POST /analyze/document (data/samples/sample_contract.txt) ===")
sample_doc_path = Path("data/samples/sample_contract.txt")
with open(sample_doc_path, encoding="utf-8") as f:
    doc_text = f.read()

r_doc = client.post("/analyze/document", json={"document_id": "sample-doc-1", "text": doc_text})
print(f"Status: {r_doc.status_code}")
doc_data = r_doc.json()
print(f"Overall Risk Score: {doc_data.get('overall_risk_score')}")
print(f"Total Clauses: {doc_data.get('total_clauses')}")
print(f"Total Risk Flags: {len(doc_data.get('risk_flags', []))}")
print("Top 5 Clause Predictions:")
for i, pred in enumerate(doc_data.get("clause_predictions", [])[:5]):
    print(f"  Clause {i+1} ({pred['clause_id']}): {pred['predicted_label']} (confidence: {pred['confidence']})")
