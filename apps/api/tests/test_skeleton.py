"""Skeleton checks: every pipeline subpackage exists and imports cleanly (IMPL_PLAN §3.2)."""

import importlib

import pytest

import perpetual

SUBPACKAGES = [
    "models",
    "config",
    "ids",
    "fixtures",
    "persistence",
    "collectors",
    "importers",
    "normalization",
    "evidence",
    "graph",
    "stacks",
    "rules",
    "simulator",
    "recovery",
    "optimizer",
    "costing",
    "iac",
    "llm",
    "knowledge",
    "runbooks",
    "api",
    "cli",
]


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_imports(name: str) -> None:
    module = importlib.import_module(f"perpetual.{name}")
    assert module.__doc__, f"perpetual.{name} needs a docstring saying what it owns"


def test_version_is_a_string() -> None:
    assert isinstance(perpetual.__version__, str)
