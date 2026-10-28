"""Load defaults and apply a project's overrides (IMPL_PLAN D12).

Defaults ship as one YAML file per section in `config/defaults/`. A project may
override any value. The override is merged into the defaults before validation,
so the result is checked as a whole: an override can't produce a weight above 1
or a weight that names a group that doesn't exist.

Merge rule: mappings merge key by key; anything else (numbers, strings, lists)
replaces the default. Replacing a list is deliberate: merging lists of type keys
would make it impossible to remove one.
"""

from collections.abc import Iterator, Mapping
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from perpetual.config.schema import Config

SECTIONS = ("evidence", "scoring", "rto_scope", "buffer", "freshness", "limits")


class ConfigError(ValueError):
    """A defaults file or project override can't be read or isn't valid."""


def load_defaults() -> dict[str, Any]:
    """The shipped defaults as plain data, one key per section."""
    root = resources.files("perpetual.config") / "defaults"
    data: dict[str, Any] = {}
    for section in SECTIONS:
        text = (root / f"{section}.yaml").read_text(encoding="utf-8")
        data[section] = _parse_mapping(text, f"defaults/{section}.yaml")
    return data


def load_config(overrides: Mapping[str, Any] | None = None) -> Config:
    """Defaults with `overrides` merged on top, validated."""
    merged = load_defaults()
    changed: list[str] = []
    if overrides:
        unknown = sorted(set(overrides) - set(SECTIONS))
        if unknown:
            raise ConfigError(f"unknown config sections: {', '.join(unknown)}")
        changed = sorted(_changed_paths(merged, overrides))
        merged = _merge(merged, overrides)
    try:
        return Config.model_validate(merged | {"overridden_paths": changed})
    except ValueError as error:
        raise ConfigError(str(error)) from error


def load_config_file(path: Path) -> Config:
    """Defaults with the overrides in a YAML file (sections at its top level)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(f"can't read {path}: {error}") from error
    return load_config(_parse_mapping(text, str(path)))


def _parse_mapping(text: str, label: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigError(f"{label} is not valid YAML: {error}") from error
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"{label} must be a mapping at the top level")
    return data


def _merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def _changed_paths(
    base: Mapping[str, Any], override: Mapping[str, Any], prefix: str = ""
) -> Iterator[str]:
    for key, value in override.items():
        path = f"{prefix}{key}"
        current = base.get(key)
        if isinstance(value, Mapping) and isinstance(current, Mapping):
            yield from _changed_paths(current, value, f"{path}.")
        elif value != current:
            yield path
