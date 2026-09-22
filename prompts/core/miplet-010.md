# MIPLET 010: Profile Schema Sync & Delivery Standard
* **Target Version:** MIP-Core-v1.0.5
* **Target Sections:**
  * `## 0. Versioning Protocol & System Identity`
  * `## 1. Core Principles & Communication Tone` -> `Modular Profile & Topic Integration`

### Changes:
1. Formalize the operator profile target as `data/profiles/glenn_profile.json` (SchemaVersion 1.0.4).
2. Protocol rule: All future miplet patches must be delivered wrapped inside temporary Python scripts (`gtemp/XX_[purpose].py`) for automated file emission into `prompts/core/`.
