# Name: test_gtr.py
# Path: tests/test_gtr.py
"""Test suite for GTR (Genealogy Token Registry) operational tool."""

import json
from pathlib import Path
import pytest

from tools.ops import gtr

SAMPLE_REGISTRY = {
    "$schema": "schemas/naming/_token_registry.schema.json",
    "schema_version": "1.0.0",
    "counties": ["Cumberland", "Dauphin"],
    "record_types": ["BAP", "CEN", "MAR"],
    "states": {
        "PA": "Pennsylvania",
        "NH": "New Hampshire"
    },
    "jurisdictions": {
        "PA_CUM": "PA_CUM",
        "PA_DAU": "PA_DAU"
    },
    "pub_codes": {
        "PATNEWS": "The Patriot-News"
    }
}


@pytest.fixture
def mock_gtr_env(tmp_path, monkeypatch):
    """Sets up an isolated registry, backup directory, and log directory."""
    schema_dir = tmp_path / "schemas" / "naming"
    schema_dir.mkdir(parents=True, exist_ok=True)
    reg_file = schema_dir / "_token_registry.json"
    reg_file.write_text(json.dumps(SAMPLE_REGISTRY, indent=2), encoding="utf-8")

    backups_dir = tmp_path / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(gtr, "REGISTRY_PATH", reg_file)
    monkeypatch.setattr(gtr, "BACKUPS_DIR", backups_dir)
    monkeypatch.setattr(gtr, "LOGS_DIR", logs_dir)

    return {
        "registry_file": reg_file,
        "backups_dir": backups_dir,
        "logs_dir": logs_dir
    }


def test_register_list_token_success(mock_gtr_env):
    gtr.register_token(vocabulary="counties", key="Adams", value=None)

    data = json.loads(mock_gtr_env["registry_file"].read_text(encoding="utf-8"))
    assert "Adams" in data["counties"]
    # Verify alphabetization
    assert data["counties"] == ["Adams", "Cumberland", "Dauphin"]

    # Verify backup was created
    backups = list(mock_gtr_env["backups_dir"].glob("_token_registry.json.*.bk"))
    assert len(backups) == 1


def test_register_list_token_duplicate_no_op(mock_gtr_env):
    gtr.register_token(vocabulary="counties", key="Cumberland", value=None)

    data = json.loads(mock_gtr_env["registry_file"].read_text(encoding="utf-8"))
    assert data["counties"] == ["Cumberland", "Dauphin"]
    # Duplicate does not trigger backup write
    backups = list(mock_gtr_env["backups_dir"].glob("_token_registry.json.*.bk"))
    assert len(backups) == 0


def test_register_dict_mapping_new_key(mock_gtr_env):
    gtr.register_token(vocabulary="pub_codes", key="EVENEWS", value="The Evening News")

    data = json.loads(mock_gtr_env["registry_file"].read_text(encoding="utf-8"))
    assert data["pub_codes"]["EVENEWS"] == "The Evening News"
    assert data["pub_codes"]["PATNEWS"] == "The Patriot-News"

    backups = list(mock_gtr_env["backups_dir"].glob("_token_registry.json.*.bk"))
    assert len(backups) == 1


def test_register_dict_mapping_update_existing_key(mock_gtr_env):
    gtr.register_token(vocabulary="pub_codes", key="PATNEWS", value="The Patriot-News Updated")

    data = json.loads(mock_gtr_env["registry_file"].read_text(encoding="utf-8"))
    assert data["pub_codes"]["PATNEWS"] == "The Patriot-News Updated"

    backups = list(mock_gtr_env["backups_dir"].glob("_token_registry.json.*.bk"))
    assert len(backups) == 1


def test_register_dict_mapping_duplicate_no_op(mock_gtr_env):
    gtr.register_token(vocabulary="pub_codes", key="PATNEWS", value="The Patriot-News")

    backups = list(mock_gtr_env["backups_dir"].glob("_token_registry.json.*.bk"))
    assert len(backups) == 0


def test_jurisdiction_shortcut_default_value(mock_gtr_env, monkeypatch):
    """Simulates main CLI invocation defaulting value to key for jurisdictions."""
    test_args = ["gtr.py", "jurisdictions", "PA_YOR"]
    monkeypatch.setattr("sys.argv", test_args)

    gtr.main()

    data = json.loads(mock_gtr_env["registry_file"].read_text(encoding="utf-8"))
    assert "PA_YOR" in data["jurisdictions"]
    assert data["jurisdictions"]["PA_YOR"] == "PA_YOR"


def test_invalid_vocabulary_raises_system_exit(mock_gtr_env):
    with pytest.raises(SystemExit):
        gtr.register_token(vocabulary="non_existent_vocab", key="TEST")


def test_dict_vocabulary_missing_value_cli_exit(mock_gtr_env, monkeypatch):
    """Simulates CLI error when dictionary vocabulary is invoked without a target value."""
    test_args = ["gtr.py", "pub_codes", "NEWCODE"]
    monkeypatch.setattr("sys.argv", test_args)

    with pytest.raises(SystemExit):
        gtr.main()