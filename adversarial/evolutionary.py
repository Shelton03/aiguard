"""Simple evolutionary loop for adversarial attack refinement."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, List, Sequence

from .schema import Attack, GenerationType
from .mutator import MutationEngine
from .storage import AttackStorage
from .scoring import ScoreResult


@dataclass
class EvolutionConfig:
    retain_top_k: int = 5
    score_threshold: float = 0.6


class EvolutionaryEngine:
    def __init__(
        self,
        storage: AttackStorage,
        mutator: MutationEngine,
        scorer: Callable[[Attack], ScoreResult],
        config: EvolutionConfig = EvolutionConfig(),
    ) -> None:
        self.storage = storage
        self.mutator = mutator
        self.scorer = scorer
        self.config = config

    def run_round(self, seed_attacks: Sequence[Attack]) -> List[Attack]:
        mutated = self.mutator.run(seed_attacks)
        scored: List[tuple[Attack, ScoreResult]] = []
        for attack in mutated:
            result = self.scorer(attack)
            scored.append((attack, result))

        # Deterministic ordering by score then attack_id
        scored.sort(key=lambda pair: (-pair[1].score, pair[0].attack_id))
        retained = [a for a, s in scored if s.score >= self.config.score_threshold]
        retained = retained[: self.config.retain_top_k]

        for attack in retained:
            attack.generation_type = GenerationType.EVOLVED
        if retained:
            self.storage.insert_attacks(retained)
        return retained
