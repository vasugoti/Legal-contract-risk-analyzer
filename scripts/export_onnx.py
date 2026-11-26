import os
import shutil
from pathlib import Path
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from onnxruntime.quantization import quantize_dynamic, QuantType

def export_and_quantize():
    src_dir = Path("NLP/LEDGAR_SRA")
    out_dir = Path("NLP/LEDGAR_SRA_ONNX")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading PyTorch model from {src_dir}...")
    tokenizer = AutoTokenizer.from_pretrained(str(src_dir), local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(str(src_dir), local_files_only=True)
    model.eval()

    raw_onnx_path = out_dir / "model.onnx"
    int8_onnx_path = out_dir / "model_int8.onnx"

    print(f"Exporting raw ONNX model to {raw_onnx_path}...")
    dummy_input = tokenizer(
        "This is a sample contract clause for onnx export.",
        return_tensors="pt",
        padding="max_length",
        max_length=128,
        truncation=True,
    )

    input_names = ["input_ids", "attention_mask"]
    dynamic_axes = {
        "input_ids": {0: "batch_size", 1: "sequence_length"},
        "attention_mask": {0: "batch_size", 1: "sequence_length"},
        "logits": {0: "batch_size"},
    }

    torch.onnx.export(
        model,
        (dummy_input["input_ids"], dummy_input["attention_mask"]),
        str(raw_onnx_path),
        input_names=input_names,
        output_names=["logits"],
        dynamic_axes=dynamic_axes,
        opset_version=14,
        do_constant_folding=True,
    )
    print(f"Raw ONNX exported: {raw_onnx_path.stat().st_size / (1024*1024):.2f} MB")

    print(f"Applying dynamic INT8 quantization (per_channel=True) -> {int8_onnx_path}...")
    quantize_dynamic(
        model_input=str(raw_onnx_path),
        model_output=str(int8_onnx_path),
        weight_type=QuantType.QInt8,
        per_channel=True,
    )
    print(f"INT8 ONNX exported: {int8_onnx_path.stat().st_size / (1024*1024):.2f} MB")

    # Remove unquantized model.onnx and any external data to save space
    if raw_onnx_path.exists():
        raw_onnx_path.unlink()
    raw_onnx_data = out_dir / "model.onnx.data"
    if raw_onnx_data.exists():
        raw_onnx_data.unlink()

    # Copy tokenizer.json, tokenizer_config.json, config.json
    for filename in ["config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"]:
        src_file = src_dir / filename
        if src_file.exists():
            shutil.copy2(src_file, out_dir / filename)
            print(f"Copied {filename} to {out_dir}")

    print("ONNX export and INT8 quantization complete!")

if __name__ == "__main__":
    export_and_quantize()
