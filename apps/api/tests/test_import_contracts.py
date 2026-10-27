"""Prove each import-linter contract catches a violation (IMPL_PLAN §3.3).

Each case copies the package to a temporary directory, plants one forbidden import
and runs `lint-imports` against the copy with the repository's contracts.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_DIR = REPO_ROOT / "apps" / "api" / "perpetual"
LINT_IMPORTS = Path(sys.executable).parent / "lint-imports"


def run_contracts(tmp_path: Path, plant: dict[str, str]) -> subprocess.CompletedProcess[str]:
    copy = tmp_path / "src" / "perpetual"
    shutil.copytree(PACKAGE_DIR, copy, ignore=shutil.ignore_patterns("__pycache__"))
    for relative_path, source in plant.items():
        (copy / relative_path).write_text(source)
    env = {**os.environ, "PYTHONPATH": str(copy.parent)}
    return subprocess.run(
        [str(LINT_IMPORTS), "--config", str(REPO_ROOT / "pyproject.toml"), "--no-cache"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("module", "statement", "contract"),
    [
        ("models/bad.py", "import perpetual.graph", "models, ids and config import nothing else"),
        ("models/bad.py", "import fastapi", "domain models never import FastAPI or SQLAlchemy"),
        ("models/bad.py", "import sqlalchemy", "domain models never import FastAPI or SQLAlchemy"),
        ("collectors/bad.py", "import perpetual.rules", "collectors only collect"),
        ("normalization/bad.py", "import perpetual.api", "normalization never imports api or cli"),
        ("rules/bad.py", "import perpetual.collectors", "rules never import collectors"),
        ("simulator/bad.py", "import perpetual.importers", "simulator never rediscovers AWS"),
        ("stacks/bad.py", "import perpetual.cli", "nothing below api and cli imports them"),
        ("graph/bad.py", "import perpetual.llm", "the engine never calls an agent"),
        ("recovery/bad.py", "import langgraph", "only llm imports LangChain or LangGraph"),
    ],
)
def test_contract_catches_violation(
    tmp_path: Path, module: str, statement: str, contract: str
) -> None:
    result = run_contracts(tmp_path, {module: f"{statement}\n"})
    assert result.returncode != 0, result.stdout
    assert f"{contract}" in result.stdout
    broken = [line for line in result.stdout.splitlines() if line.endswith("BROKEN")]
    assert any(contract in line for line in broken), result.stdout


def test_llm_may_import_langgraph(tmp_path: Path) -> None:
    result = run_contracts(tmp_path, {"llm/agents.py": "import langgraph\n"})
    assert result.returncode == 0, result.stdout
