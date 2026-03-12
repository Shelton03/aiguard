"""Adversarial module for AIGuard: ingestion, mutation, and evolution of attacks."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from .adapters.registry import registry
from .adapters import example_adapter  # noqa: F401 ensure adapter registration
from .adapters import csv_adapter  # noqa: F401
from .adapters import huggingface_adapter  # noqa: F401
from .mutator import DEFAULT_OPERATORS, MutationEngine, MutationOperator
from .storage import AttackStorage
from .schema import Attack, GenerationType, AttackType, AttackMetadata
from uuid import uuid4
from .seed_manager import SeedManager
from .evolutionary import EvolutionaryEngine, EvolutionConfig
from .scoring import HeuristicScorer
from .data import builtin_datasets_json, resolve_builtin_path
from .data import DATA_DIR


def load_datasets(config_path: Optional[str], storage: Optional[AttackStorage] = None) -> int:
    """Load datasets from a JSON config and persist canonical attacks.

    Config format:
    {
        "datasets": [
            {"type": "json_list", "path": "./data.json", "name": "mydata", "version": "v1", "options": {}}
        ]
    }

    The special path prefix ``__builtin__/`` is resolved to the adversarial
    data directory bundled inside the installed package.
    """

    storage = storage or AttackStorage()
    if not config_path:
        # No config provided → load the bundled default dataset
        return load_default_dataset(storage=storage)
    config = json.loads(Path(config_path).read_text())
    total_inserted = 0

    for dataset_cfg in config.get("datasets", []):
        adapter_type = dataset_cfg["type"]
        path = resolve_builtin_path(dataset_cfg["path"])
        name = dataset_cfg.get("name", adapter_type)
        version = dataset_cfg.get("version")
        options = dataset_cfg.get("options", {})

        adapter = registry.create(adapter_type, path=path, config={"name": name, "version": version, **options})
        storage.register_dataset(name=name, version=version, metadata=options)
        inserted = storage.insert_attacks(adapter.load())
        total_inserted += inserted
    return total_inserted


def load_default_dataset(storage: Optional[AttackStorage] = None) -> int:
    """Load the bundled default adversarial dataset shipped with the package.

    Prefers ``adversarial/data/default_adversarial_dataset.jsonl`` (generated at
    build time from 10 HuggingFace sources).  If that file is absent (e.g. an
    editable / source install without running the build script), falls back to
    the hand-crafted ``core_attacks.json`` seed dataset.

    Returns the number of attacks inserted.
    """
    storage = storage or AttackStorage()
    data_file = Path(DATA_DIR) / "default_adversarial_dataset.jsonl"
    fallback = Path(DATA_DIR) / "core_attacks.json"

    if not data_file.exists():
        if fallback.exists():
            import warnings
            warnings.warn(
                "adversarial/data/default_adversarial_dataset.jsonl not found. "
                "This file is generated at package-build time (python -m build). "
                "Falling back to the built-in seed dataset (core_attacks.json). "
                "Run `python adversarial/data/build_default_dataset.py` to generate it locally.",
                RuntimeWarning,
                stacklevel=2,
            )
            # Load via the json_list adapter (it handles both JSON array and JSONL)
            from .adapters.example_adapter import JsonListAdapter
            adapter = JsonListAdapter(str(fallback), config={"name": "aiguard-core", "version": "builtin"})
            return storage.insert_attacks(adapter.load())
        raise FileNotFoundError(
            f"Default dataset not found at {data_file} and fallback {fallback} is also missing. "
            "Run `python adversarial/data/build_default_dataset.py` to generate the dataset."
        )

    attacks = []
    with data_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            raw_type = obj.get("attack_type", "prompt_injection")
            try:
                attack_type = AttackType(raw_type)
            except Exception:
                try:
                    attack_type = AttackType(str(raw_type))
                except Exception:
                    attack_type = AttackType.PROMPT_INJECTION

            attacks.append(
                Attack(
                    attack_id=str(obj.get("id") or uuid4()),
                    source_dataset="aiguard-default",
                    attack_type=attack_type,
                    subtype=None,
                    content=obj.get("prompt", ""),
                    severity="medium",
                    success_criteria={},
                    metadata=AttackMetadata(dataset_version="builtin"),
                    generation_type=GenerationType.SEED,
                )
            )
    return storage.insert_attacks(attacks)


def run_mutation_cycle(
    attacks: Iterable[Attack],
    operators: Optional[Sequence[MutationOperator]] = None,
    storage: Optional[AttackStorage] = None,
) -> List[Attack]:
    engine = MutationEngine(operators or DEFAULT_OPERATORS)
    mutated = engine.run(attacks)
    if storage:
        storage.insert_attacks(mutated)
    return mutated


def run_evolutionary_round(
    storage: AttackStorage,
    seed_limit: Optional[int] = None,
    config: EvolutionConfig = EvolutionConfig(),
) -> List[Attack]:
    seeds = SeedManager(storage).get_seeds(limit=seed_limit)
    mutator = MutationEngine(DEFAULT_OPERATORS)
    scorer = HeuristicScorer()
    engine = EvolutionaryEngine(storage=storage, mutator=mutator, scorer=scorer, config=config)
    return engine.run_round(seeds)


__all__ = [
    "Attack",
    "GenerationType",
    "AttackStorage",
    "load_datasets",
    "run_mutation_cycle",
    "run_evolutionary_round",
    "MutationEngine",
    "EvolutionaryEngine",
    "EvolutionConfig",
    "HeuristicScorer",
]
