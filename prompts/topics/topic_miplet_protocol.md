<!--
Name: topic_miplet_protocol.md
Path: prompts/topics/topic_miplet_protocol.md
-->
# Topic Specification: Miplet Protocol & Patch Specifications
<!-- Version: 1.0.3 -->
<!-- Operational Directive: Ingest this topic specification as a modular overlay extending the active MIP baseline. Do not execute or rewrite without explicit operator command. Confirm processing and state any conflicts. -->

## 1. Operational Intent
Miplets are atomic, versioned JSON patch specifications used to stage incremental updates to system instructions (`mip_core.md` or topic specifications) without mutating active baseline instructions mid-workflow.

---

## 2. Naming & Counter Reset Lifecycle

### Monotonic Increment Per Baseline
* Miplet counters reset to 001 upon every core baseline increment (for example, when transitioning to baseline v1.1.0, the first patch targeting v1.1.0 is named `miplet_001_[topic_name].json`).
* Filenames follow the snake_case format: `miplet_[###]_[topic_name].json`.
* The `[###]` token represents a three-digit zero-padded integer relative to the target baseline (`001`, `002`, `003`, etc.).

---

## 3. Mandatory JSON Schema & Structure
Every miplet must be emitted strictly as a standalone JSON file matching the following envelope structure:

```json
{
  "_name": "miplet_001_example_patch.json",
  "_path": "prompts/core/miplet_001_example_patch.json",
  "target_baseline": "v1.1.0",
  "target_file": "prompts/core/mip_core.md",
  "target_section": "Section 2 (Directory Structure)",
  "operation": "addition",
  "description": "Concise summary of the instruction update.",
  "payload": "Markdown payload containing instruction updates..."
}
```

### Envelope Properties
* `_name`: Exact JSON filename including the three-digit counter and snake_case topic slug.
* `_path`: Canonical staging destination path under `prompts/core/`.
* `target_baseline`: Mandatory baseline version targeted by the micro-patch (for example, `v1.1.0`).
* `target_file`: Relative path to the target instruction file being patched.
* `target_section`: Target section header or identifier within the target file.
* `operation`: Operation type governing synthesis application (`addition`, `modification`, `replacement`, `deprecation`).
* `description`: Concise summary explaining the technical justification or scope of the change.
* `payload`: Verbatim Markdown string containing directives, architectural rules, or text replacements to be incorporated during synthesis.

---

## 4. Operation Types
* `addition`: Appends new directives, tools, or architectural definitions to an existing section.
* `modification`: Updates existing parameter blocks, paths, or operational rules.
* `replacement`: Replaces an entire subsection, table, or guideline block.
* `deprecation`: Flags existing instructions as obsolete for removal during baseline synthesis.

---

## 5. Staged Testing Status & Core Immutability Guardrail
* Direct Native File Emission: Miplets must be delivered directly as standalone JSON files (`prompts/core/miplet_[###]_[topic_name].json`).
* Staged Testing Status: Miplets provided during an active session represent temporary, experimental micro-patches undergoing test evaluation in working session memory.
* Core Immutability: Inbound miplets, review turns, or planning discussions must never trigger automatic synthesis, in-place re-emission, or version increments of `mip_core.md`. Active instructions remain pinned at their active version until the operator explicitly commands a formal synthesis lifecycle.
* Discrete Scope: Each miplet addresses exactly one operational rule, schema update, or architectural component.