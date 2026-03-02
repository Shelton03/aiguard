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
from .schema import Attack, GenerationType
from .seed_manager import SeedManager
from .evolutionary import EvolutionaryEngine, EvolutionConfig
from .scoring import HeuristicScorer


def load_datasets(config_path: str, storage: Optional[AttackStorage] = None) -> int:
    """Load datasets from a JSON config and persist canonical attacks.

    Config format:
    {
        "datasets": [
            {"type": "json_list", "path": "./data.json", "name": "mydata", "version": "v1", "options": {}}
        ]
    }
    """

    storage = storage or AttackStorage()
    config = json.loads(Path(config_path).read_text())
    total_inserted = 0

    for dataset_cfg in config.get("datasets", []):
        adapter_type = dataset_cfg["type"]
        path = dataset_cfg["path"]
        name = dataset_cfg.get("name", adapter_type)
        version = dataset_cfg.get("version")
        options = dataset_cfg.get("options", {})

        adapter = registry.create(adapter_type, path=path, config={"name": name, "version": version, **options})
        storage.register_dataset(name=name, version=version, metadata=options)
        inserted = storage.insert_attacks(adapter.load())
        total_inserted += inserted
    return total_inserted


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
