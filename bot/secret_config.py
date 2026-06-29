"""Secret loading helpers for local bot runtime.

Secrets are read from the process environment first, then from the Hermes
secrets file, then from Docker-style /run/secrets files. Values are never
printed by this module.
"""

from __future__ import annotations

import os
from pathlib import Path

SECRET_FILES = (
    Path.home() / ".hermes" / "secrets.env",
    Path("/home/hermes-workspace/.hermes/secrets.env"),
)


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
    except FileNotFoundError:
        pass
    return values


def _read_secret_file(name: str) -> str:
    for candidate in (Path("/run/secrets") / name, Path("/run/secrets") / name.lower()):
        try:
            value = candidate.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            continue
        if value:
            return value
    return ""


def get_secret(*names: str, default: str = "", required: bool = False) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value

    file_values: dict[str, str] = {}
    for path in SECRET_FILES:
        file_values.update(_read_env_file(path))

    for name in names:
        value = file_values.get(name, "").strip()
        if value:
            return value

    for name in names:
        value = _read_secret_file(name)
        if value:
            return value

    if required:
        joined = ", ".join(names)
        raise RuntimeError(f"required secret is missing: {joined}")
    return default


def get_evo_key(required: bool = True) -> str:
    return get_secret("EVO_KEY", "EVOLUTION_API_KEY", "EVO_API_KEY", required=required)
