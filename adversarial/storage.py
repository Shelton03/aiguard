"""Lightweight SQLite storage for adversarial attacks and datasets."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .schema import Attack, GenerationType

DB_PATH = Path(__file__).resolve().parent.parent / ".aiguard" / "aiguard.db"


class AttackStorage:
    """SQLite-backed storage for attacks and dataset metadata."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    version TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(name, version)
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS attacks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attack_id TEXT NOT NULL UNIQUE,
                    source_dataset TEXT NOT NULL,
                    dataset_version TEXT,
                    attack_type TEXT NOT NULL,
                    subtype TEXT,
                    content TEXT NOT NULL,
                    severity TEXT,
                    success_criteria TEXT,
                    metadata TEXT,
                    generation_type TEXT NOT NULL,
                    ingestion_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_attacks_dataset
                ON attacks(source_dataset, dataset_version);
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_attacks_generation
                ON attacks(generation_type);
                """
            )

    def register_dataset(self, name: str, version: Optional[str], metadata: Optional[Dict[str, Any]] = None) -> None:
        metadata_json = json.dumps(metadata or {})
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO datasets (name, version, metadata)
                VALUES (?, ?, ?);
                """,
                (name, version, metadata_json),
            )

    def insert_attacks(self, attacks: Iterable[Attack]) -> int:
        rows = [
            (
                attack.attack_id,
                attack.source_dataset,
                attack.metadata.dataset_version,
                attack.attack_type.value,
                attack.subtype,
                attack.content,
                attack.severity,
                json.dumps(attack.success_criteria),
                json.dumps(attack.metadata.to_dict()),
                attack.generation_type.value,
                datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            )
            for attack in attacks
        ]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR IGNORE INTO attacks (
                    attack_id, source_dataset, dataset_version, attack_type, subtype,
                    content, severity, success_criteria, metadata, generation_type, ingestion_ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                rows,
            )
            return conn.total_changes

    def update_generation_type(
        self, attack_ids: List[str], generation_type: GenerationType
    ) -> int:
        """Update the generation_type for a set of existing attacks by ID.

        Returns the number of rows actually updated.
        """
        if not attack_ids:
            return 0
        with self._connect() as conn:
            conn.executemany(
                "UPDATE attacks SET generation_type = ? WHERE attack_id = ?;",
                [(generation_type.value, aid) for aid in attack_ids],
            )
            return conn.total_changes

    def list_attacks(
        self,
        source_dataset: Optional[str] = None,
        generation_type: Optional[GenerationType] = None,
        limit: Optional[int] = None,
    ) -> List[Attack]:
        query = "SELECT * FROM attacks"
        clauses = []
        params: List[Any] = []
        if source_dataset:
            clauses.append("source_dataset = ?")
            params.append(source_dataset)
        if generation_type:
            clauses.append("generation_type = ?")
            params.append(generation_type.value)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY ingestion_ts DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_attack(row) for row in rows]

    def _row_to_attack(self, row: sqlite3.Row) -> Attack:
        return Attack.from_dict(
            {
                "attack_id": row["attack_id"],
                "source_dataset": row["source_dataset"],
                "attack_type": row["attack_type"],
                "subtype": row["subtype"],
                "content": row["content"],
                "severity": row["severity"],
                "success_criteria": json.loads(row["success_criteria"] or "{}"),
                "metadata": json.loads(row["metadata"] or "{}"),
                "generation_type": row["generation_type"],
                "created_at": row["ingestion_ts"],
            }
        )

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(1) FROM attacks").fetchone()[0]
