# Name: gtr.py
# Path: tools/ops/gtr.py
"""GTR (Genealogy Token Registry)

Operational CLI tool to safely append validated controlled vocabularies, tokens,
and aliases to schemas/naming/_token_registry.json with pre-execution backups.

Dependencies:
    - Standard Library: argparse, datetime, json, pathlib, shutil, sys
"""

import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys

ROOT_DIR = Path("G:/My Drive/genealogy-digital-archive")
REGISTRY_PATH = ROOT_DIR / "schemas" / "naming" / "_token_registry.json"
BACKUPS_DIR = ROOT_DIR / "backups"
LOGS_DIR = ROOT_DIR / "logs"

BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = LOGS_DIR / f"gtr-{TIMESTAMP}.log"

LIST_VOCABULARIES = {
    "counties",
    "conflicts",
    "award_categories",
    "diploma_levels",
    "other_categories",
    "news_classifications",
    "record_types"
}

DICT_VOCABULARIES = {
    "states",
    "jurisdictions",
    "pub_codes"
}


def log(msg: str, is_error: bool = False, verbose: bool = False) -> None:
    line = f"[{datetime.now().isoformat()}] {'ERROR: ' if is_error else ''}{msg}\n"
    if is_error:
        sys.stderr.write(line)
    elif verbose:
        sys.stdout.write(line)
    sys.stdout.flush()
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        err = f"Token registry not found at {REGISTRY_PATH.as_posix()}"
        log(err, is_error=True)
        sys.exit(1)
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_registry(data: dict, verbose: bool = False) -> None:
    backup_file = BACKUPS_DIR / f"_token_registry.json.{TIMESTAMP}.bk"
    shutil.copy2(REGISTRY_PATH, backup_file)
    log(f"Pre-execution backup created: {backup_file.name}", verbose=verbose)

    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    msg = f"Successfully updated token registry: {REGISTRY_PATH.as_posix()}"
    print(f"[+] {msg}")
    log(msg, verbose=verbose)


def register_token(vocabulary: str, key: str, value: str = None, verbose: bool = False) -> None:
    registry = load_registry()

    if vocabulary in LIST_VOCABULARIES:
        items = registry.get(vocabulary, [])
        if key in items:
            msg = f"Token '{key}' already exists in '{vocabulary}'. No changes made."
            print(f"[-] {msg}")
            log(msg, verbose=verbose)
            return
        items.append(key)
        items.sort()
        registry[vocabulary] = items
        msg = f"Registered token '{key}' to list '{vocabulary}'."
        print(f"[+] {msg}")
        log(msg, verbose=verbose)

    elif vocabulary in DICT_VOCABULARIES:
        mapping = registry.get(vocabulary, {})
        if key in mapping:
            existing_target = mapping[key]
            if existing_target == value:
                msg = f"Mapping '{key}': '{value}' already exists in '{vocabulary}'. No changes made."
                print(f"[-] {msg}")
                log(msg, verbose=verbose)
                return
            msg = f"Updating '{key}' in '{vocabulary}': '{existing_target}' -> '{value}'"
            print(f"[!] {msg}")
            log(msg, verbose=verbose)
        else:
            msg = f"Registered mapping '{key}': '{value}' in '{vocabulary}'."
            print(f"[+] {msg}")
            log(msg, verbose=verbose)

        mapping[key] = value
        registry[vocabulary] = dict(sorted(mapping.items(), key=lambda x: x[0].lower()))

    else:
        valid_vocabs = sorted(list(LIST_VOCABULARIES | DICT_VOCABULARIES))
        err = f"Unknown vocabulary '{vocabulary}'. Must be one of: {', '.join(valid_vocabs)}"
        log(err, is_error=True)
        sys.exit(1)

    save_registry(registry, verbose=verbose)


def main():
    parser = argparse.ArgumentParser(
        description="GTR: Append controlled vocabulary tokens or mappings to schemas/naming/_token_registry.json."
    )
    parser.add_argument(
        "vocabulary",
        help="Target controlled vocabulary (e.g., jurisdictions, counties, pub_codes, states, record_types)"
    )
    parser.add_argument(
        "key",
        help="Token name, jurisdiction alias, or dictionary key"
    )
    parser.add_argument(
        "value",
        nargs="?",
        default=None,
        help="Canonical target value for dictionary vocabularies (defaults to key if omitted for 'jurisdictions')"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Emit diagnostic output and runtime logging"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Echo runtime debug information to standard error"
    )

    args = parser.parse_args()

    log("Initialized GTR CLI.", verbose=args.verbose)

    if args.vocabulary == "jurisdictions" and not args.value:
        args.value = args.key
    elif args.vocabulary in DICT_VOCABULARIES and not args.value:
        err = f"Vocabulary '{args.vocabulary}' requires both key and value arguments."
        log(err, is_error=True)
        sys.exit(1)

    register_token(args.vocabulary, args.key, args.value, verbose=args.verbose)


if __name__ == "__main__":
    main()