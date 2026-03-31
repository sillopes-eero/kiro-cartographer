"""Shared fixtures for Cartographer Power tests."""

from pathlib import Path

import pytest


POWER_DIR = Path(__file__).resolve().parent.parent / "cartographer-power"


def read_text(path: Path) -> str:
    """Read a file and return its content as a string."""
    return path.read_text(encoding="utf-8")


@pytest.fixture
def power_dir() -> Path:
    """Return the Path to the cartographer-power/ directory."""
    return POWER_DIR


@pytest.fixture
def steering_dir(power_dir: Path) -> Path:
    """Return the Path to cartographer-power/steering/."""
    return power_dir / "steering"


@pytest.fixture
def scripts_dir(power_dir: Path) -> Path:
    """Return the Path to cartographer-power/scripts/."""
    return power_dir / "scripts"


@pytest.fixture
def power_files(power_dir: Path) -> dict[str, str]:
    """Return a dict of all text files in the Power directory (relative path -> content)."""
    text_extensions = {
        ".md", ".py", ".txt", ".yaml", ".yml", ".json", ".toml", ".cfg", ".ini",
    }
    files: dict[str, str] = {}
    for path in power_dir.rglob("*"):
        if path.is_file() and path.suffix in text_extensions:
            try:
                content = read_text(path)
                rel = str(path.relative_to(power_dir))
                files[rel] = content
            except (UnicodeDecodeError, PermissionError):
                continue
    return files
