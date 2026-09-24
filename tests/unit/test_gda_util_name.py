"""
Unit tests for GDAUtil.build_display_name.
Verifies standard canonical assembly and strict elimination of periods.
"""

from tools.lib.gda_core.GDAUtil import GDAUtil


def test_build_display_name_full_strips_periods():
    name_obj = {
        "given": "Jacob",
        "middle": "S.",
        "surname": "Lehman",
        "suffix": "Jr."
    }
    # Periods in "S." and "Jr." must be stripped
    assert GDAUtil.build_display_name(name_obj) == "Jacob S Lehman Jr"


def test_build_display_name_initial_given():
    name_obj = {
        "given": "D.",
        "middle": "Smiley",
        "surname": "Lehman"
    }
    assert GDAUtil.build_display_name(name_obj) == "D Smiley Lehman"


def test_build_display_name_no_middle_or_suffix():
    name_obj = {
        "given": "Anna",
        "surname": "Baer"
    }
    assert GDAUtil.build_display_name(name_obj) == "Anna Baer"


def test_build_display_name_raw_fallback():
    name_obj = {
        "raw_name": "Old Uncle Jacob.",
        "given": None,
        "surname": None
    }
    assert GDAUtil.build_display_name(name_obj) == "Old Uncle Jacob"


def test_build_display_name_empty_or_none():
    assert GDAUtil.build_display_name(None) == "UNKNOWN"
    assert GDAUtil.build_display_name({}) == "UNKNOWN"
