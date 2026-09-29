<!--
Name: MIP-Topic-Miplet-Protocol.md
Path: prompts/topics/MIP-Topic-Miplet-Protocol.md
-->
# Topic Specification: Miplet Protocol & Baseline Synthesis Lifecycle
<!-- Version: 1.0.1 -->
<!-- Operational Directive: Ingest this topic specification as a modular overlay extending the active MIP baseline. Do not execute or rewrite without explicit operator command. Confirm processing and state any conflicts. -->

## 1. Operational Intent
Miplets are atomic, versioned micro-patches used to stage incremental updates to system prompts (`MIP-Core.md` or topic specifications) without mutating active baseline instructions mid-workflow[cite: 11].

---

## 2. Naming & Counter Reset Lifecycle

### Monotonic Increment Per Baseline
* Miplet counters **strictly reset to `001` upon every core baseline increment** (e.g., when transitioning from `v1.0.7` to `v1.0.8`, the first patch targeting `v1.0.8` is `miplet-001-...md`)[cite: 11].
* Filenames follow the strict kebab-case format[cite: 11]:
```text
miplet-[###]-[kebab-case-topic].md
```
* `[###]`: Three-digit zero-padded integer relative to the target baseline (`001`, `002`, `003`...)[cite: 11].

---

## 3. Mandatory Metadata Header Format
Every miplet must declare its target file, target baseline, and operation type in an HTML comment header placed at the top of the file[cite: 11]:

```text
<!--
Name: miplet-[###]-[kebab-case-topic].md
Path: prompts/core/miplet-[###]-[kebab-case-topic].md
Target Baseline: v1.0.X
Target File: prompts/core/MIP-Core.md
Target Section: Section [X] ([Section Name])
Target Type: [Addition | Modification | Replacement | Deprecation]
-->
```

### Operation Types
* **Addition:** Appends new directives, tools, or architectural definitions to an existing section[cite: 11].
* **Modification:** Updates existing parameter blocks, paths, or operational rules[cite: 11].
* **Replacement:** Replaces an entire subsection, table, or guideline block[cite: 11].
* **Deprecation:** Flags existing instructions as obsolete for removal during baseline synthesis[cite: 11].

---

## 4. Delivery Format & Core Immutability Guardrail
* **Direct Native File Emission:** Miplets are delivered directly as standalone Markdown files (`prompts/core/miplet-###-[topic].md`)[cite: 6]. Wrapping miplet text inside temporary Python generator emitter scripts (`gtemp/XX_[purpose].py`) is strictly prohibited[cite: 6].
* **Staged Testing Status:** Miplets provided during an active session represent temporary, experimental micro-patches undergoing test evaluation in working session memory[cite: 4].
* **Core Immutability:** Receipt, review, or discussion of miplets must never trigger an automatic rewrite, re-synthesis, or baseline increment of `MIP-Core.md`[cite: 4]. Active instructions remain pinned at their active version until the operator explicitly commands a formal synthesis lifecycle[cite: 4].
* **Discrete Scope:** Each miplet addresses exactly one operational rule, schema update, or architectural component.

---

## 5. Synthesis & Archival Sequence
When the operator explicitly commands a core baseline synthesis:
1. **Pre-Synthesis Snapshot:** The active `MIP-Core.md` and all staging miplets (`prompts/core/miplet-*.md`) are archived together into[cite: 11]:
   `prompts/archive/mip-core-[current-version]/`
2. **Baseline Compilation:** The new `MIP-Core.md` baseline is written, incorporating all staged miplet directives and incrementing the patch version (`v1.0.X` -> `v1.0.Y`)[cite: 11].
3. **Staging Purge:** The staged miplets in `prompts/core/` are unlinked[cite: 11].
4. **Counter Reset:** The next miplet cycle resets to `001` with `<!-- Target Baseline: v1.0.Y -->`[cite: 11].