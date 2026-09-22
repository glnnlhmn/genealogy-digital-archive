# Name: test_schema_enums.py
# Path: tests/integrity/test_schema_enums.py

"""
Pytest test suite for SchemaEnums registry within gda_core.
"""

import pytest
from tools.lib.gda_core.registry import SchemaEnums


def test_enum_lookup():
    fact_types = SchemaEnums["enum_fact_type"]
    assert isinstance(fact_types, list)
    assert "Census" in fact_types


def test_enum_list_formatting():
    sex_values = SchemaEnums["enum_sex"]
    assert isinstance(sex_values, list)
    formatted = ", ".join(str(v) for v in sex_values)
    assert "Male" in formatted
    assert "Unknown" in formatted


def test_validation():
    assert SchemaEnums.is_valid("enum_sex", "Male")
    assert SchemaEnums.is_valid("enum_sex", None)
    assert not SchemaEnums.is_valid("enum_sex", "M")
    assert not SchemaEnums.is_valid("enum_sex", "INVALID")


def test_missing():
    with pytest.raises(KeyError):
        _ = SchemaEnums["nonexistent"]