# TOOL PROMPT: Technical Persona Configuration Validator
<!-- Version: 1.0.0 -->

Please confirm your active configuration before we begin by completing this verification checklist. Provide the answers directly without conversational filler:

1. System Identity & Version:
   - What is your active persona name and current prompt version?
   - What is your core role and root anchor path?

2. Workspace & Directory Routing:
   - Where do Read-Only validation and audit scripts live?
   - Where do Read/Write operational and reconciliation scripts live?
   - Where do shared library modules live?
   - What are the rules and naming standards for temporary scripts in gtemp/?
   - Where do runtime execution logs and generated reports/CSVs go?

3. Schema Versions & Contract Alignment:
   - What schemas govern your operations (names, paths, and version/schema versions)?
   - What properties are required versus forbidden on fact assertions (e.g., quay_score vs confidence_score)?

4. Operational Workflows & Responsibilities:
   - Describe your specific workflows (e.g., Fact Lifecycle Gated Pipeline, Vital Date Synchronization, Codebase Promotion).
   - What is your exact policy on date conservatism ("Option B")?
   - What are your execution safeguards (headers, CLI flags, UTF-8, pre-execution backups)?

5. Required Resources & Missing Resource Protocol:
   - What primary datasets/registries do you depend on (e.g., people.json, facts.json)?
   - Are all required data files and schemas present in your active context right now?
   - If a required file or registry is missing or not yet loaded, what is your mandatory protocol before taking any action?

6. Guardrails & Immutability:
   - What is your policy on modifying active system prompt files on disk?
   - What are your communication rules regarding directness, conversational filler, and parroting context?
