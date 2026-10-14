<!--
Name: topic_documentation_standards.md
Path: prompts/topics/topic_documentation_standards.md
-->
# Topic Specification: Documentation & Docstring Standards
<!-- Version: 1.0.0 -->
<!-- Operational Directive: Ingest this topic specification as a modular overlay extending the active MIP baseline. Do not execute or rewrite without explicit operator command. Confirm processing and state any conflicts. -->
## 1. Scope & Operational Purpose

This specification governs the authoring conventions, style contracts, and structural layouts for all system documentation and Python docstrings. Its primary objective is to maintain clear, reproducible, and standardized documentation across the codebase for human operators, automated tools, and future documentation extractors (e.g., Sphinx / `mkdocstrings`).

This specification defines how documentation is written, not the filesystem inventory of what is documented.

## 2. Python Docstring Standards (PEP 257 & Google Style)

All production modules, classes, and callable functions must adhere to PEP 257 docstring conventions formatted using the Google Style Python Docstrings specification.

### 2.1 General Rules

* Enclose docstrings in triple double-quotes (`"""`).
* The summary line must be a concise, imperative sentence ending with a period (e.g., "Mint a new canonical identifier." not "Mints a new...").
* Multi-line docstrings must leave a blank line between the summary sentence and the detailed explanation or section headers.
* Keep explanations focused on behavior, operational guarantees, and side effects.

### 2.2 Section Structure

When applicable, functions and methods must use the following standard Google-style section headers:

```python
def execute_operation(target_id: str, force: bool = False) -> bool:
    """Execute a transactional operation on an entity record.

    Applies the staged mutation against the specified identifier and writes
    the result to disk following validation.

    Args:
        target_id: Canonical entity identifier (e.g., IND-00001).
        force: If True, bypasses dirty checks and overrides existing values.

    Returns:
        True if the mutation succeeded and was persisted; False otherwise.

    Raises:
        KeyError: If target_id does not exist in the active store.
        ValueError: If the entity payload violates validation schemas.

    Example:
        >>> success = execute_operation("IND-00001", force=True)
        >>> assert success is True
    """
```

### 2.3 Module and Class Docstrings

* **Header Metadata Lines (Lines 1–3):** Every Python source file must open with comments declaring `# Name: [filename]`, `# Path: [relative_path]`, and `# Version: 1.0.0+build.r[counter]`, followed by `__version__ = "1.0.0+build.r[counter]"`.
* **Modules:** Must open with a module-level docstring summarizing the script's architectural role, CLI usage summary (if executable), and primary interfaces.
* **Classes:** Must describe the entity, invariants, and state management behavior. Public attributes should be documented in an `Attributes:` section or directly within class-level type annotations.

## 3. User Documentation & Operational Runbook Layout

External user guides and operational tool runbooks adhere to a structured four-part layout focused on actionable operator guidance.

### 3.1 Document Structure

Every operational tool guide must contain the following core sections:

1. **Title & Operational Overview:**
   * One-line declaration of the tool's core responsibility.
   * Clear statement of when and why an operator invokes the tool.

2. **Command-Line Reference & Syntax:**
   * Canonical CLI invocation command.
   * Argument and options reference table:

| Flag / Option | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `-h`, `--help` | flag | None | Show usage help and exit. |
| `-v`, `--verbose` | flag | False | Emit detailed diagnostic logs. |
| `--debug` | flag | False | Route tracebacks directly to standard error. |

3. **Practical Usage Scenarios:**
   * Minimal invocation example (standard path).
   * Parameterized execution example (overrides, dry runs, explicit inputs).
   * Verifiable output expectation (log messages, generated reports, or console summaries).

4. **Diagnostics & Remediation Matrix:**
   * Explicit mapping of potential exit codes, error tags, and failure states to operator recovery procedures:

| Error Tag / Exit Code | Root Cause | Operator Remediation Action |
| :--- | :--- | :--- |
| `ERR_DIRTY_STATE` | Uncommitted changes detected in store. | Re-run with `--force` or execute rollback. |
| `ERR_FILE_NOT_FOUND` | Configured path missing or invalid. | Verify file path parameter and repository anchors. |

## 4. Markdown Formatting & Presentation Rules

* Code listings must always use appropriate language identifiers (`bash`, `powershell`, `python`, `json`, `text`).
* Never embed raw unescaped token syntax inside list items that may break Markdown parsers or renderers.
* Tabular references must use standard GitHub Flavored Markdown (GFM) pipe-table formatting.
* Avoid narrative padding or conversational intros; lead directly with technical requirements and instructions.

## 5. Automated Documentation Preparation

Documentation authored under this standard is structured to support automated extraction and validation:

* **Docstring Harvesting:** Code documentation should be cleanly parseable by docstring engines (`mkdocstrings`, `sphinx.ext.napoleon`) without preprocessing.
* **CLI Help Synchronicity:** Option descriptions and argument names in Markdown user guides must match the in-code `argparse` help strings exactly.
* **Introspection Mixin Compatibility:** Classes inheriting runtime discovery mixins must keep public member docstrings compliant with Section 2 to ensure terminal `.help()` calls produce properly formatted output.