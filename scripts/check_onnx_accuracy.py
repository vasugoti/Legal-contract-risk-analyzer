import os
from pathlib import Path
import numpy as np
import torch
import onnxruntime as ort
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from datasets import Dataset

def main():
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    os.environ["TRANSFORMERS_VERBOSITY"] = "error"

    pytorch_dir = "NLP/LEDGAR_SRA"
    onnx_dir = "NLP/LEDGAR_SRA_ONNX"
    onnx_model_path = os.path.join(onnx_dir, "model_int8.onnx")

    print(f"Loading PyTorch model from {pytorch_dir}...")
    tokenizer = AutoTokenizer.from_pretrained(pytorch_dir, local_files_only=True)
    pt_model = AutoModelForSequenceClassification.from_pretrained(pytorch_dir, local_files_only=True)
    pt_model.eval()

    print(f"Loading ONNX INT8 session from {onnx_model_path}...")
    sess_opts = ort.SessionOptions()
    sess_opts.intra_op_num_threads = 1
    sess_opts.inter_op_num_threads = 1
    ort_session = ort.InferenceSession(onnx_model_path, sess_opts, providers=["CPUExecutionProvider"])

    # Load from local cached arrow file
    home = Path.home()
    arrow_path = home / ".cache" / "huggingface" / "datasets" / "coastalcph___lex_glue" / "ledgar" / "0.0.0" / "c23fdff1a6bf74e0e1a71cb86f1e781d37da888c" / "lex_glue-test.arrow"
    print(f"Loading 300 test clauses from local cached arrow: {arrow_path}...")
    ds = Dataset.from_file(str(arrow_path))
    samples = ds.select(range(300))

    texts = samples["text"]
    true_labels = samples["label"]

    pt_correct = 0
    onnx_correct = 0
    agreement_count = 0

    print("Evaluating 300 samples across PyTorch and ONNX INT8...")
    with torch.no_grad():
        for i, text in enumerate(texts):
            encoded = tokenizer(
                text,
                padding=False,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            input_ids = encoded["input_ids"]
            attention_mask = encoded["attention_mask"]

            # PyTorch inference
            pt_out = pt_model(input_ids=input_ids, attention_mask=attention_mask)
            pt_pred = int(torch.argmax(pt_out.logits, dim=1).item())

            # ONNX inference
            onnx_inputs = {
                "input_ids": input_ids.numpy(),
                "attention_mask": attention_mask.numpy(),
            }
            onnx_out = ort_session.run(["logits"], onnx_inputs)
            onnx_pred = int(np.argmax(onnx_out[0], axis=1)[0])

            true_label = true_labels[i]
            if pt_pred == true_label:
                pt_correct += 1
            if onnx_pred == true_label:
                onnx_correct += 1
            if pt_pred == onnx_pred:
                agreement_count += 1

    pt_acc = pt_correct / 300.0 * 100.0
    onnx_acc = onnx_correct / 300.0 * 100.0
    agreement_pct = agreement_count / 300.0 * 100.0

    print("=" * 60)
    print("STEP 2 ACCURACY CHECK RESULTS (300 LEDGAR TEST CLAUSES):")
    print(f"  PyTorch Accuracy:   {pt_acc:.2f}% ({pt_correct}/300)")
    print(f"  ONNX INT8 Accuracy: {onnx_acc:.2f}% ({onnx_correct}/300)")
    print(f"  Top-1 Agreement:    {agreement_pct:.2f}% ({agreement_count}/300)")
    print("=" * 60)

    if agreement_pct < 97.0:
        print(f"ERROR: Agreement {agreement_pct:.2f}% is below 97% threshold!")
        exit(1)
    else:
        print("PASS: Agreement is >= 97.0%!")

if __name__ == "__main__":
    main()
