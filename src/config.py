"""Incarca configurarea globala (config.yaml + variabile de mediu)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "config.yaml"

load_dotenv(ROOT_DIR / ".env")


def load_config() -> dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


CONFIG = load_config()


def env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


def path_from_root(*parts: str) -> Path:
    return ROOT_DIR.joinpath(*parts)
