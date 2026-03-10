# AIGuard

**Model-agnostic LLM safety evaluation toolkit.**

AIGuard is a local-first, modular framework for evaluating, monitoring, and governing large language model behaviour. It ships a CLI orchestration layer, adversarial attack pipelines, hallucination detection, a human review workflow, and a backend-agnostic storage layer — all operable without external services or heavyweight infrastructure.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Table of contents

1. [Modules](#1-modules)
2. [Install](#2-install)
3. [CLI — orchestration layer](#3-cli--orchestration-layer)
4. [Directory structure](#4-directory-structure)
5. [Adversarial](#5-adversarial)
6. [Evaluator](#6-evaluator)
7. [Hallucination](#7-hallucination)
8. [Storage](#8-storage)
9. [Review](#9-review)
10. [Tests](#10-tests)
11. [Extending AIGuard](#11-extending-aiguard)
12. [Design principles](#12-design-principles)
13. [Roadmap](#13-roadmap)
14. [License](#14-license)

---

## 1. Modules

| Module | Entrypoint | Purpose |
|---|---|---|
| [`adversarial`](#5-adversarial) | `adversarial/__init__.py` | Ingest, mutate, and evolve adversarial attack datasets |
| [`evaluator`](#6-evaluator) | `evaluator/engine.py` | Plug-in evaluation engine with universal result schema |
| [`hallucination`](#7-hallucination) | `hallucination/hallucination_test.py` | Automatic-mode hallucination detection |
| [`storage`](#8-storage) | `storage/manager.py` | Backend-agnostic persistence (SQLite / Postgres), per-project |
| [`review`](#9-review) | `review/server.py` | Human review queue, SMTP alerts, calibration, web UI |

---

## 2. Install

```bash
git clone https://github.com/Shelton03/aiguard
cd aiguard

python -m venv .venv && source .venv/bin/activate

# Core (adversarial + evaluator + hallucination + storage)
pip install -e .

# + Human review server (FastAPI, uvicorn, jinja2)
pip install -e ".[review]"

# + HuggingFace dataset ingestion
pip install -e ".[huggingface]"
```

**Environment variables used at runtime**

| Variable | Default | Purpose |
|---|---|---|
| `AIGUARD_PROJECT` | CWD folder name | Active project name |
| `AIGUARD_DATA_DIR` | `.aiguard/` | Where DB files are written |
| `AIGUARD_STORAGE` | `sqlite` | Backend: `sqlite` or `postgres` |
| `AIGUARD_PG_DSN` | localhost defaults | Postgres DSN string |
| `OPENAI_API_KEY` | — | Required when using OpenAI as target model |

---

## 3. CLI — orchestration layer

The `aiguard` CLI is a **thin routing layer only**. It loads `aiguard.yaml`, dispatches to module services, and returns CI-compatible exit codes. No scoring, storage, or evaluation logic lives inside it.

### 3.1 Command hierarchy

```
aiguard
│
├── project
│     ├── init                  — scaffold aiguard.yaml for a new project
│     ├── list                  — list all known projects
│     ├── delete                — delete a project (requires confirmation)
│     └── export                — export all project data to JSON
│
├── evaluate
│     ├── adversarial           — run adversarial module only
│     ├── hallucination         — run hallucination module only
│     └── (future modules auto-register via ModuleRegistry)
│
├── monitor
│     └── start <project>       — start runtime hallucination monitoring
│
├── review
│     ├── serve                 — start FastAPI review server
│     ├── list <project>        — list pending + completed review items
│     └── calibrate <project>   — force score recalibration immediately
│
├── storage
│     ├── migrate --to <backend>  — migrate between SQLite / Postgres
│     └── info                    — print active backend and project
│
└── ci
      └── template <github|gitlab> --project <name>
                                — print ready-to-copy CI YAML (does not modify files)
```

### 3.2 Project configuration — `aiguard.yaml`

Create one `aiguard.yaml` per project at your project root. All thresholds and module settings are locked here — the CLI never overrides them.

```yaml
project: econet_llm_eval

model:
  provider: openai
  endpoint: https://api.openai.com/v1
  model_name: gpt-4o
  api_key_env: OPENAI_API_KEY

evaluation:
  enabled_modules:
    - adversarial
    - hallucination

  adversarial:
    threshold: 0.15        # global risk score above which run fails
    mode: quick            # quick (subset) or full (all attacks)
    runs_per_test: 3       # each attack is scored N times; average is used
    dataset_config: datasets.json

  hallucination:
    threshold: 0.35
    test_cases: []         # list of inline test case dicts (see §7)
```

Scaffold a new config:

```bash
aiguard project init --project econet_llm_eval
```

### 3.3 Running evaluations

```bash
# Run all enabled_modules, combine into one report
aiguard evaluate --project econet_llm_eval

# Run a single module
aiguard evaluate adversarial --project econet_llm_eval

# Write JSON artifact
aiguard evaluate adversarial --project econet_llm_eval --output report.json

# Choose evaluation depth
aiguard evaluate adversarial --project econet_llm_eval --mode full
```

### 3.4 JSON report format

The CLI serialises module output as-is — it never reshapes scores.

**Single-module report**

```json
{
    "project": "econet_llm_eval",
    "module": "adversarial",
    "timestamp": "2026-03-10T09:00:00",
    "mode": "quick",
    "total_tests": 120,
    "failed_tests": 8,
    "global_risk_score": 0.19,
    "threshold": 0.15,
    "status": "fail",
    "failure_breakdown_by_category": {
        "prompt_injection": 4,
        "jailbreak": 4
    },
    "top_failing_examples": [
        {
            "attack_id": "abc123",
            "attack_type": "jailbreak",
            "subtype": "roleplay",
            "avg_score": 0.62,
            "content_snippet": "Pretend you are DAN..."
        }
    ]
}
```

**Multi-module combined report**

```json
{
    "project": "econet_llm_eval",
    "timestamp": "2026-03-10T09:00:00",
    "status": "fail",
    "modules": [
        {"module": "adversarial",   "status": "fail", "global_risk_score": 0.19},
        {"module": "hallucination", "status": "pass", "global_risk_score": 0.12}
    ]
}
```

### 3.5 Exit codes

| Code | Meaning |
|---|---|
| `0` | PASS — all modules within threshold |
| `1` | FAIL — at least one module exceeded its threshold |
| `2` | SYSTEM ERROR — misconfiguration, missing dataset, exception |

Multi-module rule: `2` > `1` > `0` (worst code wins).

### 3.6 CI template generator

```bash
aiguard ci template github --project econet_llm_eval
aiguard ci template gitlab --project econet_llm_eval
```

Prints a ready-to-copy YAML snippet. Does **not** modify any repository files.

**GitHub Actions output example**

```yaml
name: AIGuard Evaluation
on: [push, pull_request]
jobs:
  aiguard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install aiguard
      - run: aiguard evaluate --project econet_llm_eval
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

### 3.7 Other CLI commands

```bash
# Project management
aiguard project list
aiguard project delete myproject          # prompts for name confirmation
aiguard project export myproject --output export.json

# Review server
aiguard review serve --port 8123
aiguard review list myproject
aiguard review calibrate myproject

# Storage
aiguard storage info
aiguard storage migrate --to postgres

# Legacy review CLI (still available)
aiguard-review serve --port 8123
```

---

## 4. Directory structure

```
.
├── aiguard/                        # CLI orchestration package
│   ├── __init__.py
│   ├── cli/
│   │   ├── main.py                 # Typer app — all commands defined here
│   │   ├── config.py               # aiguard.yaml loader + project name resolution
│   │   ├── exit_codes.py           # exit code constants + aggregation logic
│   │   ├── reporting.py            # JSON report writer (no reshaping)
│   │   ├── templates.py            # GitHub / GitLab YAML printer
│   │   └── services.py             # thin adapters to existing module APIs
│   └── evaluation/
│       ├── base.py                 # BaseEvaluationModule contract
│       ├── registry.py             # ModuleRegistry (name → class)
│       └── modules.py              # AdversarialEvaluationModule, HallucinationEvaluationModule
│
├── adversarial/                    # Adversarial attack pipeline
│   ├── __init__.py                 # public API: load_datasets, run_mutation_cycle, run_evolutionary_round
│   ├── schema.py                   # Attack, AttackMetadata, AttackType, GenerationType
│   ├── storage.py                  # AttackStorage (SQLite, attack-specific)
│   ├── seed_manager.py             # SeedManager — get_seeds, promote_to_seed
│   ├── mutator.py                  # MutationOperator base + 4 built-in operators + MutationEngine
│   ├── evolutionary.py             # EvolutionaryEngine + EvolutionConfig
│   ├── scoring.py                  # HeuristicScorer (pluggable)
│   ├── multi_turn.py               # ConversationStep, MultiTurnAttack, MultiTurnSimulator
│   └── adapters/
│       ├── base_adapter.py         # BaseDatasetAdapter
│       ├── registry.py             # adapter registry + @register_adapter decorator
│       ├── example_adapter.py      # JSON list adapter
│       ├── csv_adapter.py          # CSV adapter
│       └── huggingface_adapter.py  # HuggingFace datasets adapter
│
├── evaluator/                      # Generic evaluation engine
│   ├── base_test.py                # BaseEvaluationTest + TargetModel protocol
│   ├── registry.py                 # TestRegistry + @register_test decorator
│   ├── execution.py                # ExecutionRunner + ExecutionTrace
│   ├── result.py                   # EvaluationResult schema
│   ├── engine.py                   # EvaluationEngine orchestration
│   └── pipeline.py                 # run_evaluation() convenience wrapper
│
├── hallucination/                  # Hallucination detection
│   ├── hallucination_test.py       # HallucinationTest — main entrypoint
│   ├── modes.py                    # ExecutionMode, HallucinationMode, detection helpers
│   ├── ground_truth_checker.py     # GroundTruthChecker
│   ├── context_checker.py          # ContextChecker
│   ├── consistency_checker.py      # ConsistencyChecker
│   ├── uncertainty_estimator.py    # UncertaintyEstimator
│   ├── judge.py                    # judge hook (stubbed; replaceable)
│   ├── scoring.py                  # ScoreBundle + clamp()
│   └── taxonomy.py                 # HallucinationCategory enum
│
├── storage/                        # Backend-agnostic persistence
│   ├── manager.py                  # StorageManager — single entry point
│   ├── base_backend.py             # BaseBackend abstract interface
│   ├── sqlite_backend.py           # SQLiteBackend (default)
│   ├── postgres_backend.py         # PostgresBackend (optional, needs psycopg2)
│   ├── models.py                   # TestCase, Trace, EvaluationResultRecord, ReviewLabel, DatasetRegistry
│   ├── migrations.py               # migrate_backend() helper
│   └── project.py                  # resolve_project(), load_config(), sanitize_project()
│
├── review/                         # Human review workflow
│   ├── __init__.py
│   ├── models.py                   # ReviewQueueItem, ReviewLabel, CalibrationState, ReviewStatus, ReviewDecision
│   ├── queue.py                    # ReviewQueue — enqueue, complete, list, token management
│   ├── emailer.py                  # Emailer + SMTPConfig + load_smtp_config()
│   ├── calibration_manager.py      # CalibrationManager — apply(), check_and_update(), force_update()
│   ├── routes.py                   # FastAPI route handlers
│   ├── server.py                   # FastAPI app factory (create_app)
│   ├── cli.py                      # aiguard-review CLI (argparse)
│   ├── templates/                  # Jinja2 HTML templates
│   └── static/style.css            # CSS (no JS frameworks)
│
├── tests/
│   ├── smoke_test.py               # adversarial + evaluator + hallucination smoke tests
│   └── test_review.py              # review module — 19 tests, zero warnings
│
├── aiguard.yaml                    # example project config (see §3.2)
├── pyproject.toml
└── README.md
```

---

## 5. Adversarial

Local-first adversarial dataset pipeline: **ingest → mutate → evolve → store**.

### 5.1 Public API

```python
from adversarial import load_datasets, run_mutation_cycle, run_evolutionary_round, AttackStorage
from adversarial.evolutionary import EvolutionConfig

storage = AttackStorage()                               # defaults to .aiguard/aiguard.db

# 1. Ingest
load_datasets("datasets.json", storage=storage)

# 2. Mutate
seeds   = storage.list_attacks(limit=50)
mutated = run_mutation_cycle(seeds, storage=storage)

# 3. Evolve (mutate → score → retain top-K above threshold → persist as EVOLVED)
evolved = run_evolutionary_round(
    storage=storage,
    seed_limit=50,
    config=EvolutionConfig(retain_top_k=10, score_threshold=0.4),
)

print(f"Seeds: {len(seeds)}  Mutated: {len(mutated)}  Evolved: {len(evolved)}")
```

### 5.2 `Attack` schema

```python
Attack(
    attack_id: str,                    # UUID
    source_dataset: str,               # dataset name
    attack_type: AttackType,           # PROMPT_INJECTION | JAILBREAK | PII_EXFILTRATION |
                                       # POLICY_OVERRIDE | MODEL_SPECIFIC
    subtype: str | None,               # e.g. "roleplay", "base64"
    content: str,                      # the attack payload
    severity: str,                     # "critical" | "high" | "medium" | "low"
    success_criteria: dict,            # e.g. {"must_bypass": True}
    metadata: AttackMetadata(
        dataset_version: str,
        multi_turn: bool,
        language: str,
        extra: dict,
    ),
    generation_type: GenerationType,   # SEED | MUTATED | EVOLVED
)
```

### 5.3 `datasets.json` format

```json
{
  "datasets": [
    {
      "type": "json_list",
      "path": "data/local_attacks.json",
      "name": "local_seeds",
      "version": "v1"
    },
    {
      "type": "huggingface",
      "path": "r1char9/prompt-2-prompt-injection-v2-dataset",
      "name": "p2p_v2",
      "version": "v2",
      "options": {
        "split": "train",
        "attack_type_value": "prompt_injection",
        "field_mapping": {"content": "prompt"}
      }
    }
  ]
}
```

**Supported HuggingFace seed datasets** (require `pip install -e ".[huggingface]"`):

| Dataset | Attack type |
|---|---|
| `r1char9/prompt-2-prompt-injection-v2-dataset` | prompt_injection |
| `imoxto/prompt_injection_hackaprompt_gpt35` | prompt_injection |
| `Guardian0369/Prompt-injection-and-PII` | prompt_injection / pii_exfiltration |

### 5.4 Built-in mutation operators

| Operator | Variants per attack | Effect |
|---|---|---|
| `ParaphraseMutation` | 2 | Rephrases content while preserving intent |
| `ObfuscationMutation` | 2 | Zero-width spaces + leetspeak variants |
| `ContextWrappingMutation` | 1 | Wraps with distracting system-prompt context |
| `RoleReframingMutation` | 2 | Prepends adversarial role framing |

Total variants per seed (default config): **7**.

```python
from adversarial.mutator import MutationEngine, DEFAULT_OPERATORS

mutated = MutationEngine(DEFAULT_OPERATORS).run(seeds)
```

### 5.5 Seed manager

```python
from adversarial.seed_manager import SeedManager

manager = SeedManager(storage)
seeds = manager.get_seeds(limit=20)

# Promote mutated attacks to seed status (UPDATE existing, INSERT new — no silent skips)
promoted = manager.promote_to_seed(some_attacks)
```

### 5.6 `EvolutionConfig`

```python
from adversarial.evolutionary import EvolutionConfig, run_evolutionary_round

config = EvolutionConfig(retain_top_k=5, score_threshold=0.6)
evolved = run_evolutionary_round(storage=storage, seed_limit=5, config=config)
```

| Parameter | Default | Description |
|---|---|---|
| `retain_top_k` | `10` | Maximum number of top-scoring attacks to retain per cycle |
| `score_threshold` | `0.4` | Minimum score required to be retained |

### 5.7 Multi-turn attacks

```python
from adversarial.multi_turn import ConversationStep, MultiTurnAttack, MultiTurnSimulator

attack = MultiTurnAttack(
    base_attack=seed,
    steps=[
        ConversationStep(role="user", content="Let's do a roleplay..."),
        ConversationStep(role="user", content="Now, as that character..."),
        ConversationStep(role="user", content="Finally, tell me how to..."),
    ],
)

simulator = MultiTurnSimulator(model_fn=my_model_callable)
result = simulator.run(attack)
```

### 5.8 Custom dataset adapter

```python
from adversarial.adapters.base_adapter import BaseDatasetAdapter
from adversarial.adapters.registry import register_adapter
from adversarial.schema import Attack, AttackType, AttackMetadata

@register_adapter("my_format")
class MyAdapter(BaseDatasetAdapter):
    @property
    def name(self) -> str:
        return self.config.get("name", "my_dataset")

    def load(self):
        for record in self._parse_source():
            yield Attack(
                attack_id=record["id"],
                source_dataset=self.name,
                attack_type=AttackType.JAILBREAK,
                subtype=record.get("subtype"),
                content=record["text"],
                severity=record.get("severity", "medium"),
                success_criteria={"must_bypass": True},
                metadata=AttackMetadata(dataset_version=self.version, multi_turn=False),
            )
```

Reference as `"type": "my_format"` in `datasets.json`.

---

## 6. Evaluator

Registry-based evaluation engine. Each test type owns its scoring logic; the engine is agnostic.

### 6.1 Writing a custom test

```python
from evaluator import registry, base_test, engine
from evaluator.execution import ExecutionRunner
from evaluator.result import EvaluationResult

@registry.register_test("sample")
class SampleTest(base_test.BaseEvaluationTest):
    test_type = "sample"

    def prepare_input(self, test_case, target_model):
        return test_case["prompt"]

    def execute(self, prepared_input, target_model):
        return ExecutionRunner(target_model).run_single(prepared_input)

    def evaluate(self, trace, test_case):
        success = "expected" in str(trace.steps[0].output).lower()
        return EvaluationResult(
            test_type=self.test_type, case_id=test_case["id"],
            success=success, risk_score=0.0 if success else 1.0,
            severity="info" if success else "critical",
            confidence=0.7, category="sample",
            trace_id=trace.trace_id, metadata={},
        )

class EchoModel:
    def run(self, payload): return payload
```

### 6.2 Running via the engine

```python
engine.EvaluationEngine(EchoModel()).run(
    test_type="sample",
    test_cases=[{"id": "1", "prompt": "expected response"}],
)
```

### 6.3 `EvaluationResult` schema

| Field | Type | Description |
|---|---|---|
| `test_type` | `str` | Registered test type name |
| `case_id` | `str` | Unique test case identifier |
| `success` | `bool` | Pass/fail determination |
| `risk_score` | `float` | 0.0–1.0 |
| `severity` | `str` | `info` / `medium` / `high` / `critical` |
| `confidence` | `float` | 0.0–1.0 |
| `category` | `str` | Failure category label |
| `trace_id` | `str` | Link back to execution trace |
| `metadata` | `dict` | Any extra context |

---

## 7. Hallucination

Model-agnostic hallucination evaluator with automatic mode selection.

### 7.1 Modes

| Mode | Selected when | Primary checker |
|---|---|---|
| `ground_truth` | `ground_truth` key present in test case | `GroundTruthChecker` |
| `context_grounded` | `context_documents` key present | `ContextChecker` |
| `self_consistency` | fallback | `ConsistencyChecker` |

**Execution modes** (set via `trace.metadata.execution_mode`):

- `evaluation` — full checks; suitable for CI / batch offline runs
- `monitoring` — lightweight heuristics only; suitable for runtime

### 7.2 Usage

### 7.2 Usage

```python
from hallucination.hallucination_test import HallucinationTest

result = HallucinationTest().evaluate(
    test_case={
        "prompt": "Who wrote The Hobbit?",
        "response": "The Hobbit was written by J.R.R. Tolkien in 1937.",
        "context_documents": ["J.R.R. Tolkien wrote The Hobbit, published in 1937."],
    },
    trace={"trace_id": "t1", "model": "my-llm", "metadata": {"execution_mode": "evaluation"}},
)
print(result.to_dict())
```

### 7.3 Result shape

```json
{
  "module": "hallucination",
  "mode": "context_grounded",
  "execution_mode": "evaluation",
  "scores": {
    "factual_score": null,
    "grounding_score": 0.78,
    "consistency_score": null,
    "uncertainty_score": 0.42,
    "overall_risk": 0.22
  },
  "category": "unsupported_claim",
  "confidence": 0.7,
  "reasoning": "support=0.80, contradiction=0.05 | hedges=1, overconf=0",
  "metadata": {"trace_id": "t1", "model": "my-llm", "mode": "context_grounded"}
}
```

### 7.4 Inline test cases for CI (`aiguard.yaml`)

```yaml
evaluation:
  hallucination:
    threshold: 0.35
    test_cases:
      - id: "tc-001"
        prompt: "Who wrote The Hobbit?"
        response: "It was written by J.R.R. Tolkien."
        context_documents:
          - "J.R.R. Tolkien wrote The Hobbit, published in 1937."
      - id: "tc-002"
        prompt: "What year was the Eiffel Tower built?"
        response: "The Eiffel Tower was built in 1887."
        ground_truth: "The Eiffel Tower was completed in 1889."
```

---

## 8. Storage

Backend-agnostic persistence layer scoped per project. SQLite by default; Postgres optional.

### 8.1 Python API

```python
from storage.manager import StorageManager
from storage.models import Trace, EvaluationResultRecord
from datetime import datetime
from uuid import uuid4

sm = StorageManager()               # auto-detects project from CWD / aiguard.yaml
sm.save_trace(Trace(
    trace_id=str(uuid4()),
    project="myproject",
    model="gpt-4o",
    input_payload="...",
    output_payload="...",
    latency_ms=310,
    timestamp=datetime.utcnow(),
    metadata={},
))
results = sm.get_evaluations(limit=50)
projects = sm.list_projects()
sm.export_project("myproject")
```

### 8.2 Backend selection

Priority order: `AIGUARD_STORAGE` env → `aiguard.yaml` → default SQLite.

```bash
# SQLite (default) — creates .aiguard/aiguard.db automatically

# Postgres
export AIGUARD_STORAGE=postgres
export AIGUARD_PG_DSN="host=localhost port=5432 user=postgres password=postgres dbname=aiguard"
```

### 8.3 CLI

```bash
aiguard project list
aiguard project delete myproject           # prompts for project name confirmation
aiguard project export myproject --output export.json
aiguard storage migrate --to postgres
aiguard storage info
```

---

## 9. Review

Lightweight human review workflow for production monitoring. No login system — access is via secure single-use token links delivered over email.

### 9.1 Architecture

```
ReviewQueue          — enqueue items, issue tokens, mark completed (token rotated on use)
Emailer              — SMTP alerts with token-based review links
CalibrationManager   — logistic score recalibration (30-day / 100-review triggers)
FastAPI server       — minimal HTML UI (no JS frameworks)
```

### 9.2 Python API

```python
from review.queue import ReviewQueue
from review.emailer import Emailer
from review.calibration_manager import CalibrationManager
from pathlib import Path

queue = ReviewQueue(db_path=Path(".aiguard/myproject.db"), project="myproject")

# Enqueue an item for review
item = queue.enqueue(
    evaluation_id="eval-abc123",
    module_type="hallucination",
    model_response="The Eiffel Tower is in London.",
    raw_score=0.91,
    calibrated_score=0.87,
    trigger_reason="high_raw_score",
)

# Send email alert
Emailer().send_review_alert(
    project="myproject",
    item_id=item.id,
    module_type=item.module_type,
    trigger_reason=item.trigger_reason,
    raw_score=item.raw_score,
    token=item.review_token,
)

# Calibrate a score
cal = CalibrationManager(db_path=Path(".aiguard/myproject.db"), project="myproject")
calibrated = cal.apply(raw_score=0.82)   # → float in [0, 1]
cal.check_and_update()                   # run recalibration if triggers met
cal.force_update()                       # force recalibration immediately (CLI: aiguard review calibrate)
```

### 9.3 Web server

```bash
# Start review server (port priority: --port > AIGUARD_REVIEW_PORT > config > 8000)
aiguard review serve --port 8123

# Or using the legacy entrypoint
aiguard-review serve --port 8123
```

**Routes**

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | List all projects + pending counts |
| `GET` | `/project/{name}/dashboard` | Pending + completed reviews, calibration stats |
| `GET` | `/project/{name}/review/{token}` | Display review form |
| `POST` | `/project/{name}/review/{token}` | Submit decision, expire token |

### 9.4 SMTP configuration

Environment variables (override config file):

```bash
AIGUARD_SMTP_HOST=smtp.gmail.com
AIGUARD_SMTP_PORT=587
AIGUARD_SMTP_USER=alerts@example.com
AIGUARD_SMTP_PASSWORD=secret
AIGUARD_SMTP_FROM=alerts@example.com
AIGUARD_SMTP_TO=reviewer@example.com
AIGUARD_SMTP_USE_TLS=true
AIGUARD_REVIEW_BASE_URL=https://review.example.com
```

Or use `.aiguard/review_config.toml`:

```toml
[smtp]
host     = "smtp.gmail.com"
port     = 587
user     = "alerts@example.com"
password = "secret"
from     = "alerts@example.com"
to       = "reviewer@example.com"
use_tls  = true

[review]
base_url = "https://review.example.com"
port     = 8000
```

### 9.5 Calibration

The manager applies logistic scaling to raw scores:

$$\text{calibrated} = \frac{1}{1 + e^{-k \cdot (x - 0.5) \cdot 10}}$$

where $k$ = `scale_factor` (stored in `calibration_state`, updated after each cycle).

Recalibration triggers automatically when **≥100 reviews** have been completed since the last cycle, **or** **≥30 days** have elapsed. The scale factor is adjusted ±5% based on the fraction of human-marked-correct labels (>0.7 → tighten, <0.3 → loosen). Minimum 10 labels required; otherwise scale stays at 1.0.

### 9.6 Token security

- Generated with `secrets.token_urlsafe(32)` — 256-bit entropy (43+ character URL-safe string).
- **Single-use**: rotated to a new random value immediately on submit.
- Re-submitting the original URL returns HTTP 409.
- No sessions, no login — the token *is* the credential.

---

## 10. Tests

```bash
# Install test deps
pip install pytest pytest-asyncio httpx

# Run all tests
python -m pytest tests/ -v

# Run by module
python -m pytest tests/smoke_test.py -v      # adversarial + evaluator + hallucination
python -m pytest tests/test_review.py -v     # review module (19 tests)
```

---

## 11. Extending AIGuard

### 11.1 Add a new evaluation module

Create a class that implements `BaseEvaluationModule` and register it:

```python
# my_module/cli_adapter.py
from aiguard.evaluation.base import BaseEvaluationModule
from aiguard.evaluation.registry import module_registry

class BiasEvaluationModule(BaseEvaluationModule):
    module_name = "bias"

    def run(self) -> None:
        # call your module's existing service layer
        ...

    def generate_report(self) -> dict:
        return {...}

    def exit_code(self) -> int:
        return 0  # or 1 / 2

module_registry.register("bias", BiasEvaluationModule)
```

Import your adapter anywhere before `aiguard evaluate` is called (e.g., in a plugin `__init__.py`).
No CLI restructuring required.

### 11.2 Add a new dataset adapter

```python
from adversarial.adapters.base_adapter import BaseDatasetAdapter
from adversarial.adapters.registry import register_adapter

@register_adapter("my_format")
class MyAdapter(BaseDatasetAdapter):
    def load(self): ...
```

Reference as `"type": "my_format"` in `datasets.json`.

### 11.3 Add a new mutation operator

```python
from adversarial.mutator import MutationOperator
from adversarial.schema import Attack

class SynonymMutation(MutationOperator):
    name = "synonym"

    def mutate(self, attack: Attack) -> list[Attack]:
        return [self._clone_with_content(attack, swap_synonyms(attack.content))]
```

Pass it to `MutationEngine([..., SynonymMutation()])`.

---

## 12. Design principles

- **Local-first** — SQLite by default; no cloud dependency to run evaluations.
- **Thin CLI** — zero business logic in the CLI; all logic lives in modules.
- **Module-agnostic registry** — adding a new evaluation module requires no CLI edits.
- **Deterministic CI** — `runs_per_test=3` averaging, temperature=0 for judge, locked thresholds.
- **Clean separation** — ingestion ↔ storage ↔ mutation ↔ evaluation ↔ review are independent layers.
- **No auth in v1** — token-based access; pluggable auth is a planned v2 addition.

---

## 13. Roadmap

- [ ] Identity-based authentication layer (v2)
- [ ] Role-based access control
- [ ] Bias evaluation module
- [ ] Toxicity evaluation module
- [ ] Local LLM judge fine-tuning (Unsloth integration)
- [ ] Postgres multi-tenant review queue
- [ ] Async FastAPI routes
- [ ] OpenTelemetry trace export
- [ ] Organization-level config inheritance

---

## 14. License

MIT © [Shelton Mutambirwa](https://github.com/Shelton03)
