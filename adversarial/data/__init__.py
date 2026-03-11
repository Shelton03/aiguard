"""Built-in adversarial datasets shipped with aiguard-safety."""
from pathlib import Path

DATA_DIR = Path(__file__).parent


def builtin_datasets_json() -> Path:
    """Return the path to the bundled datasets.json config."""
    return DATA_DIR / "datasets.json"


def resolve_builtin_path(path: str) -> str:
    """Resolve a ``__builtin__/`` path reference to an absolute file path.

    The ``datasets.json`` config uses ``__builtin__/filename`` as a portable
    way to reference files that live inside this package regardless of where
    the user has installed it.

    Example
    -------
    >>> resolve_builtin_path("__builtin__/core_attacks.json")
    '/path/to/site-packages/adversarial/data/core_attacks.json'
    """
    prefix = "__builtin__/"
    if path.startswith(prefix):
        return str(DATA_DIR / path[len(prefix):])
    return path
