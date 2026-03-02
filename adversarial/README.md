# AIGuard Adversarial Module

Local-first, extensible adversarial evaluation layer for LLM governance. This module ingests adversarial datasets, normalizes them to a canonical schema, stores them in SQLite, mutates/evolves attacks, and supports multi-turn simulations. No external services or heavyweight infra required.

## At a glance
- **Canonical schema**: Consistent `Attack` contract across ingestion, mutation, storage.
- **Adapters**: Registry-based dataset loaders (JSON/CSV/HF/etc.) that normalize to the schema.
- **Storage**: SQLite (`.aiguard/aiguard.db`) with dataset/version tracking and JSON fields.
- **Mutation engine**: Operator pattern (paraphrase, obfuscation, context wrapping, role reframing).
- **Evolutionary engine**: Deterministic loop: mutate → score → retain top-K → persist as `evolved`.
- **Multi-turn support**: Conversation steps and simulator for staged attacks.
- **Public API**: `load_datasets`, `run_mutation_cycle`, `run_evolutionary_round`.

## Install / setup
This package is standard-library only. Ensure the project root is on `PYTHONPATH` or install the package locally.

```bash
# from project root
python -m pip install -e .  # if you later package this module
```

By default, SQLite lives at `.aiguard/aiguard.db` (created on first use).

## Directory structure
```
adversarial/
├── __init__.py            # public API surface
├── schema.py              # canonical Attack schema & enums
├── storage.py             # SQLite persistence
├── seed_manager.py        # seed retrieval/promotion
├── mutator.py             # mutation operators + engine
├── evolutionary.py        # evolutionary loop
├── scoring.py             # pluggable scoring (heuristic example)
├── multi_turn.py          # multi-turn attack representation/simulation
└── adapters/
    ├── base_adapter.py    # abstract adapter contract
    ├── registry.py        # adapter registry + decorator
    └── example_adapter.py # JSON list adapter example
evaluator/
├── base_test.py          # BaseEvaluationTest and TargetModel protocol
├── registry.py           # registry pattern for tests
├── execution.py          # ExecutionRunner and ExecutionTrace
├── result.py             # EvaluationResult schema
├── engine.py             # EvaluationEngine orchestration
└── pipeline.py           # Convenience entrypoints
```

## Canonical schema
`Attack` is the internal contract:

```python
Attack(
    attack_id: str,
    source_dataset: str,
    attack_type: AttackType,           # prompt_injection, jailbreak, pii_exfiltration, policy_override, etc.
    subtype: str | None,
    content: str,
    severity: str,
    success_criteria: dict,            # structured pass/fail signals
    metadata: AttackMetadata,          # dataset_version, multi_turn, language, extra
    generation_type: GenerationType,   # seed, mutated, evolved, runtime_discovered
    created_at: datetime,
)
```

## Quickstart
Create a dataset config and load, mutate, evolve attacks.

`datasets.json`
```json
{
  "datasets": [
    {"type": "json_list", "path": "data/attacks.json", "name": "my_seeds", "version": "v1"}
  ]
}
```
## Prompt-injection seed datasets (requested)
The following HuggingFace datasets can be ingested as seeds via the `huggingface` adapter. Ensure `pip install datasets` first.

- `r1char9/prompt-2-prompt-injection-v2-dataset`
- `imoxto/prompt_injection_hackaprompt_gpt35`
- `Guardian0369/Prompt-injection-and-PII`

Example `datasets.json` using these as initial sources:
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
        {
            "type": "huggingface",
            "path": "imoxto/prompt_injection_hackaprompt_gpt35",
            "name": "hackaprompt_gpt35",
            "version": "v1",
            "options": {
                "split": "train",
                "attack_type_value": "prompt_injection",
                "field_mapping": {"content": "prompt"}
            }
        },
        {
            "type": "huggingface",
            "path": "Guardian0369/Prompt-injection-and-PII",
            "name": "prompt_injection_pii",
            "version": "v1",
            "options": {
                "split": "train",
                "attack_type_value": "prompt_injection",
                "field_mapping": {"content": "prompt"}
            }
        }
    ]
}
```
If a dataset uses different field names, adjust `field_mapping` accordingly.

## Evaluator module (overview)
An extensible, model-agnostic evaluation engine that treats each test type as a plug-in. Core pieces:
- `BaseEvaluationTest` defines `prepare_input`, `execute`, `evaluate`—tests own their scoring.
- `TargetModel` protocol: any provider wrapper implementing `run(payload)`.
- `ExecutionRunner` centralizes single/multi-turn execution and trace capture (`ExecutionTrace`).
- `EvaluationResult` is a universal result schema (test_type, case_id, success, risk_score, severity, confidence, category, trace_id, metadata).
- `EvaluationEngine` picks the registered test for `test_type`, runs cases, aggregates summary stats.
- Registry (`register_test`) allows adding new test modules without modifying the engine.

Minimal usage example (pseudo):
```python
from evaluator import engine, registry, base_test

# Define a test
@registry.register_test("sample")
class SampleTest(base_test.BaseEvaluationTest):
    test_type = "sample"
    def prepare_input(self, test_case, target_model):
        return test_case["prompt"]
    def execute(self, prepared_input, target_model):
        from evaluator.execution import ExecutionRunner
        return ExecutionRunner(target_model).run_single(prepared_input)
    def evaluate(self, trace, test_case):
        from evaluator.result import EvaluationResult
        success = "expected" in str(trace.steps[0].output).lower()
        return EvaluationResult(
            test_type=self.test_type,
            case_id=test_case["id"],
            success=success,
            risk_score=0.0 if success else 1.0,
            severity="critical" if not success else "info",
            confidence=0.7,
            category="sample",
            trace_id=trace.trace_id,
            metadata={},
        )

class EchoModel:
    def run(self, input_payload):
        return input_payload

engine.EvaluationEngine(EchoModel()).run(
    test_type="sample",
    test_cases=[{"id": "1", "prompt": "expected response"}],
)
```

`python - <<'PY'`
```python
from adversarial import (
    load_datasets, run_mutation_cycle, run_evolutionary_round,
    AttackStorage
)

storage = AttackStorage()
load_datasets("datasets.json", storage=storage)

seeds = storage.list_attacks(limit=2)
mutated = run_mutation_cycle(seeds, storage=storage)

# Run one evolutionary round over seeds
from adversarial.evolutionary import EvolutionConfig
from adversarial.scoring import HeuristicScorer

config = EvolutionConfig(retain_top_k=5, score_threshold=0.6)
evolved = run_evolutionary_round(storage=storage, seed_limit=5, config=config)

print("Seeds:", len(seeds))
print("Mutated:", len(mutated))
print("Evolved:", len(evolved))
PY
```

## Adapter pattern
Implement `BaseDatasetAdapter` and register it:

```python
from adversarial.adapters import BaseDatasetAdapter, register_adapter
from adversarial.schema import Attack, AttackType, AttackMetadata

@register_adapter("my_format")
class MyAdapter(BaseDatasetAdapter):
    @property
    def name(self) -> str:
        return self.config.get("name", "my_dataset")

    def load(self):
        # parse self.path ...
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

## Mutation engine
Operators subclass `MutationOperator` and return new `Attack` instances. Built-ins:
- `ParaphraseMutation`
- `ObfuscationMutation`
- `ContextWrappingMutation`
- `RoleReframingMutation`

Use:
```python
from adversarial.mutator import MutationEngine, DEFAULT_OPERATORS
mutated = MutationEngine(DEFAULT_OPERATORS).run(seeds)
```

## Evolutionary loop
Deterministic flow (see `evolutionary.py`): mutate seeds → score → sort → retain top-K above threshold → store as `EVOLVED`.
Configure with `EvolutionConfig(retain_top_k=..., score_threshold=...)` and plug in any scorer (`Callable[[Attack], ScoreResult]`).

## Multi-turn attacks
Represent staged attacks via `MultiTurnAttack` and `ConversationStep`; run through `MultiTurnSimulator` to step prompts while tracking completion.

## Storage
- File: `.aiguard/aiguard.db`
- Tables: `datasets` (name, version, metadata), `attacks` (canonical fields, JSON text columns, generation_type, ingestion_ts)
- Indexes: `(source_dataset, dataset_version)`, `generation_type`

## Public API (importable)
- `load_datasets(config_path, storage=None) -> int`
- `run_mutation_cycle(attacks, operators=None, storage=None) -> list[Attack]`
- `run_evolutionary_round(storage, seed_limit=None, config=EvolutionConfig()) -> list[Attack]`
- `AttackStorage` for persistence helpers

## Design principles
- Local-first, no SaaS assumptions
- Deterministic defaults; extensible operators/scorers/adapters
- Clean boundaries: ingestion ↔ storage ↔ mutation ↔ evolution ↔ simulation
- Suitable for CI/CD gating and offline evaluation
