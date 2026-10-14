# Name: test_schema_util.py
# Path: tools/lib/gdaschema/tests/test_schema_util.py
# Version: 1.0.0rc1+build.r2

"""Unit test suite verifying schema_util envelope builder and formatting utilities.

Operational Role:
    Validates Draft 2020-12 envelope scaffolding, canonical URI resolution,
    deterministic 2-space indentation formatting, and _name/_path metadata
    enforcement required by GSI script intake.

Test Structure & Protocol:
    - Atomized tests: Strict 1:1 behavioral assertion mapping per test function.
    - Fully decorated: Decorated with @pytest.mark.unit and @pytest.mark.smoke.
    - Dependencies: gdaschema.schema_util, pytest.
"""

from __future__ import annotations

import pytest

from gdaschema.schema_util import (
    CANONICAL_SCHEMA_BASE_URI,
    SCHEMA_DRAFT_2020_12,
    build_schema_envelope,
    format_schema_json,
    normalize_schema_subpath,
    resolve_schema_id,
)

# ==============================================================================
# GROUP 1: URI & PATH NORMALIZATION
# Note: Verifies subpath normalization and canonical URI expansion
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_normalize_schema_subpath_strips_leading_schemas_prefix() -> None:
    """Verify normalize_schema_subpath removes leading 'schemas/' segment."""
    res = normalize_schema_subpath("schemas/defs/_enums.schema.json")
    assert res == "defs/_enums.schema.json"


@pytest.mark.unit
@pytest.mark.smoke
def test_normalize_schema_subpath_normalizes_backslashes() -> None:
    """Verify normalize_schema_subpath converts Windows backslashes to forward slashes."""
    res = normalize_schema_subpath(r"defs\_enums.schema.json")
    assert res == "defs/_enums.schema.json"


@pytest.mark.unit
@pytest.mark.smoke
def test_resolve_schema_id_constructs_canonical_uri() -> None:
    """Verify resolve_schema_id prepends the canonical base URI."""
    res = resolve_schema_id("defs/_enums.schema.json")
    assert res == f"{CANONICAL_SCHEMA_BASE_URI}defs/_enums.schema.json"


# ==============================================================================
# GROUP 2: ENVELOPE GENERATION & GSI METADATA
# Note: Verifies envelope keys, types, _name, and _path formatting
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_build_schema_envelope_standard_fields() -> None:
    """Verify build_schema_envelope emits Draft 2020-12 metadata and GSI paths."""
    env = build_schema_envelope(
        title="Test Schema",
        version="1.0.0",
        description="A test envelope",
        schema_id="defs/_test.schema.json",
    )
    assert env["$schema"] == SCHEMA_DRAFT_2020_12
    assert env["$id"] == f"{CANONICAL_SCHEMA_BASE_URI}defs/_test.schema.json"
    assert env["_name"] == "_test.schema.json"
    assert env["_path"] == "schemas/defs/_test.schema.json"
    assert env["title"] == "Test Schema"
    assert env["version"] == "1.0.0"
    assert env["description"] == "A test envelope"
    assert env["type"] == "object"


@pytest.mark.unit
@pytest.mark.smoke
def test_build_schema_envelope_absolute_uri_preserved() -> None:
    """Verify build_schema_envelope preserves pre-resolved HTTP URIs in $id."""
    uri = "https://custom.org/schema.json"
    env = build_schema_envelope(
        title="Custom",
        version="1.0.0",
        description="Custom URI envelope",
        schema_id=uri,
    )
    assert env["$id"] == uri


@pytest.mark.unit
@pytest.mark.smoke
def test_build_schema_envelope_empty_schema_type_omits_type_key() -> None:
    """Verify build_schema_envelope omits type attribute when schema_type is empty string."""
    env = build_schema_envelope(
        title="Untyped Schema",
        version="1.0.0",
        description="Untyped definition envelope",
        schema_id="defs/untyped.json",
        schema_type="",
    )
    assert "type" not in env


# ==============================================================================
# GROUP 3: DETERMINISTIC JSON FORMATTING
# Note: Verifies indentation and trailing newline invariants
# ==============================================================================


@pytest.mark.unit
@pytest.mark.smoke
def test_format_schema_json_two_space_indent_and_trailing_newline() -> None:
    """Verify format_schema_json formats with 2 spaces and ends with a newline."""
    data = {"b": 2, "a": 1}
    out = format_schema_json(data)
    assert out == '{\n  "b": 2,\n  "a": 1\n}\n'