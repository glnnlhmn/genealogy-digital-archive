<!--
Name: kinship.md
Path: docs/lib/gdadomain/kinship.md
-->

# KinshipEngine Domain Authority

`KinshipEngine` (`tools/lib/gdadomain/src/gdadomain/kinship.py`) serves as the stateless domain authority for relationship mathematics, reciprocal kinship edge resolution, marriage symmetry auditing, and pedigree graph topology.

## 1. Key Invariants & Features
* **Zero Disk I/O & In-Memory Computation:** Operates entirely in memory without reading or writing database files, entity registries, or schema JSON files.
* **Controlled Reference Vocabulary Authority:** Sourced directly from `GDAReferenceManager` with zero external filesystem dependencies.
* **Bi-Directional Sex Normalization:** Seamlessly processes single-character (`M`, `F`, `U`) and full string tokens (`Male`, `Female`), preventing unassigned fallback errors.
* **Ahnentafel Binary Math:** Computes generation distance, parent pairing, and child numbers with exact integer and logarithmic arithmetic in O(1) time.
* **Topological Cycle Detection:** Identifies circular ancestral loops and self-referential links in parent-child directed graphs via DFS recursion tracking.
* **Symmetry Audit Dataclasses:** Returns frozen diagnostic results (`KinshipAuditResult`, `UnionAuditResult`) consumed directly by audit tools such as `gpa.py`.

## 2. Public API Reference

### Reciprocal Role Mapping
```python
from gdadomain.kinship import KinshipEngine

# Inverse parentage
assert KinshipEngine.get_reciprocal_role("FATH") == "CHIL"
assert KinshipEngine.get_reciprocal_role("CHIL", subject_sex="M") == "FATH"
assert KinshipEngine.get_reciprocal_role("CHIL", subject_sex="F") == "MOTH"
assert KinshipEngine.get_reciprocal_role("CHIL", subject_sex=None) == "PARENT"

# Unions and collaterals
assert KinshipEngine.get_reciprocal_role("SPOU") == "SPOU"
assert KinshipEngine.get_reciprocal_role("HUSB", subject_sex="F") == "WIFE"
assert KinshipEngine.get_reciprocal_role("SIBL") == "SIBL"

# Contextual unreciprocated roles return None
assert KinshipEngine.get_reciprocal_role("WITN") is None