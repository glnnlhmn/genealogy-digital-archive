# Topic Specification: Miplet Protocol & Baseline Synthesis Lifecycle
<!-- Version: 1.0.0 -->
<!-- Location: prompts/topics/MIP-Topic-Miplet-Protocol.md -->

## 1. Operational Intent
Miplets are atomic, versioned micro-patches used to stage incremental updates to system prompts (`MIP-Core.md` or topic specifications) without directly mutating active baseline instructions mid-workflow.

---

## 2. Naming & Counter Reset Lifecycle

### Monotonic Increment Per Baseline
* Miplet counters **strictly reset to `001` upon every core baseline increment** (e.g., when transitioning from `v1.0.6` to `v1.0.7`, the first patch targeting `v1.0.7` is `miplet-001-...md`).
* Filenames follow the strict kebab-case format:
```text
miplet-[###]-[kebab-case-topic].md
```
* `[###]`: Three-digit zero-padded integer relative to current baseline (`001`, `002`, `003`...).

---

## 3. Mandatory Metadata Header Format
Every miplet must declare its target file, target baseline, and operation type in an HTML comment header within the first 10 lines:

```text
# Miplet [###]: [Descriptive Title]
<!-- Target File: prompts/core/MIP-Core.md -->
<!-- Target Baseline: v1.0.X -->
<!-- Target Section: Section [X] ([Section Name]) -->
<!-- Target Type: [Addition | Modification | Replacement | Deprecation] -->
```

### Operation Types
* **Addition:** Appends new directives, tools, or definitions to an existing section.
* **Modification:** Updates existing parameter blocks, paths, or rules.
* **Replacement:** Replaces an entire subsection, table, or guideline block.
* **Deprecation:** Flags existing instructions as obsolete and removes them during synthesis.

---

## 4. Authoring & Tokenization Safeguards
Per Section 2 of MIP-Core, all miplet patch emitters must be delivered wrapped inside temporary Python scripts under `gtemp/`:
1. **Tokenized Documentation Generation Protocol:** Emitter scripts must represent nested code fences and markdown blocks using intermediate string tokens (````python`, ````powershell`, ````text`) to avoid Python triple-quote crashes.
2. **Context-Free Directives:** Present exact replacement text or additions rather than conversational summaries.
3. **Discrete Scope:** Each miplet addresses exactly one operational rule or architecture component.

---

## 5. Synthesis & Archival Sequence
When a core baseline synthesis is triggered:
1. **Pre-Synthesis Snapshot:** Active `MIP-Core.md` and all staging miplets (`prompts/core/miplet-*.md`) are archived together into:
   `prompts/archive/mip-core-[current-version]/`
2. **Baseline Compilation:** The new `MIP-Core.md` baseline is written, incorporating all staged miplet directives and incrementing the version string (`v1.0.X` -> `v1.0.Y`).
3. **Staging Purge:** The staged miplets in `prompts/core/` are unlinked.
4. **Counter Reset:** Any future miplets created begin at `001` with `<!-- Target Baseline: v1.0.Y -->`.
