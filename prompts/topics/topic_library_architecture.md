<!--
Name: topic_library_architecture.md
Path: prompts/topics/topic_library_architecture.md
-->
# Topic Specification: Library Architecture & Packaging Hierarchy
<!-- Version: 1.0.1 -->
<!-- Operational Directive: Ingest this topic specification as a modular overlay extending the active MIP baseline. Do not execute or rewrite without explicit operator command. Confirm processing and state any conflicts. -->

## 1. Architectural Scope & Directory Hierarchy

Shared archive code resides under `tools/lib/`, partitioned into three decoupled, single-responsibility packages. Packages maintain strict directional import boundaries, isolating foundational primitives from high-level domain management.

```text
tools/lib/
  ├── gdacore/
  │     ├── pyproject.toml
  │     ├── src/gdacore/
  │     │     ├── __init__.py
  │     │     ├── config.py
  │     │     ├── introspectable.py
  │     │     ├── logger.py
  │     │     ├── reference_manager.py
  │     │     ├── util.py
  │     │     └── vocabulary_manager.py
  │     └── tests/
  ├── gdaschema/
  │     ├── pyproject.toml
  │     ├── src/gdaschema/
  │     │     └── __init__.py
  │     └── tests/
  └── gdadomain/
        ├── pyproject.toml
        ├── src/gdadomain/
        │     ├── __init__.py
        │     ├── facts.py
        │     ├── locations.py
        │     ├── people.py
        │     └── sites.py
        └── tests/
```

## 2. Library Package Roles & Dependencies

### 2.1 Core Infrastructure (`tools/lib/gdacore/`)

* **Role:** Foundational, domain-agnostic infrastructure services—providing runtime configuration (`GDAConfig`), bracketed logging (`GDALogger`), atomic Safe Backup Protocol and JSON serialization (`GDAUtil`), canonical URN and identifier parsing (`GDAReferenceManager`), controlled vocabulary parsing (`GDAVocabularyManager`), and runtime reflection (`IntrospectableMixin`).

* **Dependency Invariant:** Zero internal dependencies. Imports strictly from the Python standard library and filesystem specifications.

### 2.2 Schema Management (`tools/lib/gdaschema/`)

* **Role:** Primary operational authority for repository schema contracts. Compiles, validates, and emits structural JSON Schema definitions under `schemas/` (entities, indexes, defs, naming tokens). Integrates with `gdacore.GDAVocabularyManager` as the single code authority for enumeration tokens, generating serialized schema files (e.g., `schemas/defs/_enums.schema.json`) and enforcing contract drift detection.

* **Dependency Invariant:** Depends strictly on `gdacore` primitives for configuration, logging, controlled vocabulary definitions (`GDAVocabularyManager`), and filesystem utilities. Zero dependencies on `gdadomain`.

### 2.3 Domain Entity Management (`tools/lib/gdadomain/`)

* **Role:** High-level genealogical business entities and transaction managers—governing active entity stores (`people.json`, `facts.json`, `locations.json`, `sites.json`), sequential ID allocation, reciprocal kinship state machines, biological plausibility boundaries, in-place assertion tombstones, and geographic normalization.

* **Dependency Invariant:** Depends directly on `gdacore` for foundational services and `gdaschema` for schema validation contracts.

## 3. Core Architectural Contracts

### 3.1 Introspection Contract (`IntrospectableMixin`)

All public service classes across all framework libraries inherit `IntrospectableMixin` to provide self-documenting `.help()` discovery in interactive sessions and terminal runs.

* Calling `.help()` without arguments prints an indexed directory of public methods and properties.

* Calling `.help("member_name")` outputs the method call signature, argument types, and docstring summary.

### 3.2 Docstring Specification (PEP 257 & Google Style)

To support runtime reflection via `.help()` and future automated documentation extraction (e.g., Sphinx), all library classes, methods, and functions must adhere strictly to PEP 257 and Google-style docstring conventions (`Args:`, `Returns:`, `Raises:`, `Example:`). Detailed APIs, parameter types, and return values are maintained directly in code docstrings, not in markdown topic files.

### 3.3 State Persistence & In-Place Tombstoning

* **Atomic Writes:** All filesystem mutations and serialized writes must use `GDAUtil` routines to enforce atomic file replacements and pre-write Safe Backups (`backups/[filename].[timestamp].bk`).

* **In-Place Tombstoning:** Deprecated, superseded, or absorbed domain entities and assertions remain in their primary stores (e.g., `data/entities/facts.json`) marked with tombstone metadata (`is_deprecated: true`, `superseded_by: <id>`) rather than moving to external archive stores.

## 4. Packaging, Testing & Installation

### 4.1 Independent Packaging (PEP 518 / PEP 621)

Each library root maintains its own independent `pyproject.toml` declaring its dependencies, metadata, and build requirements.

### 4.2 Test Suite Isolation

Each library houses its own unit and integration tests under `<library>/tests/`.

* Tests adhere to the 7-marker taxonomy and conventions defined in `topic_test_harness.md`.

* Production libraries must satisfy >= 95% statement and branch test coverage. Operational domain managers require >= 85% minimum fail-under.

* Windows workstation test runs must isolate temporary paths using `--basetemp=gtemp/pytest_tmp`.

### 4.3 Development Installation Protocols

Packages are managed via `pip`. For active workstation development, install libraries in editable mode (`-e`) so workspace changes reflect immediately:

```powershell
pip install -e tools/lib/gdacore
pip install -e tools/lib/gdaschema
pip install -e tools/lib/gdadomain
```