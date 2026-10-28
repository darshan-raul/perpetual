"""Fixture format v1: schema, loader and cross-reference checks (spec §90.1, §104)."""

from perpetual.fixtures.loader import (
    DERIVED_FIELDS,
    FIXTURE_PROJECT_ID,
    FIXTURES_DIR_ENV,
    FixtureError,
    FixtureIssue,
    expand,
    fixture_names,
    load_fixture,
    parse_fixture,
    resolve_fixture,
)
from perpetual.fixtures.schema import FORMAT, VERSION, Fixture, fixture_json_schema
from perpetual.fixtures.validate import check_references

__all__ = [
    "DERIVED_FIELDS",
    "FIXTURES_DIR_ENV",
    "FIXTURE_PROJECT_ID",
    "FORMAT",
    "VERSION",
    "Fixture",
    "FixtureError",
    "FixtureIssue",
    "check_references",
    "expand",
    "fixture_json_schema",
    "fixture_names",
    "load_fixture",
    "parse_fixture",
    "resolve_fixture",
]
