from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from contract_risk_analyzer.api.routes import router
from contract_risk_analyzer.config.settings import load_yaml

config = load_yaml("configs/api.yaml")

app = FastAPI(
    title=config["service"]["title"],
    version=config["service"]["version"],
    description="NLP document intelligence service for contract clause analysis and risk triage.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.post("/extract-text")
async def extract_text(file: UploadFile = File(...)):
    """Extract plain text from an uploaded PDF, DOCX or TXT contract."""
    data = await file.read()
    name = (file.filename or "").lower()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 10 MB).")
    try:
        if name.endswith(".pdf"):
            import fitz  # PyMuPDF
            doc = fitz.open(stream=data, filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)
        elif name.endswith(".docx"):
            import io, docx
            d = docx.Document(io.BytesIO(data))
            text = "\n".join(p.text for p in d.paragraphs)
        elif name.endswith(".txt"):
            text = data.decode("utf-8", errors="ignore")
        else:
            raise HTTPException(400, "Only PDF, DOCX or TXT files are supported.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Could not read file: {e}")

    if len(text.strip()) < 50:
        raise HTTPException(400, "No text found. Is this a scanned PDF? Please use a digital PDF.")
    return {"filename": file.filename, "characters": len(text), "text": text}


web_dir = Path(__file__).resolve().parent.parent / "web"
if web_dir.exists():
    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")


