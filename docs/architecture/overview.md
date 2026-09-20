# Topology & System Overview

## 1. Architectural Purpose
The Genealogy Digital Archive (GDA) is a local-first, schema-governed data repository and automation framework. It provides standardized intake, verification, canonical entity indexing, and automated audit trails for family history records, biographical artifacts, and controlled vocabularies.

## 2. Directory Structure & Environment
The repository root anchors strictly to G:/My Drive/genealogy-digital-archive.

* backups/: Pre-execution atomic rollback snapshots ([filename].[timestamp].bk) and manifest snapshots (gda_config.json.bk).
* data/: Core production databases and archival repositories.
  * data/archival_records/: Cataloged historical documents and transcriptions.
  * data/entities/: Canonical registry files (people.json, facts.json).
  * data/indexes/: Structured lookup maps and cross-reference indices.
  * data/media/: Curated, verified image and media assets.
  * data/queues/: Work queues and ingestion pipelines.
  * data/stories/: Structured biographical summaries and compiled family lineages.
* docs/: Technical documentation, operational runbooks, and schema definitions.
  * docs/architecture/: System blueprints and topology references.
  * docs/defs/: Protocol standards and governance policies.
  * docs/tools/: Technical runbooks for CLI utilities.
* gtemp/: Ephemeral scripts, scratch parsers, and transient analysis files.
* logs/: Runtime execution logs for permanent operational scripts.
* reports/: Static audit summaries, data extracts, and consistency checks.
* schemas/: JSON Schema contracts governing data models, naming schemes, and registries.
* tests/: Automated test suites verifying tool behavior and schema compliance.
* tools/: Permanent automation suite (tools/ops/ for administrative tools, tools/lib/ for shared libraries).

## 3. Core Operational Pipeline
Data flows through three distinct boundaries to enforce referential integrity and schema compliance:

1. Acquisition & Staging: Raw fact assertions enter the archive as staged factoids (data/entities/factoid-[GUID].json).
2. Intake & Quarantine (GFI): The Genealogy Fact Intake tool (tools/ops/gfi.py) evaluates staged assertions against data/entities/people.json. Malformed, orphan, or recursive entries are diverted to data/entities/quarantine/, while valid records are organized into batch envelopes under data/entities/fact-new/.
3. Master Registry Sync: Valid batches are appended to data/entities/facts.json under fact_registry.schema.json (v1.0.1). Pre-execution backups of the target database and new ingestion payloads are written to backups/, after which temporary batch folders are purged.

## 4. Controlled Vocabularies & Standards
All metadata categorizations, jurisdiction codes, county lists, and publication mappings are governed by schemas/naming/_token_registry.json. The Genealogy Token Registry tool (tools/ops/gtr.py) administers updates to this registry, maintaining alphabetized key sorting, verifying value constraints, and enforcing safe backup protocols prior to modifications.