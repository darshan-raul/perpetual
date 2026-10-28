"""Typed configuration loading and versioned defaults (IMPL_PLAN D12)."""

from perpetual.config.loader import (
    SECTIONS,
    ConfigError,
    load_config,
    load_config_file,
    load_defaults,
)
from perpetual.config.schema import (
    BufferConfig,
    Config,
    CostUnits,
    EvidenceConfig,
    EvidenceWeight,
    FreshnessConfig,
    LimitsConfig,
    OutOfScopeCategory,
    RtoScopeConfig,
    ScoringConfig,
    Severity,
)

__all__ = [
    "SECTIONS",
    "BufferConfig",
    "Config",
    "ConfigError",
    "CostUnits",
    "EvidenceConfig",
    "EvidenceWeight",
    "FreshnessConfig",
    "LimitsConfig",
    "OutOfScopeCategory",
    "RtoScopeConfig",
    "ScoringConfig",
    "Severity",
    "load_config",
    "load_config_file",
    "load_defaults",
]
