# MIPLET-002: Operational Tool Versioning & Build Protocol (PEP 440)
<!-- Version: 1.0.0 -->
<!-- Status: Staged for next MIP synthesis (Target: v1.0.6) -->

## Context & Problem Statement
Operational Python scripts under tools/ require a standardized, unambiguous versioning
scheme to distinguish planned revisions/refactors from intra-session bug fixes, patches,
and regenerations.

## Standard Versioning & Build Specification (PEP 440)
All permanent tools under tools/ops/ and tools/lib/ must declare a PEP 440 compliant
__version__ string utilizing local version identifiers (+build.<specifier>):

Format: <major>.<minor>.<revision>+build.<build_id>
Example: __version__ = '1.0.1+build.20260922.1'

### Rules for Version Increments:
1. Revision Bump (<major>.<minor>.<revision+1>):
   - Increment the revision (patch) position whenever starting a planned refactor, feature
     enhancement, or architectural integration (e.g., 1.0.0 -> 1.0.1).
   - Reset the build counter suffix for the new revision.

2. Build Increment (+build.<YYYYMMDD>.<counter>):
   - When regenerating, fixing bugs, resolving test failures, or repairing syntax collisions
     during the development of that revision, the base semantic version remains unchanged.
   - Increment the local build specifier: date of generation (YYYYMMDD) followed by a sequential
     integer counter for that date (e.g., +build.20260922.1 -> +build.20260922.2).

3. Mandatory Variable Placement:
   - Place __version__ near the top of the script following standard module docstrings and imports.
   - Do not maintain disparate BUILD_VERSION or __build__ integers; consolidate all runtime
     traces and logs to report __version__ directly.
