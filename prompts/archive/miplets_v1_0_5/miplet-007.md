# MIPLET 007: Miplet Staging & Patch Workflow
* **Target Version:** MIP-Core-v1.0.5
* **Target Section:** `## 0. Versioning Protocol & System Identity`

### Changes:
1. Document the Miplet micro-patch mechanism:
   * Incremental instruction updates are staged as discrete patch notes (`miplet-XXX.md`) in `prompts/core/`.
   * Accumulated miplets are applied in batches during scheduled prompt version increments (`v1.0.X`), eliminating continuous re-generation churn.
