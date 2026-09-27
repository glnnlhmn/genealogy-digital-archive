# Miplet 018: Fact Consolidation & Architectural Boundaries
<!-- Target: MIP-Core.md Section 2 (Permanent Automation & Tooling Suite) & Section 4 -->

### Tool Addition: `tools/ops/facts_merge.py`
* **Genealogy Fact Merger:** Merges duplicate fact clusters into newly minted canonical assertions adhering to the 6-group consolidation model.
* **Safe Backup & Commit Pipeline:** Defaults to safe dry-run. Commits atomic updates to `data/entities/facts.json` with pre-execution snapshots under `backups/` only when `--run` / `-r` (or alias `--apply`) is commanded.
* **Consolidation Audit Reporting:** Automatically emits structured Markdown summaries to `reports/facts_merge_report_[timestamp].md` during active runs (`-r`), detailing minted IDs, absorbed constituents, and offloaded context notes.
* **Postponed Index Synchronization:** Index rebuilding is explicitly decoupled from fact merging. Consolidations emit terminal warnings alerting operators to stale lookup tables in `data/indexes/`; automated reciprocal index rebuilds remain postponed pending dedicated GIX tool development.
* **Atomized Source Invariance:** Sources sharing identical `record_urn` values represent singular digital artifacts; secondary citation divergence is non-existent by definition, and matching URNs consolidate via exact deduplication and attribute backfilling.
* **Inspection Decoupling:** Schema and chronological validation remains decoupled from merge execution, allowing manual or chained execution via `facts_insp.py`.
