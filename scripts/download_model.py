#!/usr/bin/env python3
"""Download ONNX model files for Render deployment.

Uses only Python standard library (urllib.request).
Downloads 4 files from $env:MODEL_BASE_URL (or command-line argument) into NLP/LEDGAR_SRA_ONNX/:
- model_int8.onnx
- config.json
- tokenizer.json
- tokenizer_config.json

Skips files that already exist locally.
"""

from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

FILES = [
    "model_int8.onnx",
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
]


def download_model(base_url: str | None = None, target_dir: str | Path = "NLP/LEDGAR_SRA_ONNX") -> None:
    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)

    url_base = base_url or os.getenv("MODEL_BASE_URL")
    if not url_base:
        print("ERROR: MODEL_BASE_URL environment variable (or argument) is not set.")
        print("Usage: python scripts/download_model.py <base_url>")
        sys.exit(1)

    url_base = url_base.rstrip("/")

    print(f"Target directory: {target_path.resolve()}")
    print(f"Base URL: {url_base}")

    for filename in FILES:
        file_path = target_path / filename
        if file_path.exists() and file_path.stat().st_size > 0:
            print(f"[SKIP] {filename} already exists ({file_path.stat().st_size:,} bytes).")
            continue

        file_url = f"{url_base}/{filename}"
        print(f"[DOWNLOADING] {filename} from {file_url}...")
        try:
            urllib.request.urlretrieve(file_url, str(file_path))
            print(f"[OK] Downloaded {filename} ({file_path.stat().st_size:,} bytes).")
        except Exception as exc:
            print(f"[ERROR] Failed to download {filename}: {exc}")
            if file_path.exists():
                file_path.unlink()
            sys.exit(1)

    print("All required model files are present.")


if __name__ == "__main__":
    arg_url = sys.argv[1] if len(sys.argv) > 1 else None
    download_model(base_url=arg_url)
