"""Benchmark and memory test for contract-risk-analyzer under ONNX backend.

Starts the FastAPI server with CONTRACT_RISK_BACKEND=onnx,
queries /health and /model/info,
then analyzes each PDF in legal_agreement/,
measuring response time and tracking peak Resident Set Size (RSS) memory.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
import json
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import fitz  # PyMuPDF
import psutil

def get_process_rss_mb(proc: psutil.Process) -> float:
    try:
        mem = proc.memory_info().rss
        # include children if any
        for child in proc.children(recursive=True):
            try:
                mem += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return mem / (1024 * 1024)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0.0

def main():
    venv_python = Path(sys.executable)
    print(f"Using Python: {venv_python}")

    env = os.environ.copy()
    env["CONTRACT_RISK_BACKEND"] = "onnx"
    env["CONTRACT_RISK_MOCK_MODEL"] = "false"
    env["PYTHONUNBUFFERED"] = "1"

    # Start uvicorn server on port 8009 for testing
    port = 8009
    server_cmd = [
        str(venv_python),
        "-m",
        "uvicorn",
        "contract_risk_analyzer.api.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]

    print(f"Starting server on port {port}...")
    proc = subprocess.Popen(server_cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    ps_proc = psutil.Process(proc.pid)

    peak_rss = 0.0
    start_time = time.time()

    try:
        # Wait for server to come up
        ready = False
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as resp:
                    if resp.status == 200:
                        ready = True
                        break
            except Exception:
                time.sleep(0.5)
            rss = get_process_rss_mb(ps_proc)
            if rss > peak_rss:
                peak_rss = rss

        if not ready:
            print("ERROR: Server failed to start within 15 seconds.")
            out, _ = proc.communicate(timeout=2)
            print("Server output:\n", out)
            sys.exit(1)

        print("Server is up and responsive!")
        rss = get_process_rss_mb(ps_proc)
        if rss > peak_rss:
            peak_rss = rss
        print(f"Initial server RSS: {rss:.2f} MB")

        # Query /model/info
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/model/info", timeout=5) as resp:
            info = json.loads(resp.read().decode())
            print(f"/model/info response: backend={info.get('active_backend')}, model={info.get('model_name')}, loaded={info.get('model_loaded')}")

        # Test each PDF in legal_agreement/
        pdf_dir = Path("legal_agreement")
        pdf_files = sorted(list(pdf_dir.glob("*.pdf")))
        print(f"\nFound {len(pdf_files)} PDF agreements to analyze:")

        timings = []
        for pdf_path in pdf_files:
            # Extract text
            doc = fitz.open(str(pdf_path))
            text = "\n".join(page.get_text() for page in doc)
            doc.close()

            req_data = json.dumps({"text": text, "document_id": pdf_path.stem}).encode("utf-8")
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/analyze/document",
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            t0 = time.perf_counter()
            with urllib.request.urlopen(req, timeout=30) as resp:
                res = json.loads(resp.read().decode())
            latency = time.perf_counter() - t0
            timings.append((pdf_path.name, latency, res.get("total_clauses", 0), len(res.get("risk_flags", []))))

            rss = get_process_rss_mb(ps_proc)
            if rss > peak_rss:
                peak_rss = rss

            print(f"  - {pdf_path.name}: {latency:.3f}s, clauses={res.get('total_clauses')}, flags={len(res.get('risk_flags'))}, current RSS={rss:.2f} MB")

        print("\n" + "=" * 60)
        print("PERFORMANCE & MEMORY BENCHMARK REPORT:")
        print(f"Total documents tested: {len(pdf_files)}")
        for name, lat, clauses, flags in timings:
            print(f"  {name:<40}: {lat*1000:6.1f} ms ({clauses} clauses, {flags} flags)")
        avg_lat = sum(t[1] for t in timings) / len(timings) if timings else 0.0
        print(f"Average latency per document: {avg_lat*1000:.1f} ms ({avg_lat:.2f} s)")
        print(f"PEAK RESIDENT MEMORY (RSS): {peak_rss:.2f} MB")
        print("Render Free Plan Limit:      512.00 MB")
        print("Target Ceiling:              420.00 MB")
        if peak_rss < 420.0:
            print("STATUS: PASS (Well within 420 MB safety ceiling!)")
        else:
            print("STATUS: WARNING (Exceeded 420 MB target)")
        print("=" * 60)

    finally:
        print("Stopping server...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("Server stopped cleanly.")

if __name__ == "__main__":
    main()
