from fastapi.testclient import TestClient

from contract_risk_analyzer.api.main import app


def test_health(monkeypatch) -> None:
    monkeypatch.setenv("CONTRACT_RISK_MOCK_MODEL", "true")
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}


def test_analyze_clause_mock_mode(monkeypatch) -> None:
    monkeypatch.setenv("CONTRACT_RISK_MOCK_MODEL", "true")
    client = TestClient(app)
    response = client.post("/analyze/clause", json={"text": "Either party may terminate without cause."})
    assert response.status_code == 200
    payload = response.json()
    assert payload["predicted_label"] == "termination"
    assert payload["risk_flags"]


def test_analyze_document_mock_mode(monkeypatch) -> None:
    monkeypatch.setenv("CONTRACT_RISK_MOCK_MODEL", "true")
    client = TestClient(app)
    response = client.post(
        "/analyze/document",
        json={"document_id": "d1", "text": "1. Termination. Either party may terminate. 2. Payment. Customer shall pay invoices."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_clauses"] >= 1
    assert "not legal advice" in payload["disclaimer"].lower()


def test_extract_text_txt(monkeypatch) -> None:
    monkeypatch.setenv("CONTRACT_RISK_MOCK_MODEL", "true")
    client = TestClient(app)
    content = b"This is a sample contract text that has more than fifty characters to pass the minimum validation length check."
    response = client.post(
        "/extract-text",
        files={"file": ("contract.txt", content, "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "contract.txt"
    assert data["characters"] == len(content.decode("utf-8"))
    assert "sample contract text" in data["text"]


def test_extract_text_pdf(monkeypatch) -> None:
    monkeypatch.setenv("CONTRACT_RISK_MOCK_MODEL", "true")
    client = TestClient(app)
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (50, 72),
        "This is a digital PDF contract containing more than fifty characters for the unit test validation.",
        fontsize=11,
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    response = client.post(
        "/extract-text",
        files={"file": ("contract.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "contract.pdf"
    assert "digital PDF contract" in data["text"]


def test_model_info_mock_mode(monkeypatch) -> None:
    monkeypatch.setenv("CONTRACT_RISK_MOCK_MODEL", "true")
    client = TestClient(app)
    response = client.get("/model/info")
    assert response.status_code == 200
    info = response.json()
    assert info["mock_mode"] is True
    assert info["active_backend"] == "mock"


def test_model_info_tfidf_mode(monkeypatch) -> None:
    monkeypatch.setenv("CONTRACT_RISK_MOCK_MODEL", "false")
    monkeypatch.setenv("CONTRACT_RISK_CLASSIFIER", "tfidf")
    client = TestClient(app)
    response = client.get("/model/info")
    assert response.status_code == 200
    info = response.json()
    assert info["mock_mode"] is False
    assert info["active_backend"] == "tfidf"
    assert info["model_name"] == "tfidf_logistic_regression"


def test_metrics_legalpro_backend(monkeypatch) -> None:
    monkeypatch.setenv("CONTRACT_RISK_MOCK_MODEL", "false")
    monkeypatch.setenv("CONTRACT_RISK_CLASSIFIER", "legalpro")
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["active_backend"] == "legalpro"
    assert data["active_model_name"] == "LegalPro-BERT"
    assert "benchmark" in data
    bm = data["benchmark"]
    assert bm["effective_backend"] == "legalpro"
    assert "87.05%" in [c["value"] for c in bm["cards"]]


def test_metrics_tfidf_backend(monkeypatch) -> None:
    monkeypatch.setenv("CONTRACT_RISK_MOCK_MODEL", "false")
    monkeypatch.setenv("CONTRACT_RISK_CLASSIFIER", "tfidf")
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["active_backend"] == "tfidf"
    assert data["active_model_name"] == "TF-IDF + Logistic Regression"
    assert "benchmark" in data
    bm = data["benchmark"]
    assert bm["effective_backend"] == "tfidf"
    assert "83.07%" in [c["value"] for c in bm["cards"]]


