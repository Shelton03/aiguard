#!/usr/bin/env python3
"""
Verify that installed dependencies match expected versions.

This script checks that all dependencies are within the pinned version ranges
to ensure compatibility and prevent breaking changes.

Usage:
    python verify_versions.py
"""

import sys
from importlib.metadata import version, PackageNotFoundError

# Expected version ranges
EXPECTED_VERSIONS = {
    "fastapi": ("0.115.0", "0.116.0"),
    "starlette": ("0.38.0", "0.39.0"),
    "uvicorn": ("0.29.0", "0.30.0"),
    "jinja2": ("3.1.0", "4.0.0"),
    "python-multipart": ("0.0.9", "0.1.0"),
    "typer": ("0.12.0", None),  # Only minimum version
    "pyyaml": ("6.0", None),
    "litellm": ("1.0", None),
    "datasets": ("2.16.0", None),
    "langdetect": ("1.0.9", None),
    "reportlab": ("4.0.0", None),
}


def parse_version(v: str) -> tuple:
    """Parse version string into tuple for comparison."""
    return tuple(map(int, v.split(".")))


def check_version(package: str, min_ver: str, max_ver: str | None) -> bool:
    """Check if installed version is within expected range."""
    try:
        installed = version(package)
        installed_tuple = parse_version(installed)
        min_tuple = parse_version(min_ver)
        
        # Check minimum version
        if installed_tuple < min_tuple:
            print(f"❌ {package}: {installed} (minimum: {min_ver})")
            return False
        
        # Check maximum version (if specified)
        if max_ver:
            max_tuple = parse_version(max_ver)
            if installed_tuple >= max_tuple:
                print(f"❌ {package}: {installed} (maximum: {max_ver})")
                return False
        
        print(f"✅ {package}: {installed} (✓ within range {min_ver} - {max_ver or '∞'})")
        return True
        
    except PackageNotFoundError:
        print(f"❌ {package}: NOT INSTALLED")
        return False


def main():
    """Main entry point."""
    print("=" * 60)
    print("Dependency Version Verification")
    print("=" * 60)
    print()
    
    results = []
    for package, (min_ver, max_ver) in EXPECTED_VERSIONS.items():
        max_str = max_ver if max_ver else "∞"
        print(f"Checking {package} ({min_ver} - {max_str})...")
        result = check_version(package, min_ver, max_ver)
        results.append(result)
        print()
    
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} packages OK")
    
    if all(results):
        print("✅ All dependencies are within expected version ranges!")
        print("=" * 60)
        return 0
    else:
        print("❌ Some dependencies are outside expected version ranges!")
        print("   Run 'pip install -r requirements.txt' or update pyproject.toml")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
