"""Inspect AmitTewari/LegalPro-BERT-base model labels and verify mapping to LexGLUE LEDGAR."""

from __future__ import annotations

import sys

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Inspect HF model labels and verify mapping to LexGLUE LEDGAR.")
    parser.add_argument("--model", default="AmitTewari/LegalPro-BERT-base", help="Model repo or local path")
    args = parser.parse_args()

    model_id = args.model
    print(f"Loading tokenizer and model config from {model_id}...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForSequenceClassification.from_pretrained(model_id)
    model.eval()

    num_labels = model.config.num_labels
    print(f"\nModel num_labels: {num_labels}")
    if num_labels != 100:
        print(f"ERROR: Expected num_labels == 100, got {num_labels}", file=sys.stderr)
        return 1

    id2label_raw = model.config.id2label
    print("\nFirst 10 id2label entries from model config:")
    for i in range(min(10, len(id2label_raw))):
        key = i if i in id2label_raw else str(i)
        print(f"  {i}: {id2label_raw.get(key)}")

    is_generic = all(
        str(id2label_raw.get(i if i in id2label_raw else str(i), "")).startswith("LABEL_")
        for i in range(min(10, len(id2label_raw)))
    )

    if is_generic:
        print("\nModel config has generic label names (LABEL_0, LABEL_1, ...). Loading LexGLUE LEDGAR dataset...")
        try:
            import datasets

            ledgar_ds = datasets.load_dataset("coastalcph/lex_glue", "ledgar")
            ledgar_names = ledgar_ds["train"].features["label"].names
            print(f"Loaded {len(ledgar_names)} label names from coastalcph/lex_glue (ledgar).")
        except Exception as exc:
            print(f"Failed to load from Hugging Face datasets: {exc}. Trying fallback...")
            raise RuntimeError(f"Could not load coastalcph/lex_glue dataset: {exc}") from exc

        if len(ledgar_names) != 100:
            print(f"ERROR: Expected 100 LEDGAR names, got {len(ledgar_names)}", file=sys.stderr)
            return 1

        id2label = {i: name for i, name in enumerate(ledgar_names)}
        print("\nCreated mapping index -> LEDGAR name. First 10 mapped labels:")
        for i in range(10):
            print(f"  {i}: {id2label[i]}")
    else:
        print("\nModel config contains real label names! Using them directly.")
        id2label = {int(k): v for k, v in id2label_raw.items()}

    # Sanity checks on 5 obvious clauses
    test_cases = [
        (
            "Governing Law",
            "This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware, without giving effect to any principles of conflicts of law.",
            ["governing law", "governing laws", "applicable law", "applicable laws"],
        ),
        (
            "Confidentiality",
            "Each party agrees to maintain in strict confidence and not to disclose to any third party any Confidential Information received from the other party.",
            ["confidentiality", "confidential information"],
        ),
        (
            "Termination",
            "Either party may terminate this Agreement without cause upon thirty (30) days prior written notice to the other party.",
            ["termination", "terminations", "term", "terms"],
        ),
        (
            "Indemnification",
            "Supplier shall indemnify, defend, and hold harmless Customer and its officers, directors, and employees from and against any third-party claims, damages, or liabilities.",
            ["indemnification", "indemnity", "indemnifications"],
        ),
        (
            "Payment / Fees",
            "Customer shall pay all undisputed fees and invoices within thirty (30) days of receipt of invoice. Late payments shall accrue interest at 1.5% per month.",
            ["payment", "payments", "fees", "fee"],
        ),
    ]

    print("\n" + "=" * 60)
    print("Running sanity checks on 5 obvious contract clauses...")
    print("=" * 60)

    passed_checks = 0
    with torch.inference_mode():
        for category, text, expected_keywords in test_cases:
            inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            logits = model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)[0]
            top_k_indices = torch.topk(probs, k=3).indices.tolist()

            predicted_idx = top_k_indices[0]
            predicted_label = id2label[predicted_idx]
            confidence = probs[predicted_idx].item()

            top_3 = [(id2label[idx], probs[idx].item()) for idx in top_k_indices]

            matches_expected = any(kw in predicted_label.lower() for kw in expected_keywords)
            status = "PASS" if matches_expected else "FAIL"
            if matches_expected:
                passed_checks += 1

            print(f"\nClause [{category}]:")
            print(f"  Snippet: {text[:90]}...")
            print(f"  Predicted Label: {predicted_label} (Confidence: {confidence:.2%}) -> {status}")
            print("  Top 3:")
            for rank, (lbl, conf) in enumerate(top_3, 1):
                print(f"    {rank}. {lbl}: {conf:.2%}")

    print("\n" + "=" * 60)
    print(f"Sanity Check Summary: {passed_checks}/{len(test_cases)} passed.")
    print("=" * 60)

    if passed_checks < 4:
        print(f"ERROR: Sanity checks failed! Only {passed_checks}/{len(test_cases)} passed.", file=sys.stderr)
        return 1

    print("\nSUCCESS: AmitTewari/LegalPro-BERT-base verified successfully with 100 LEDGAR labels.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
