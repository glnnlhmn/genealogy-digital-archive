<!--
Name: people.md
Path: docs/lib/gdadomain/people.md
-->

# GDAPeople Domain Entity Manager

`GDAPeople` (`tools/lib/gdadomain/src/gdadomain/people.py`) serves as the master entity manager for individual genealogical personas stored in `data/entities/people.json`. It provides auto-minting of `IND-XXXXX` identifiers, display name normalization, bidirectional reciprocal kinship wiring, union pairing, active view filtering, and atomic persistence via the Safe Backup Protocol.

## 1. Key Invariants & Features
* **Zero Schema File Dependency:** Controlled vocabularies (`VALID_SEX`, `VALID_KINSHIP_ROLES`, `VALID_UNION_STATUSES`) and reciprocal pairing rules are embedded in Python code, eliminating runtime JSON schema dependencies.
* **Monotonic Minting:** Sequential monotonic ID allocation (`IND-00001` through `IND-NNNNN`).
* **Display Name Compilation:** Assembles canonical name objects into clean display strings, stripping trailing/internal dots (`J.B.` $\to$ `JB`, `Sr.` $\to$ `Sr`) with fallback to `raw_name` or `"UNKNOWN"`.
* **Graph Reciprocity:** Automatically maintains reciprocal edges across `associated_people` (`FATH`/`MOTH` $\leftrightarrow$ `CHIL`, `SPOU` $\leftrightarrow$ `SPOU`, `SIBL` $\leftrightarrow$ `SIBL`) based on subject sex.
* **Cascading Cleanup:** Deleting a person automatically purges reciprocal pointers across all remaining entities.
* **View Filtering:** Supports dynamic view filtering with fnmatch wildcards (`*Sterling*`), sex filtering, and custom predicates. `len(mgr)` automatically reflects the active filtered count.

## 2. Public API Reference

### Initialization & Context Manager
```python
from gdadomain.people import GDAPeople

# Standalone instance
mgr = GDAPeople()

# Transactional context manager (auto-saves on clean exit)
with GDAPeople() as mgr:
    mgr.add(canonical_name={"given": "Glenn", "surname": "Lehman"}, sex="M")