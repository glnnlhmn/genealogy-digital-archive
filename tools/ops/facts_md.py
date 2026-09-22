# Name: facts_md.py
# Path: tools/ops/facts_md.py

import argparse
import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path

from tools.lib.gda_core.GDAConfig import CONFIG
from tools.lib.gda_core.GDALogger import setup_logger
from tools.lib.gda_core.GDAUtil import GDAUtil
from tools.lib.gda_core.registry import SchemaEnums

BUILD_VERSION = "1.1.0"


def resolve_insp_report(insp_arg: str | None = None, reports_dir: Path | None = None) -> Path:
    """
    Resolves the facts_insp audit summary file:
    1. If --insp is specified:
       - Appends '.json' if extension is missing.
       - Prefixes with CONFIG.reports if no directory path is provided.
       - Raises FileNotFoundError if the file does not exist.
    2. If --insp is omitted:
       - Discovers the latest 'facts_audit_summary_*.json' in CONFIG.reports.
       - Raises FileNotFoundError if no report exists, advising that facts_insp must be run first.
    """
    r_dir = reports_dir or CONFIG.reports

    if insp_arg:
        target = Path(insp_arg)
        if not target.suffix:
            target = target.with_suffix(".json")
        
        if len(target.parts) == 1:
            target = r_dir / target

        if not target.exists():
            raise FileNotFoundError(f"Inspection audit report not found: {target}")
        return target

    candidates = sorted(r_dir.glob("facts_audit_summary_*.json"), key=lambda p: p.name, reverse=True)
    if not candidates:
        candidates = sorted(Path(".").glob("facts_audit_summary_*.json"), key=lambda p: p.name, reverse=True)

    if not candidates:
        raise FileNotFoundError("No audit summary report found. Run facts_insp before executing remediation.")

    return candidates[0]


def fix_tier_1_facts(
    audit_file: Path,
    facts_path: Path | None = None,
    verbose: bool = False,
    logger: logging.Logger | None = None,
) -> bool:
    """
    Tier 1: Record Validation & Formatting
    Remediates Stage 1 findings (UUID/Identifier formatting, typology/controlled vocabularies, date modifiers).
    """
    log = logger or logging.getLogger("facts_md")
    log.info("Function STARTED: fix_tier_1_facts (Tier 1: Record Validation & Formatting)", extra={"sys_event": True})
    start_time = datetime.now()

    target_path = facts_path or CONFIG.facts
    if not target_path.exists():
        log.error(f"Facts registry not found at {target_path}")
        log.info(f"Function STOPPED: fix_tier_1_facts | Duration: {(datetime.now() - start_time).total_seconds():.2f}s", extra={"sys_event": True})
        return False

    if not audit_file.exists():
        log.error(f"Audit summary not found at {audit_file}")
        log.info(f"Function STOPPED: fix_tier_1_facts | Duration: {(datetime.now() - start_time).total_seconds():.2f}s", extra={"sys_event": True})
        return False

    audit_data = GDAUtil.load_json(audit_file)

    flagged_fact_ids = {
        item["fact_id"]
        for item in audit_data.get("findings", [])
        if item.get("category") == "Schema"
    }

    if not flagged_fact_ids:
        log.info("No non-compliant fact identifiers flagged for correction in Tier 1.")
        log.info(f"Function STOPPED: fix_tier_1_facts | Duration: {(datetime.now() - start_time).total_seconds():.2f}s", extra={"sys_event": True})
        return True

    registry = GDAUtil.load_json(target_path)
    facts_list = registry.get("facts", []) if isinstance(registry, dict) else registry
    existing_ids = {fact.get("fact_id") for fact in facts_list if isinstance(fact, dict) and fact.get("fact_id")}
    updated_count = 0

    for fact in facts_list:
        if not isinstance(fact, dict):
            continue
        fid = fact.get("fact_id")
        if fid in flagged_fact_ids:
            old_id = fid
            while True:
                new_uuid = str(uuid.uuid4())
                if new_uuid not in existing_ids:
                    break
            fact["fact_id"] = new_uuid
            existing_ids.add(new_uuid)
            updated_count += 1

            if verbose:
                log.info(f"[RECORD UPDATE] Person: {fact.get('person_id')} | Old: '{old_id}' -> New: '{new_uuid}'")
            else:
                log.debug(f"Updated fact_id: {old_id} -> {new_uuid}")

    if updated_count > 0:
        GDAUtil.save_json(target_path, registry)
        log.info(f"Safely persisted {updated_count} updated records to {target_path.name}.")
    else:
        log.info("No matching fact identifiers found in registry to update. File not modified.")

    duration = (datetime.now() - start_time).total_seconds()
    log.info(f"Tier 1 Summary: Successfully updated {updated_count} fact records.")
    log.info(f"Function STOPPED: fix_tier_1_facts | Duration: {duration:.2f}s", extra={"sys_event": True})
    return True


def fix_tier_2_facts(
    audit_file: Path,
    facts_path: Path | None = None,
    verbose: bool = False,
    logger: logging.Logger | None = None,
) -> bool:
    """
    Tier 2: Biological & Chronological Plausibility (Placeholder)
    Remediates Stage 2 findings (Lifespan bounds, pre-natal, non-exempt post-mortem facts).
    """
    log = logger or logging.getLogger("facts_md")
    log.info("Function STARTED: fix_tier_2_facts (Tier 2: Biological & Chronological Plausibility)", extra={"sys_event": True})
    log.info("Status: Placeholder - not yet implemented.")
    log.info("Function STOPPED: fix_tier_2_facts | Total records updated: 0", extra={"sys_event": True})
    return True


def fix_tier_3_facts(
    audit_file: Path,
    facts_path: Path | None = None,
    verbose: bool = False,
    logger: logging.Logger | None = None,
) -> bool:
    """
    Tier 3: Deduplication & Merge Proposals (Placeholder)
    Remediates Stage 3 findings (Redundant source extractions, duplicate event assertions).
    """
    log = logger or logging.getLogger("facts_md")
    log.info("Function STARTED: fix_tier_3_facts (Tier 3: Deduplication & Merge Proposals)", extra={"sys_event": True})
    log.info("Status: Placeholder - not yet implemented.")
    log.info("Function STOPPED: fix_tier_3_facts | Total records updated: 0", extra={"sys_event": True})
    return True


def fix_tier_4_facts(
    audit_file: Path,
    facts_path: Path | None = None,
    verbose: bool = False,
    logger: logging.Logger | None = None,
) -> bool:
    """
    Tier 4: Relational Reciprocal Consistency (Placeholder)
    Remediates Stage 4 findings (Unreciprocated partner assertions, missing spousal facts).
    """
    log = logger or logging.getLogger("facts_md")
    log.info("Function STARTED: fix_tier_4_facts (Tier 4: Relational Reciprocal Consistency)", extra={"sys_event": True})
    log.info("Status: Placeholder - not yet implemented.")
    log.info("Function STOPPED: fix_tier_4_facts | Total records updated: 0", extra={"sys_event": True})
    return True


def run_all_fixes(
    audit_file: Path,
    facts_path: Path | None = None,
    verbose: bool = False,
    logger: logging.Logger | None = None,
):
    """Executes all tiers sequentially with a single pre-execution backup of facts.json."""
    log = logger or logging.getLogger("facts_md")
    target_path = facts_path or CONFIG.facts
    log.info("Batch Execution STARTED: Running all pipeline tiers", extra={"sys_event": True})
    start_time = datetime.now()

    backup_file = GDAUtil.create_safe_backup(target_path)
    log.info(f"Safe Backup Protocol: verified snapshot created at {backup_file}")

    fix_tier_1_facts(audit_file=audit_file, facts_path=target_path, verbose=verbose, logger=log)
    fix_tier_2_facts(audit_file=audit_file, facts_path=target_path, verbose=verbose, logger=log)
    fix_tier_3_facts(audit_file=audit_file, facts_path=target_path, verbose=verbose, logger=log)
    fix_tier_4_facts(audit_file=audit_file, facts_path=target_path, verbose=verbose, logger=log)

    duration = (datetime.now() - start_time).total_seconds()
    log.info(f"Batch Execution STOPPED: All pipeline tiers finished | Total Duration: {duration:.2f}s", extra={"sys_event": True})


def interactive_menu(audit_file: Path, verbose: bool = False, logger: logging.Logger | None = None):
    """Interactive menu loop supporting tier selection and behind-the-menu verbose logging."""
    log = logger or logging.getLogger("facts_md")
    current_verbose = verbose
    target_path = CONFIG.facts

    while True:
        v_status = "ON" if current_verbose else "OFF"
        print("\n=======================================================")
        print(f"  FACTS_MD - Fact Remediation Pipeline ({BUILD_VERSION})")
        print(f"  Target Facts: {target_path}")
        print(f"  Audit Report: {audit_file.name}")
        print(f"  Verbose Mode: {v_status}")
        print("=======================================================")
        print("  1. Tier 1: Record Validation & Formatting")
        print("  2. Tier 2: Biological & Chronological Plausibility")
        print("  3. Tier 3: Deduplication & Merge Proposals")
        print("  4. Tier 4: Relational Reciprocal Consistency")
        print("  A. Run All Pipeline Tiers")
        print(f"  V. Toggle Verbose Mode (Currently {v_status})")
        print("  Q. Quit (or press Enter)")
        print("=======================================================")

        choice = input("Select an option [1-4, A, V, Q]: ").strip().upper()

        if choice in ("", "Q"):
            log.info("Session terminated by user from interactive menu.")
            break
        elif choice == "V":
            current_verbose = not current_verbose
            v_status_new = "ON" if current_verbose else "OFF"
            log.info(f"Verbose logging toggled via menu: {v_status_new}")
        elif choice == "1":
            backup_file = GDAUtil.create_safe_backup(target_path)
            log.info(f"Safe Backup Protocol: verified snapshot created at {backup_file}")
            fix_tier_1_facts(audit_file=audit_file, facts_path=target_path, verbose=current_verbose, logger=log)
        elif choice == "2":
            backup_file = GDAUtil.create_safe_backup(target_path)
            log.info(f"Safe Backup Protocol: verified snapshot created at {backup_file}")
            fix_tier_2_facts(audit_file=audit_file, facts_path=target_path, verbose=current_verbose, logger=log)
        elif choice == "3":
            backup_file = GDAUtil.create_safe_backup(target_path)
            log.info(f"Safe Backup Protocol: verified snapshot created at {backup_file}")
            fix_tier_3_facts(audit_file=audit_file, facts_path=target_path, verbose=current_verbose, logger=log)
        elif choice == "4":
            backup_file = GDAUtil.create_safe_backup(target_path)
            log.info(f"Safe Backup Protocol: verified snapshot created at {backup_file}")
            fix_tier_4_facts(audit_file=audit_file, facts_path=target_path, verbose=current_verbose, logger=log)
        elif choice == "A":
            run_all_fixes(audit_file=audit_file, facts_path=target_path, verbose=current_verbose, logger=log)
        else:
            print("Invalid selection. Please choose an option from the menu.")


def main():
    parser = argparse.ArgumentParser(description="Facts Remediation Pipeline Tool (facts_md)")
    parser.add_argument("--insp", type=str, default=None, help="Explicit audit report (filename or path; default: latest in reports/)")
    parser.add_argument("--tier1", action="store_true", help="Run Tier 1: Record validation & formatting")
    parser.add_argument("--tier2", action="store_true", help="Run Tier 2: Biological & chronological plausibility")
    parser.add_argument("--tier3", action="store_true", help="Run Tier 3: Deduplication & merge proposals")
    parser.add_argument("--tier4", action="store_true", help="Run Tier 4: Relational reciprocal consistency")
    parser.add_argument("--all", action="store_true", help="Run all pipeline tiers headlessly")
    parser.add_argument("--debug", action="store_true", help="Enable debug trace output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose diagnostics")

    args = parser.parse_args()

    c_level = logging.DEBUG if args.debug else logging.INFO
    logger = setup_logger("facts_md", console_level=c_level, file_level=logging.DEBUG)
    logger.info(f"Initialized facts_md v{BUILD_VERSION}", extra={"sys_event": True})
    if args.verbose:
        logger.info("Verbose logging enabled: detailed record-level tracking active.")
    if args.debug:
        logger.info("Debug tracing active.")

    try:
        audit_file = resolve_insp_report(insp_arg=args.insp)
        logger.info(f"Resolved inspection audit report: {audit_file}")
    except FileNotFoundError as e:
        logger.error(str(e))
        print(f"\n[FATAL ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    headless_actions = [args.tier1, args.tier2, args.tier3, args.tier4, args.all]

    if any(headless_actions):
        logger.info("Executing in headless CLI mode.")
        if args.all:
            run_all_fixes(audit_file=audit_file, verbose=args.verbose, logger=logger)
        else:
            backup_file = GDAUtil.create_safe_backup(CONFIG.facts)
            logger.info(f"Safe Backup Protocol: verified snapshot created at {backup_file}")
            if args.tier1:
                fix_tier_1_facts(audit_file=audit_file, verbose=args.verbose, logger=logger)
            if args.tier2:
                fix_tier_2_facts(audit_file=audit_file, verbose=args.verbose, logger=logger)
            if args.tier3:
                fix_tier_3_facts(audit_file=audit_file, verbose=args.verbose, logger=logger)
            if args.tier4:
                fix_tier_4_facts(audit_file=audit_file, verbose=args.verbose, logger=logger)
    else:
        interactive_menu(audit_file=audit_file, verbose=args.verbose, logger=logger)


if __name__ == "__main__":
    main()