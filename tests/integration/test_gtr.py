# Name: test_gtr.py
# Path: tests/integration/test_gtr.py

"""Integration test suite for GTR (Genealogy Token Registry) operational tool."""

import json
import logging
from pathlib import Path
import pytest

from tools.lib.gda_core.GDAConfig import GDAConfig
from tools.lib.gda_core.GDAUtil import GDAUtil
from tools.ops import gtr

SAMPLE_REGISTRY = {
    "$schema": "schemas/naming/_token_registry.schema.json",
    "schema_version": "1.0.0",
    "counties": ["Cumberland", "Dauphin"],
    "record_types": ["BAP", "CEN", "MAR"],
    "states": {
        "PA": "Pennsylvania",
        "NH": "New Hampshire",
    },
    "jurisdictions": {
        "PA_CUM": "PA_CUM",
        "PA_DAU": "PA_DAU",
    },
    "pub_codes": {
        "PATNEWS": "The Patriot-News",
    },
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

    mock_config = GDAConfig(root=tmp_path, manifest={})
    monkeypatch.setattr("tools.lib.gda_core.GDAConfig.CONFIG", mock_config)
    monkeypatch.setattr("tools.lib.gda_core.GDAUtil.CONFIG", mock_config)
    monkeypatch.setattr("tools.ops.gtr.CONFIG", mock_config)

    test_logger = logging.getLogger("gtr_test")
    test_logger.handlers.clear()
    test_logger.addHandler(logging.NullHandler())

    return {
        "root": tmp_path,
        "config": mock_config,
        "registry_file": reg_file,
        "backups_dir": backups_dir,
        "logs_dir": logs_dir,
        "logger": test_logger,
    }


def test_register_list_token_success(mock_gtr_env):
    """Verifies appending a token to a list vocabulary and automatic sorting."""
    gtr.register_token(
        vocabulary="counties",
        key="Adams",
        value=None,
        registry_path=mock_gtr_env["registry_file"],
        backups_dir=mock_gtr_env["backups_dir"],
        logger=mock_gtr_env["logger"],
    )

    data = GDAUtil.load_json(mock_gtr_env["registry_file"])
    assert "Adams" in data["counties"]
    assert data["counties"] == ["Adams", "Cumberland", "Dauphin"]

    backups = list(mock_gtr_env["backups_dir"].glob("_token_registry.json.*.bk"))
    assert len(backups) == 1


def test_register_list_token_duplicate_no_op(mock_gtr_env):
    """Verifies that duplicate list tokens do not trigger writes or backups."""
    gtr.register_token(
        vocabulary="counties",
        key="Cumberland",
        value=None,
        registry_path=mock_gtr_env["registry_file"],
        backups_dir=mock_gtr_env["backups_dir"],
        logger=mock_gtr_env["logger"],
    )

    data = GDAUtil.load_json(mock_gtr_env["registry_file"])
    assert data["counties"] == ["Cumberland", "Dauphin"]

    backups = list(mock_gtr_env["backups_dir"].glob("_token_registry.json.*.bk"))
    assert len(backups) == 0


def test_register_dict_mapping_new_key(mock_gtr_env):
    """Verifies adding a new key-value pair to a dictionary vocabulary."""
    gtr.register_token(
        vocabulary="pub_codes",
        key="EVENEWS",
        value="The Evening News",
        registry_path=mock_gtr_env["registry_file"],
        backups_dir=mock_gtr_env["backups_dir"],
        logger=mock_gtr_env["logger"],
    )

    data = GDAUtil.load_json(mock_gtr_env["registry_file"])
    assert data["pub_codes"]["EVENEWS"] == "The Evening News"
    assert data["pub_codes"]["PATNEWS"] == "The Patriot-News"

    backups = list(mock_gtr_env["backups_dir"].glob("_token_registry.json.*.bk"))
    assert len(backups) == 1


def test_register_dict_mapping_update_existing_key(mock_gtr_env):
    """Verifies updating an existing dictionary mapping value."""
    gtr.register_token(
        vocabulary="pub_codes",
        key="PATNEWS",
        value="The Patriot-News Updated",
        registry_path=mock_gtr_env["registry_file"],
        backups_dir=mock_gtr_env["backups_dir"],
        logger=mock_gtr_env["logger"],
    )

    data = GDAUtil.load_json(mock_gtr_env["registry_file"])
    assert data["pub_codes"]["PATNEWS"] == "The Patriot-News Updated"

    backups = list(mock_gtr_env["backups_dir"].glob("_token_registry.json.*.bk"))
    assert len(backups) == 1


def test_register_dict_mapping_duplicate_no_op(mock_gtr_env):
    """Verifies that an identical dictionary mapping triggers no mutations or backups."""
    gtr.register_token(
        vocabulary="pub_codes",
        key="PATNEWS",
        value="The Patriot-News",
        registry_path=mock_gtr_env["registry_file"],
        backups_dir=mock_gtr_env["backups_dir"],
        logger=mock_gtr_env["logger"],
    )

    backups = list(mock_gtr_env["backups_dir"].glob("_token_registry.json.*.bk"))
    assert len(backups) == 0


def test_jurisdiction_shortcut_default_value(mock_gtr_env, monkeypatch):
    """Simulates main CLI invocation defaulting value to key for jurisdictions."""
    test_args = ["gtr.py", "jurisdictions", "PA_YOR"]
    monkeypatch.setattr("sys.argv", test_args)

    gtr.main()

    data = GDAUtil.load_json(mock_gtr_env["registry_file"])
    assert "PA_YOR" in data["jurisdictions"]
    assert data["jurisdictions"]["PA_YOR"] == "PA_YOR"


def test_invalid_vocabulary_raises_system_exit(mock_gtr_env):
    """Verifies system exit when supplied with an unregistered vocabulary category."""
    with pytest.raises(SystemExit):
        gtr.register_token(
            vocabulary="non_existent_vocab",
            key="TEST",
            registry_path=mock_gtr_env["registry_file"],
            backups_dir=mock_gtr_env["backups_dir"],
            logger=mock_gtr_env["logger"],
        )


def test_dict_vocabulary_missing_value_cli_exit(mock_gtr_env, monkeypatch):
    """Simulates CLI error when dictionary vocabulary is invoked without a target value."""
    test_args = ["gtr.py", "pub_codes", "NEWCODE"]
    monkeypatch.setattr("sys.argv", test_args)

    with pytest.raises(SystemExit):
        gtr.main()