<!--
Name: miplet-002-nested-markdown-codefences.md
Path: prompts/core/miplet-002-nested-markdown-codefences.md
Target Baseline: v1.0.8
Target File: prompts/core/MIP-Core.md
Target Section: Section 3 (Operational Protocols & Scripting Safeguards)
Target Type: Addition
-->

### Operational Context & Addition Summary
Prevents Markdown deliverable leakage into the chat stream caused by nested triple-backtick code fences closing outer copy containers prematurely.

---

### Delta Directives

#### Section 3 Addition: Nested Code Fence Outer Container Standard
Add the following directive under Section 3:

* **Nested Code Fence Outer Container Standard:** When emitting native Markdown documents (`.md`), documentation runbooks, or notebook payloads containing embedded internal code blocks (`python`, `powershell`, `json`, `text`), the outer deliverable code fence must strictly use **four backticks** (````markdown ... ````). Internal examples must remain three backticks (```). This prevents the UI parser from prematurely closing the container box and leaking subsequent documentation into the active chat stream.