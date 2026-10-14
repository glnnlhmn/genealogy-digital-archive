# Name: gsm.py
# Path: tools/ops/gsm.py
# Version: 1.6.2+build.20261008.1

"""Genealogy Schema Manager CLI tool for compilation, drift auditing, and validation."""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from gdaschema import GDASchemaManager

__version__ = "1.6.2+build.20261008.1"


def run_gsm(args: argparse.Namespace, manager: Optional[GDASchemaManager] = None) -> int:
    """Execute GSM workflows against a GDASchemaManager collection."""
    mgr = manager or GDASchemaManager()

    # Resolve target list: single schema or entire collection
    if args.schema:
        if args.schema not in mgr:
            print(f"[GSM] ERROR: Unregistered schema: '{args.schema}'")
            return 1
        targets = [mgr[args.schema]]
    else:
        targets = list(mgr)

    # 1. READ-ONLY DRIFT AUDIT (--check)
    if args.check:
        print(f"[GSM] Checking drift for {len(targets)} schema(s)...")
        drift_count = 0
        for schema in targets:
            has_drift, reason = schema.inspect_drift()
            if has_drift:
                print(f"[GSM] DRIFTED: {schema.key} -> {reason}")
                drift_count += 1
            else:
                print(f"[GSM] SYNCHRONIZED: {schema.key}")
        print(f"[GSM] Audit complete: {drift_count} drifted/missing, {len(targets) - drift_count} synchronized.")
        return 1 if drift_count > 0 else 0

    # 2. META-SCHEMA VALIDATION (--validate)
    if args.validate:
        print(f"[GSM] Validating {len(targets)} schema(s) against Draft 2020-12...")
        failures = 0
        for schema in targets:
            valid, err = schema.validate()
            if not valid:
                print(f"[GSM] FAILED: {schema.key} -> {err}")
                failures += 1
                continue
            print(f"[GSM] VALID:   {schema.key}")
        return 1 if failures > 0 else 0

    # 3. SCHEMA COMPILATION & PERSISTENCE (--compile)
    actioned = 0
    print(f"[GSM] Compiling {len(targets)} schema(s)...")
    for schema in targets:
        has_drift, _ = schema.inspect_drift()
        if args.force or has_drift:
            schema.write(create_backup=False)
            status = "Updated (drift detected)" if has_drift else "Forced"
            print(f"[GSM] {status}: {schema.target_path}")
            actioned += 1
        else:
            print(f"[GSM] Skipped (synchronized): {schema.key}")
    print(f"[GSM] Compilation finished: {actioned} actioned, {len(targets) - actioned} skipped.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint supporting parameter injection."""
    parser = argparse.ArgumentParser(
        description="Genealogy Schema Manager (GSM): Compile, check drift, and validate JSON schemas."
    )
    parser.add_argument(
        "schema",
        nargs="?",
        default=None,
        help="Optional specific schema filename to target (e.g. '_enums.schema.json'). If omitted, operates on all.",
    )
    parser.add_argument(
        "-c", "--compile",
        action="store_true",
        help="Compile and persist schema(s) if drift is detected (or if --force is set).",
    )
    parser.add_argument(
        "-k", "--check",
        action="store_true",
        help="Read-only audit: Check if on-disk files match generator definitions without modifying files.",
    )
    parser.add_argument(
        "-v", "--validate",
        action="store_true",
        help="Validate schema syntax against JSON Schema Draft 2020-12 meta-schema.",
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force overwrite files during compilation even if synchronized.",
    )

    args = parser.parse_args(argv)

    if not any((args.compile, args.check, args.validate)):
        parser.print_help()
        return 0

    return run_gsm(args)


if __name__ == "__main__":
    sys.exit(main())