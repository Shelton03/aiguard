"""Build the default_adversarial_dataset.jsonl by fetching and normalizing
multiple HuggingFace datasets.

Usage:
    python adversarial/data/build_default_dataset.py

This script requires the `datasets` package and network access.
It writes `default_adversarial_dataset.jsonl` next to itself.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, List, Dict, Any, Optional

from datasets import load_dataset

ROOT = Path(__file__).parent
OUT = ROOT / "default_adversarial_dataset.jsonl"

# Provided datasets (owner/name)
DATASETS = [
    "qualifire/Qualifire-prompt-injection-benchmark",
    "S-Labs/prompt-injection-dataset",
    "dmilush/shieldlm-prompt-injection",
    "neuralchemy/Prompt-injection-dataset",
    "Mindgard/evaded-prompt-injection-and-jailbreak-samples",
    "Lshafii/Jailbreak-PromptBank",
    "darkknight25/Prompt_Injection_Benign_Prompt_Dataset",
    "ai4privacy/pii-masking-200k",
    "ai4privacy/synthetic-pii-finance",
    "bigcode/pii-detection",
]

# Datasets that are known benign or that should be skipped unless labelled
SKIP_DATASETS = {
    "darkknight25/Prompt_Injection_Benign_Prompt_Dataset",
}

# Preferred fields that may contain the prompt text
PROMPT_FIELDS = ["text", "instruction", "query", "prompt", "input", "content", "example"]

# Labels that indicate an entry is adversarial
ADVERSARIAL_LABELS = {"jailbreak", "malicious", "unsafe", "attack", "injection", "exploit", "pii", "pii_exfiltration"}
SAFE_LABELS = {"benign", "safe", "normal", "clean"}

# Map dataset -> default attack_type when not explicit
DATASET_ATTACK_TYPE: Dict[str, str] = {
    "qualifire/Qualifire-prompt-injection-benchmark": "prompt_injection",
    "S-Labs/prompt-injection-dataset": "prompt_injection",
    "dmilush/shieldlm-prompt-injection": "prompt_injection",
    "neuralchemy/Prompt-injection-dataset": "prompt_injection",
    "Mindgard/evaded-prompt-injection-and-jailbreak-samples": "jailbreak",
    "Lshafii/Jailbreak-PromptBank": "jailbreak",
    "ai4privacy/pii-masking-200k": "pii_exfiltration",
    "ai4privacy/synthetic-pii-finance": "pii_exfiltration",
    "bigcode/pii-detection": "pii_exfiltration",
}


def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def find_prompt_field(record: Dict[str, Any]) -> Optional[str]:
    for f in PROMPT_FIELDS:
        if f in record and isinstance(record[f], str) and record[f].strip():
            return record[f]
    # fallback: any string field
    for k, v in record.items():
        if isinstance(v, str) and v.strip():
            return v
    return None


def find_label(record: Dict[str, Any]) -> Optional[str]:
    for key in ("label", "labels", "category", "class", "annotation", "target"):
        if key in record:
            val = record[key]
            # numeric labels -> unknown
            if isinstance(val, (list, tuple)) and val:
                val = val[0]
            if isinstance(val, (int, float)):
                # can't infer numeric label generically
                return None
            if isinstance(val, str):
                return val.lower()
    return None


def process_dataset(ds_id: str) -> Iterable[Dict[str, Any]]:
    print(f"Loading {ds_id}...")
    try:
        ds = load_dataset(ds_id, split="train")
    except Exception:
        # try without split (some datasets have multiple files)
        ds = load_dataset(ds_id)
        # ds may be a DatasetDict
        if hasattr(ds, "values"):
            # pick first split
            ds = list(ds.values())[0]

    for rec in ds:
        rec = dict(rec)
        # skip whole dataset known benign unless labelled as malicious
        if ds_id in SKIP_DATASETS:
            label = find_label(rec)
            if not label or label in SAFE_LABELS:
                continue
        prompt = find_prompt_field(rec)
        if not prompt:
            continue
        prompt = normalize_whitespace(prompt)
        if not prompt:
            continue
        label = find_label(rec)
        if label:
            if label in SAFE_LABELS:
                continue
            # keep only if label indicates adversarial-ish
            if label not in ADVERSARIAL_LABELS:
                # unknown label, keep (conservative)
                pass
        # determine attack_type
        attack_type = DATASET_ATTACK_TYPE.get(ds_id)
        if not attack_type and label:
            # infer from label tokens
            for tok in ADVERSARIAL_LABELS:
                if tok in label:
                    attack_type = tok
                    break
        if not attack_type:
            attack_type = "prompt_injection"

        yield {"prompt": prompt, "attack_type": attack_type, "is_adversarial": True}


def build_all(out_path: Path = OUT) -> int:
    seen = set()
    count = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as out:
        for ds_id in DATASETS:
            try:
                for entry in process_dataset(ds_id):
                    p = normalize_whitespace(entry["prompt"]) if entry.get("prompt") else None
                    if not p:
                        continue
                    if p in seen:
                        continue
                    seen.add(p)
                    out.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    count += 1
            except Exception as exc:
                print(f"Warning: failed processing {ds_id}: {exc}")
                continue
    print(f"Wrote {count} unique adversarial prompts to {out_path}")
    return count


if __name__ == "__main__":
    build_all()
