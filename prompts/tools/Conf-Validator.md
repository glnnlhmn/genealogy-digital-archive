# TOOL PROMPT: Unified Domain & Technical Persona Configuration Validator
<!-- Version: 1.0.0 -->

Please confirm your active configuration before we begin by completing this verification checklist. Provide the answers directly without conversational filler:

1. System Identity & Version:
   - What is your active persona name, role, and current prompt version?
   - What is your root anchor directory and core anchor path?

2. Operational Scope, Boundaries & In-Bounds/Out-of-Bounds Rules:
   - Which specific directories under `data/`, `import/`, or `prompts/` do you operate within?
   - What are your structural workspace directories (e.g., Read-Only validation scripts vs. Read/Write operational scripts, shared libraries, temporary `gtemp/` scripts, runtime logs, reports/CSVs)?
   - Confirm your boundaries: Are you permitted to edit schemas, alter system prompts, or write permanent Python tools? What is your policy on modifying active system prompt files on disk?

3. Schema Governance & Contract Alignment:
   - What schema versions govern the files, entities, operations, or outputs you generate or evaluate?
   - What validation rules, formatting standards, and required versus forbidden properties (e.g., `quay_score` vs `confidence_score`) must your outputs adhere to?

4. Specific Workflows & Operational Responsibilities:
   - Describe your exact operational workflows (e.g., Stage 1 atomic factoid extraction, verbatim transcription, GPS genealogical proof arguments, narrative synthesis, Fact Lifecycle Gated Pipeline, Vital Date Synchronization, Codebase Promotion).
   - What are your specific rules and policies for handling conflicting dates, uncorroborated assertions, transcription ambiguities, and date conservatism ("Option B")?
   - What are your mandatory execution safeguards (headers, CLI flags, UTF-8, pre-execution backups)?

5. Required Resources & Missing Resource Protocol:
   - What specific registries, files, or reference profiles do you require to execute your work (e.g., `people.json`, `facts.json`, Glenn-User-Profile, specific source scans)?
   - Which of these required resources are currently loaded in this chat context, and which are missing?
   - What is your mandatory protocol if an essential person, document, schema, or registry is not provided in context?

6. Communication, Tone Standards & Guardrails:
   - What is your required output format, tone, and opening style?
   - What are your communication rules regarding directness, conversational filler, parroting context, and zero-filler verification responses?
