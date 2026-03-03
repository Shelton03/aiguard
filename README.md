# AIGuard

**Model-agnostic LLM safety evaluation toolkit.**

AIGuard is a local-first, modular framework for evaluating, monitoring, and governing large language model behaviour. No external services, no heavyweight infrastructure.

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Modules

| Module | Purpose |
|---|---|
| [`adversarial`](#adversarial) | Ingest, mutate, and evolve adversarial attack datasets |
| [`evaluator`](#evaluator) | Plug-in evaluation engine with universal result schema |
| [`hallucination`](#hallucination) | Automatic mode hallucination detection |
| [`storage`](#storage) | Backend-agnostic persistence (SQLite / Postgres), per-project |
| [`review`](#review) | Human review queue, SMTP alerts, calibration manager, web UI |

---

## Install

```bash
git clone https://github.com/Shelton03/aiguard
cd aiguard

python -m venv .venv && source .venv/bin/activate

# Core (no optional deps)
pip install -e .

# With human-review server
pip install -e ".[review]"

# With HuggingFace dataset support
pip install -e ".[huggingface]"
```

---

## Directory structure

```
aiguard/
├── adversarial/
│   ├── __init__.py
│   ├── schema.py              # canonical Attack schema & enums
│   ├── storage.py             # SQLite persistence (attack-specific)
│   ├── seed_manager.py        # seed retrieval / promotion
│   ├── mutator.py             # mutation operators + engine
│   ├── evolutionary.py        # evolutionary loop
│   ├── scoring.py             # pluggable scoring (heuristic)
│   ├── multi_turn.py          # multi-turn attack representation + simulator
│   └── adapters/
│       ├── base_adapter.py
│       ├── registry.py
│       └── example_adapter.py
├── evaluator/
│   ├── base_test.py           # BaseEvaluationTest + TargetModel protocol
│   ├── registry.py            # test registry
│   ├── execution.py           # ExecutionRunner + ExecutionTrace
│   ├── result.py              # EvaluationResult schema
│   ├── engine.py              # EvaluationEngine orchestration
│   └── pipeline.py            # convenience entrypoints
├── hallucination/
│   ├── hallucination_test.py  # main entrypoint
│   ├── modes.py               # execution + hallucination mode detection
│   ├── ground_truth_checker.py
│   ├── context_checker.py
│   ├── consistency_checker.py
│   ├── uncertainty_estimator.py
│   ├── judge.py
│   ├── scoring.py
│   └── taxonomy.py
├── storage/
│   ├── manager.py             # StorageManager — single entry point
│   ├── base_backend.py        # abstract backend interface
│   ├── sqlite_backend.py      # default local persistence
│   ├── postgres_backend.py    # optional Docker-hosted Postgres
│   ├── models.py              # canonical records (TestCase, Trace, EvaluationResult…)
│   ├── migrations.py          # backend migration helpers
│   ├── project.py             # project name resolution
│   └── cli.py                 # aiguard storage CLI
├── review/
│   ├── __init__.py
│   ├── models.py              # ReviewQueueItem, ReviewLabel, CalibrationState
│   ├── queue.py               # ReviewQueue (SQLite-backed, single-use tokens)
│   ├── emailer.py             # SMTP alert emailer
│   ├── calibration_manager.py # logistic score recalibration
│   ├── routes.py              # FastAPI route handlers
│   ├── server.py              # FastAPI app factory
│   ├── cli.py                 # aiguard-review CLI
│   ├── templates/             # minimal Jinja2 HTML templates
│   └── static/                # CSS (no JS frameworks)
└── tests/
    ├── test_smoke.py
    └── test_review.py
```

---

## Adversarial

Local-first adversarial dataset pipeline: ingest → mutate → evolve.

### Quickstart

```python
from adversarial import load_datasets, run_mutation_cycle, run_evolutionary_round, AttackStorage
from adversarial.evolutionary import EvolutionConfig
from adversarial.scoring import HeuristicScorer

storage = AttackStorage()
load_datasets("datasets.json", storage=storage)

seeds   = storage.list_attacks(limit=50)
mutated = run_mutation_cycle(seeds, storage=storage)
evolved = run_evolutionary_round(storage=storage, seed_limit=50, config=EvolutionConfig(retain_top_k=10))

print(f"Seeds: {len(seeds)}  Mutated: {len(mutated)}  Evolved: {len(evolved)}")
```

### `datasets.json` format

```json
{
  "datasets": [
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
    },
    {"type": "json_list", "path": "data/local_attacks.json", "name": "local", "version": "v1"}
  ]
}
```

### Built-in mutation operators

| Operator | Effect |
|---|---|
| `ParaphraseMutation` | Rephrases content while preserving intent |
| `ObfuscationMutation` | Zero-width spaces + leetspeak variants |
| `ContextWrappingMutation` | Wraps content with distracting system-prompt context |
| `RoleReframingMutation` | Prepends adversarial role framing |

### Custom adapter

```python
from adversarial.adapters import BaseDatasetAdapter, register_adapter
from adversarial.schema import Attack, AttackType, AttackMetadata

@register_adapter("my_format")
class MyAdapter(BaseDatasetAdapter):
    @property
    def name(self) -> str:
        return self.config.get("name", "my_dataset")

    def load(self):
        yield Attack(
            attack_id="...",
            source_dataset=self.name,
            attack_type=AttackType.JAILBREAK,
            subtype="roleplay",
            content="...",
            severity="high",
            success_criteria={"must_bypass": True},
            metadata=AttackMetadata(dataset_version=self.version, multi_turn=False),
        )
```

---

## Evaluator

Registry-based evaluation engine. Each test type owns its scoring; the engine is unaware of specifics.

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

engine.EvaluationEngine(EchoModel()).run(
    test_type="sample",
    test_cases=[{"id": "1", "prompt": "expected response"}],
)
```

---

## Hallucination

Model-agnostic hallucination evaluator with automatic mode selection.

**Modes (auto-selected from inputs)**

| Mode | Trigger | Checker |
|---|---|---|
| Ground-truth | `ground_truth` present | `GroundTruthChecker` |
| Context-grounded | `context_documents` present | `ContextChecker` |
| Self-consistency | fallback | `ConsistencyChecker` |

**Execution modes**: `evaluation` (deeper checks) or `monitoring` (lightweight heuristics).

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

**Result shape**

```json
{
  "module": "hallucination",
  "mode": "context_grounded",
  "execution_mode": "evaluation",
  "scores": {
    "grounding_score": 0.78,
    "uncertainty_score": 0.42,
    "overall_risk": 0.22
  },
  "category": "unsupported_claim",
  "confidence": 0.7
}
```

---

## Storage

Backend-agnostic persistence layer scoped per project.

```python
from storage.manager import StorageManager
from storage.models import Trace, EvaluationResultRecord
from datetime import datetime
from uuid import uuid4

sm = StorageManager()               # auto-detects project from CWD
sm.save_trace(Trace(...))
results = sm.get_evaluations(limit=50)
```

**Backend selection** (priority: env → config → default SQLite)

```bash
# SQLite (default)
# creates .aiguard/aiguard.db automatically

# Postgres (Docker)
export AIGUARD_STORAGE=postgres
export AIGUARD_PG_DSN="host=localhost port=5432 user=postgres password=postgres"
```

**CLI**

```bash
aiguard project list
aiguard project delete <project>
aiguard project export <project> --output export.json
aiguard migrate --to postgres
```

---

## Review

Lightweight human review workflow for production monitoring. No login system — access is via secure single-use token links delivered over email.

### Architecture

```
ReviewQueue          — enqueue items, issue tokens, mark completed (token rotated on use)
Emailer              — SMTP alerts with token-based review links
CalibrationManager   — logistic score recalibration (30-day / 100-review triggers)
FastAPI server       — minimal HTML UI (no JS frameworks)
```

### Quickstart

```python
from review import ReviewQueue, Emailer, CalibrationManager, ReviewDecision
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
emailer = Emailer()
emailer.send_review_alert(
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
```

### Web server

```bash
# Start review server (port priority: --port > AIGUARD_REVIEW_PORT > config > 8000)
aiguard-review serve --port 8123

# Enqueue a test item from the CLI (dev helper)
aiguard-review enqueue --project myproject --module hallucination --email
```

**Routes**

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | List all projects + pending counts |
| `GET` | `/project/{name}/dashboard` | Pending + completed reviews, calibration stats |
| `GET` | `/project/{name}/review/{token}` | Display review form |
| `POST` | `/project/{name}/review/{token}` | Submit decision, expire token |

### SMTP configuration

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

### Calibration

The manager applies logistic scaling to raw scores:

$$\text{calibrated} = \frac{1}{1 + e^{-k \cdot (x - 0.5) \cdot 10}}$$

where $k$ = `scale_factor` (stored in `calibration_state`, updated after each cycle).

Recalibration triggers automatically when **≥100 reviews** have been completed since the last cycle, **or** **≥30 days** have elapsed. The scale factor is adjusted up (tighten) or down (loosen) based on the ratio of human-marked-correct to total labels.

### Token security

- Generated with `secrets.token_urlsafe(32)` — 256-bit entropy.
- **Single-use**: the token is rotated to a new random value in the database immediately when a review is submitted. Re-submitting the original URL returns HTTP 409.
- No login system in v1 — the token itself is the credential.

---

## Tests

```bash
# All tests
python -m pytest tests/ -v

# Review module only
python -m pytest tests/test_review.py -v
```

---

## Design principles

- **Local-first** — SQLite by default; no cloud dependency.
- **Modular** — each module has clean boundaries and can be used independently.
- **Extensible** — adapters, operators, scorers, and test types are all plug-in.
- **Production-grade structure** — suitable for CI/CD gating and lightweight production monitoring.
- **No auth in v1** — token-based access; pluggable auth layer is a planned v2 addition.

---

## Roadmap

- [ ] Identity-based authentication layer (v2)
- [ ] Role-based access control
- [ ] Local LLM judge fine-tuning (Unsloth integration)
- [ ] Postgres multi-tenant review queue
- [ ] Async FastAPI routes
- [ ] OpenTelemetry trace export

---

## License

MIT © [Shelton Mutambirwa](https://github.com/Shelton03)
