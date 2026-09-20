# GTR (Genealogy Token Registry) Tool Runbook

## 1. Overview
The gtr.py operational CLI tool provides programmatic entry and maintenance for controlled vocabularies, token registries, and jurisdiction alias mappings defined in schemas/naming/_token_registry.json. It guarantees alphabetized serialization for clean Git diffs and creates timestamped pre-execution backups before every write operation.

## 2. Location & Dependencies
* Script Path: tools/ops/gtr.py
* Log Directory: logs/gtr-[YYYYMMDD_HHMMSS].log
* Target Registry: schemas/naming/_token_registry.json
* Dependencies: Python Standard Library (argparse, datetime, json, pathlib, shutil, sys)

## 3. Supported Vocabularies
* List Vocabularies (Value-less tokens):
  * counties
  * conflicts
  * award_categories
  * diploma_levels
  * other_categories
  * news_classifications
  * record_types
* Dictionary Vocabularies (Key-Value mappings):
  * states (e.g., "PA": "Pennsylvania")
  * jurisdictions (e.g., "PA_CUM": "PA_CUM")
  * pub_codes (e.g., "PATNEWS": "The Patriot-News")

## 4. CLI Syntax & Options

Syntax:
python tools/ops/gtr.py vocabulary key [value] [-v] [--debug]

Parameters:
* vocabulary: Target controlled vocabulary name.
* key: Token name, dictionary key, or jurisdiction alias.
* value (Optional): Target canonical value for dictionary vocabularies. For jurisdictions, if omitted, it defaults to the key value.
* -v, --verbose: Outputs diagnostic logs and session execution details to logs/.
* --debug: Prints runtime debug information to standard error.

## 5. Usage Examples

Register a new list token (auto-sorted alphabetically):
python tools/ops/gtr.py counties "Franklin" -v

Register a jurisdiction alias mapping (value defaults to key):
python tools/ops/gtr.py jurisdictions "PA_FRA" -v

Register or update a publication code:
python tools/ops/gtr.py pub_codes "SENTINEL" "The Sentinel" -v

## 6. Test Suite & Verification
Verification is maintained via an isolated pytest suite:
pytest tests/test_gtr.py -v