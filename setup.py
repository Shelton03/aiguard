"""setup.py — used only as a build hook to generate the bundled dataset.

`python -m build` calls this via setuptools. The actual metadata lives in
pyproject.toml; this file adds a single responsibility: run the dataset
build script before setuptools copies package data into the wheel.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py


class BuildPyWithDataset(_build_py):
    """Subclass of build_py that generates the default dataset JSONL first."""

    def run(self) -> None:
        script = Path(__file__).parent / "adversarial" / "data" / "build_default_dataset.py"
        out = Path(__file__).parent / "adversarial" / "data" / "default_adversarial_dataset.jsonl"

        if not out.exists():
            print(
                f"[aiguard-safety] Generating bundled adversarial dataset — this may take a minute…",
                flush=True,
            )
            result = subprocess.run(
                [sys.executable, str(script)],
                check=False,
            )
            if result.returncode != 0:
                print(
                    "[aiguard-safety] WARNING: dataset generation failed "
                    "(network access required). Building without default dataset.",
                    flush=True,
                )
        else:
            print(
                f"[aiguard-safety] Using cached dataset at {out} ({out.stat().st_size // 1024 // 1024} MB)",
                flush=True,
            )

        super().run()


setup(
    cmdclass={"build_py": BuildPyWithDataset},
)
