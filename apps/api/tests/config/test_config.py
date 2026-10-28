"""Typed config defaults and project overrides (IMPL_PLAN D12; spec §22, §24.1, §31,
§49.2, §59.1, §76.1)."""

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from perpetual.config import (
    SECTIONS,
    ConfigError,
    OutOfScopeCategory,
    Severity,
    load_config,
    load_config_file,
    load_defaults,
)
from perpetual.models import FreshnessPolicy


def test_defaults_load_with_the_spec_values() -> None:
    config = load_config()
    weights = config.evidence.weights
    assert weights["terraform_reference"].weight == 1.0
    assert weights["cloudtrail_mapped_principal"].weight == 0.95
    assert weights["iam_wildcard_resource"].supporting_only
    assert config.evidence.combination == "noisy_or"
    assert config.scoring.severity_weights[Severity.CRITICAL] == -25
    assert config.buffer.contingency_percent == Decimal(10)
    assert config.freshness.measurement_max_age == timedelta(minutes=15)
    assert config.limits.alternative_selection_cap == 32
    assert config.limits.cost.days_per_month == Decimal(730) / 24
    assert config.overridden_paths == []
    assert set(config.versions) == set(SECTIONS)


def test_out_of_scope_defaults_cover_the_spec_categories() -> None:
    scope = load_config().rto_scope
    assert scope.category_of("codepipeline/pipeline") is OutOfScopeCategory.CICD
    assert scope.category_of("logs/log-group") is OutOfScopeCategory.LOGGING
    assert scope.category_of("rds/db") is None
    assert "cloudwatch/alarm" in scope.out_of_scope_type_keys


def test_freshness_config_builds_the_domain_policy() -> None:
    # config can't import models, so the two must keep the same fields.
    freshness = load_config().freshness
    policy = FreshnessPolicy.model_validate(freshness.model_dump())
    assert policy.inventory_max_age == timedelta(hours=24)


def test_override_changes_one_value_and_records_it() -> None:
    config = load_config(
        {"evidence": {"weights": {"endpoint_string_match": {"weight": 0.6}}}, "limits": {}}
    )
    assert config.evidence.weights["endpoint_string_match"].weight == 0.6
    # The rest of the entry and its siblings keep their defaults.
    assert config.evidence.weights["endpoint_string_match"].group == "configuration_references"
    assert config.evidence.weights["terraform_reference"].weight == 1.0
    assert config.overridden_paths == ["evidence.weights.endpoint_string_match.weight"]


def test_an_override_equal_to_the_default_is_not_recorded() -> None:
    assert load_config({"scoring": {"severity_weights": {"high": -10}}}).overridden_paths == []


def test_lists_are_replaced_not_merged() -> None:
    config = load_config({"rto_scope": {"out_of_scope": {"logging": []}}})
    assert config.rto_scope.category_of("logs/log-group") is None
    assert config.rto_scope.category_of("codepipeline/pipeline") is OutOfScopeCategory.CICD


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"evidnce": {}}, "unknown config sections: evidnce"),
        ({"evidence": {"review_threshold": 0.8}}, "Extra inputs are not permitted"),
        ({"evidence": {"weights": {"x": {"weight": 1.2, "group": "terraform"}}}}, "less than"),
        ({"evidence": {"weights": {"x": {"weight": 0.5, "group": "nope"}}}}, "unknown group"),
        (
            {
                "evidence": {
                    "weights": {"x": {"weight": 0.5, "group": "terraform", "supporting_only": True}}
                }
            },
            "supporting-only evidence has weight 0",
        ),
        ({"evidence": {"correlation_groups": ["terraform", "terraform"]}}, "must not repeat"),
        ({"evidence": {"combination": "sum"}}, "noisy_or"),
        ({"scoring": {"severity_weights": {"low": -30}}}, "never cost more"),
        ({"scoring": {"severity_weights": {"info": 1}}}, "never cost more"),
        ({"rto_scope": {"out_of_scope": {"logging": ["Logs/LogGroup"]}}}, "type key"),
        (
            {"rto_scope": {"out_of_scope": {"logging": ["codepipeline/pipeline"]}}},
            "once",
        ),
        ({"buffer": {"contingency_percent": -1}}, "greater than or equal"),
        ({"freshness": {"inventory_max_age": "PT0S"}}, "greater than"),
        ({"limits": {"alternative_selection_cap": 0}}, "greater than or equal"),
    ],
)
def test_invalid_overrides_fail(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        load_config(overrides)


def test_scoring_needs_every_severity(monkeypatch: pytest.MonkeyPatch) -> None:
    defaults = load_defaults()
    del defaults["scoring"]["severity_weights"]["info"]
    monkeypatch.setattr("perpetual.config.loader.load_defaults", lambda: defaults)
    with pytest.raises(ConfigError, match="every severity"):
        load_config()


def test_override_file(tmp_path: Path) -> None:
    path = tmp_path / "perpetual-config.yaml"
    path.write_text("buffer:\n  contingency_percent: 20\n", encoding="utf-8")
    config = load_config_file(path)
    assert config.buffer.contingency_percent == Decimal(20)
    assert config.overridden_paths == ["buffer.contingency_percent"]


def test_empty_override_file_gives_defaults(tmp_path: Path) -> None:
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    assert load_config_file(path).overridden_paths == []


@pytest.mark.parametrize(
    ("text", "message"),
    [("- a\n- b\n", "mapping at the top level"), ("buffer: [unclosed\n", "not valid YAML")],
)
def test_bad_override_files(tmp_path: Path, text: str, message: str) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match=message):
        load_config_file(path)


def test_missing_override_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="can't read"):
        load_config_file(tmp_path / "missing.yaml")
