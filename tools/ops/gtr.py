# Name: gtr.py
# Path: tools/ops/gtr.py

"""GTR (Genealogy Token Registry).

Operational CLI tool to safely append validated controlled vocabularies, tokens,
and aliases to schemas/naming/_token_registry.json with pre-execution backups.
"""

import argparse
import logging
from pathlib import Path
import sys
from typing import Dict, Optional, Set

# Ensure repository root is on sys.path for standalone invocation
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.lib.gda_core.GDAConfig import CONFIG
from tools.lib.gda_core.GDALogger import setup_logger
from tools.lib.gda_core.GDAUtil import GDAUtil

__version__ = "1.0.1+build.20260922.1"

LIST_VOCABULARIES: Set[str] = {
    "counties",
    "conflicts",
    "award_categories",
    "diploma_levels",
    "other_categories",
    "news_classifications",
    "record_types",
}

DICT_VOCABULARIES: Set[str] = {
    "states",
    "jurisdictions",
    "pub_codes",
}


def load_registry(
    registry_path: Optional[Path] = None,
    logger: Optional[logging.Logger] = None,
) -> dict:
    """Loads the token registry JSON payload from disk.

    Args:
        registry_path (Optional[Path]): Explicit path to _token_registry.json.
        logger (Optional[logging.Logger]): Operational logger.

    Returns:
        dict: Parsed registry data dictionary.
    """
    target = registry_path or CONFIG.token_registry
    log = logger or logging.getLogger("gtr")

    if not target.exists():
        err = f"Token registry not found at {target.as_posix()}"
        log.error(err)
        sys.exit(1)

    return GDAUtil.load_json(target)


def save_registry(
    data: dict,
    registry_path: Optional[Path] = None,
    backups_dir: Optional[Path] = None,
    verbose: bool = False,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Creates a Safe Backup and atomically saves updated registry data.

    Args:
        data (dict): Updated registry payload to persist.
        registry_path (Optional[Path]): Explicit path to _token_registry.json.
        backups_dir (Optional[Path]): Explicit backup directory.
        verbose (bool): Whether to log detailed diagnostic traces.
        logger (Optional[logging.Logger]): Operational logger.
    """
    target = registry_path or CONFIG.token_registry
    dest_backups = backups_dir or CONFIG.backups
    log = logger or logging.getLogger("gtr")

    backup_file = GDAUtil.create_safe_backup(target, backup_dir=dest_backups)
    if verbose:
        log.info(f"Pre-execution backup created: {backup_file.name}", extra={"sys_event": True})

    GDAUtil.save_json(target, data)
    msg = f"Successfully updated token registry: {target.as_posix()}"
    print(f"[+] {msg}")
    log.info(msg, extra={"sys_event": True})


def register_token(
    vocabulary: str,
    key: str,
    value: Optional[str] = None,
    registry_path: Optional[Path] = None,
    backups_dir: Optional[Path] = None,
    verbose: bool = False,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Appends or updates a token/mapping within the controlled vocabulary registry.

    Args:
        vocabulary (str): Target vocabulary section.
        key (str): Token string or dictionary key.
        value (Optional[str]): Mapped target value for dictionary vocabularies.
        registry_path (Optional[Path]): Explicit path to _token_registry.json.
        backups_dir (Optional[Path]): Explicit backup directory.
        verbose (bool): Whether to log detailed diagnostic messages.
        logger (Optional[logging.Logger]): Operational logger.
    """
    log = logger or logging.getLogger("gtr")
    target = registry_path or CONFIG.token_registry
    dest_backups = backups_dir or CONFIG.backups

    registry = load_registry(registry_path=target, logger=log)

    if vocabulary in LIST_VOCABULARIES:
        items = registry.get(vocabulary, [])
        if key in items:
            msg = f"Token '{key}' already exists in '{vocabulary}'. No changes made."
            print(f"[-] {msg}")
            if verbose:
                log.info(msg)
            return
        items.append(key)
        items.sort()
        registry[vocabulary] = items
        msg = f"Registered token '{key}' to list '{vocabulary}'."
        print(f"[+] {msg}")
        log.info(msg)

    elif vocabulary in DICT_VOCABULARIES:
        mapping = registry.get(vocabulary, {})
        if key in mapping:
            existing_target = mapping[key]
            if existing_target == value:
                msg = f"Mapping '{key}': '{value}' already exists in '{vocabulary}'. No changes made."
                print(f"[-] {msg}")
                if verbose:
                    log.info(msg)
                return
            msg = f"Updating '{key}' in '{vocabulary}': '{existing_target}' -> '{value}'"
            print(f"[!] {msg}")
            log.info(msg)
        else:
            msg = f"Registered mapping '{key}': '{value}' in '{vocabulary}'."
            print(f"[+] {msg}")
            log.info(msg)

        mapping[key] = value
        registry[vocabulary] = dict(sorted(mapping.items(), key=lambda x: x[0].lower()))

    else:
        valid_vocabs = sorted(list(LIST_VOCABULARIES | DICT_VOCABULARIES))
        err = f"Unknown vocabulary '{vocabulary}'. Must be one of: {', '.join(valid_vocabs)}"
        log.error(err)
        sys.exit(1)

    save_registry(registry, registry_path=target, backups_dir=dest_backups, verbose=verbose, logger=log)


def main() -> None:
    """CLI argument parsing and entry point for GTR operations."""
    parser = argparse.ArgumentParser(
        description=f"GTR ({__version__}): Append controlled vocabulary tokens or mappings to schemas/naming/_token_registry.json."
    )
    parser.add_argument(
        "vocabulary",
        help="Target controlled vocabulary (e.g., jurisdictions, counties, pub_codes, states, record_types)",
    )
    parser.add_argument(
        "key",
        help="Token name, jurisdiction alias, or dictionary key",
    )
    parser.add_argument(
        "value",
        nargs="?",
        default=None,
        help="Canonical target value for dictionary vocabularies (defaults to key if omitted for 'jurisdictions')",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Emit diagnostic output and runtime logging",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Route runtime traces directly to console/stderr",
    )

    args = parser.parse_args()

    c_level = logging.DEBUG if args.debug else logging.INFO
    logger = setup_logger("gtr", console_level=c_level, file_level=logging.DEBUG)
    logger.info(f"Initialized GTR CLI ({__version__}).", extra={"sys_event": True})

    if args.vocabulary == "jurisdictions" and not args.value:
        args.value = args.key
    elif args.vocabulary in DICT_VOCABULARIES and not args.value:
        err = f"Vocabulary '{args.vocabulary}' requires both key and value arguments."
        logger.error(err)
        sys.exit(1)

    register_token(args.vocabulary, args.key, args.value, verbose=args.verbose, logger=logger)


if __name__ == "__main__":
    main()