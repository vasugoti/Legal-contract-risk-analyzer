import torch
import transformers
from transformers import AutoModelForSequenceClassification, AutoTokenizer

model_path = "NLP/LEDGAR_SRA"
print(f"Loading from: {model_path}")
tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
model = AutoModelForSequenceClassification.from_pretrained(model_path, local_files_only=True)
model.eval()

print(f"Model Type: {model.config.model_type}")
print(f"Num Labels: {model.config.num_labels}")
print(f"Transformers Version: {transformers.__version__}")
print(f"Torch Version: {torch.__version__}")

sentences = [
    ("a", "This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware."),
    ("b", "Either party may terminate this Agreement upon thirty (30) days prior written notice to the other party."),
    ("c", "The Company shall indemnify and hold harmless the Executive from any and all claims arising out of his employment."),
]

id2label = model.config.id2label

with torch.no_grad():
    for tag, text in sentences:
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
        outputs = model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)[0]
        top_probs, top_indices = torch.topk(probs, 3)
        print(f"\nSentence ({tag}): {text}")
        for p, idx in zip(top_probs, top_indices, strict=False):
            label_idx = idx.item()
            label_name = id2label.get(label_idx, id2label.get(str(label_idx), f"LABEL_{label_idx}"))
            print(f"  {label_name}: {p.item():.4f}")
