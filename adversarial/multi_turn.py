"""Support for multi-turn adversarial interactions."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .schema import Attack


@dataclass
class ConversationStep:
    role: str
    content: str


@dataclass
class MultiTurnAttack:
    attack: Attack
    steps: List[ConversationStep] = field(default_factory=list)

    def to_history(self) -> List[dict]:
        return [{"role": step.role, "content": step.content} for step in self.steps]


class MultiTurnSimulator:
    """Tracks conversation state for multi-turn attacks."""

    def __init__(self, multi_attack: MultiTurnAttack) -> None:
        self.multi_attack = multi_attack
        self.current_step = 0

    def next_prompt(self, last_response: Optional[str] = None) -> Optional[str]:
        if self.current_step >= len(self.multi_attack.steps):
            return None
        prompt = self.multi_attack.steps[self.current_step].content
        self.current_step += 1
        return prompt

    def is_complete(self) -> bool:
        return self.current_step >= len(self.multi_attack.steps)
