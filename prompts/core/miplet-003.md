# MIPLET-003: Operational Tool Acronym Realignment (GNA -> GAM)
<!-- Version: 1.0.0 -->
<!-- Status: Staged for next MIP synthesis (Target: v1.0.6) -->

## Context & Operational Alignment
The operational system manager tool historically known as `gna.py` has been formally renamed
to `gam.py` (Genealogy Archive Manager) to eliminate naming ambiguities and align directly with
the standard 3-letter operational tool naming schema (gpi, gpa, gsi, gfi, gtr, gam).

## Routing & Manifest Standards
1. Permanent Tool Path: `tools/ops/gam.py`
2. Integration Test Path: `tests/integration/test_gam.py`
3. Report Outputs: `reports/gam_audit_[timestamp].json` and `reports/gam_audit_[timestamp].md`
4. Logging Channel: `logs/gam-[timestamp].log`
