# Analyze Phase

Two-pass analysis with disk-persisted reports for resilience. Subagent reports are written to `docs/.cartographer/reports/` so progress is never lost if a subagent crashes.

## Principles

- The orchestrating agent **never reads codebase files directly**. All file reading is delegated to subagents.
- All subagents for this phase are spawned **in a single turn** so they execute in parallel.
- Do **not** specify a model name — Kiro handles model selection automatically.
- Even for small codebases (under 100,000 tokens), at least one subagent must be used.
- Each subagent **writes its report to disk** before returning. This ensures completed work survives if other subagents fail.
- Skip locale/i18n files (e.g., files under `locales/`, `i18n/`, `translations/`, or `_locales/` directories, and files like `*.po`, `*.mo`, `*.xliff`). These contain repeated translated strings across languages and don't provide architectural insight.

## Report Directory

The planner script (run during the Scan & Plan phase with `--output-reports`) has already created report skeleton files at `docs/.cartographer/reports/<id>.md`. Each skeleton contains:

- A file checklist with checkboxes for tracking progress
- Pre-filled module headers and file path sections
- Empty fields for the subagent to fill in (Purpose, Exports, Imports, Patterns, Gotchas)

Verify the skeletons exist:

```bash
ls docs/.cartographer/reports/
```

The subagent's job is to read the assigned files, then **overwrite** its report skeleton with the completed analysis and "check" the file checkbox.

## Pass 1: Raw File Summaries (Lightweight)

The first pass is intentionally lightweight — subagents read files and produce concise per-file summaries. This minimizes context pressure and reduces the chance of crashes.

### Step 1a: Build Pass 1 Prompts

For each subagent assignment, construct a prompt using this template:

```
You are scanning part of a codebase to produce concise file summaries. Read every file listed below and write a brief summary for each.

## Files to Scan

<for each file in the assignment>
- <file_path>
</for each>

## Instructions

For **each file**, produce a concise but substantive summary:

- **Purpose**: One or two sentences describing what the file does and its role in the module.
- **Exports**: Key functions, classes, types with brief descriptions (e.g., `createUser (async, takes UserInput, returns User), UserSchema (Zod validation)`).
- **Imports**: Notable dependencies with brief context (e.g., `express (routing), ./db (database connection), ../utils/logger (structured logging)`).
- **Patterns**: Design patterns with one-line explanation (e.g., `factory — creates service instances based on config`).
- **Gotchas**: One or two sentences about non-obvious behavior, edge cases, or implicit assumptions. Write "None" if nothing stands out.

Keep each file summary to **5–8 lines**. Be concise but capture enough detail that someone who hasn't read the source can understand what the file does and how it connects to others.

After all file summaries, add a brief Module Connections block:

- Entry points: <list of entry point files>
- Key data flows: <one sentence>
- Config dependencies: <list or "None">

## CRITICAL: Write Report to Disk

After completing your analysis, you MUST write the full report to disk using the file write tool:

**File path**: `docs/.cartographer/reports/<ASSIGNMENT_ID>.md`

Write the report in this exact format:

## Module: <module_name>

### <file_path>
- **Purpose**: <one or two sentences>
- **Exports**: <names with brief descriptions>
- **Imports**: <names with brief context>
- **Patterns**: <pattern with one-line explanation>
- **Gotchas**: <one or two sentences, or "None">

(Repeat for each file.)

### Module Connections
- Entry points: <list>
- Key data flows: <one sentence>
- Config dependencies: <list or "None">

Writing the file to disk is the most important step. Even if you cannot analyze every file, write what you have.
```

### Step 1b: Spawn All Pass 1 Subagents

Use `invokeSubAgent` to spawn every subagent **in a single turn**:

```
invokeSubAgent(
  name: "general-task-execution",
  prompt: "<filled-in Pass 1 prompt>",
  explanation: "Pass 1: Scan files for modules: <module names> (<estimated_tokens> tokens), write report to docs/.cartographer/reports/<id>.md",
  contextFiles: [{"path": "<file_path>"}, {"path": "<file_path>"}, ...]
)
```

All four parameters are **required**:

- `name`: Always `"general-task-execution"`.
- `prompt`: The filled-in Pass 1 template with the assignment ID baked into the write path.
- `explanation`: Brief description including the assignment ID and modules. **This parameter is required and must not be omitted.**
- `contextFiles`: Array of `{"path": "<file>"}` objects for every file in the assignment.

### Step 1c: Verify Pass 1 Reports

After all subagents return, check which report files were written to disk:

```bash
ls docs/.cartographer/reports/
```

- For each assignment, verify `docs/.cartographer/reports/<id>.md` exists and is non-empty.
- If a report is missing, that subagent failed. Record the failed assignment for retry.

### Step 1d: Retry Failed Assignments

If any reports are missing:

1. Re-spawn subagents **only for the failed assignments** using the same prompts.
2. Check again after retry.
3. If a subagent fails twice, log the gap and move on — the Synthesize phase will note incomplete coverage.

## Pass 2: Cross-Cutting Analysis (Enrichment)

The second pass reads the file summaries from disk and adds what individual subagents couldn't see: cross-file relationships, cross-module dependencies, and architectural narratives. It does **not** re-describe individual files — those summaries from Pass 1 are already substantive enough.

### Step 2a: Read All Pass 1 Reports

Read all report files from `docs/.cartographer/reports/`:

```bash
cat docs/.cartographer/reports/*.md
```

Or read each file individually. These are the per-file summaries from Pass 1.

### Step 2b: Enrich Each Module

For each module, **append** (do not replace) cross-cutting analysis:

1. **Module narrative**: A paragraph describing the module's overall role in the system and how its files work together.
2. **Internal data flow**: How data moves between files within the module (what calls what, shared state, event chains).
3. **Cross-module dependencies**: What this module imports from other modules, and what other modules depend on it. Use the import/export info from Pass 1 to trace these connections.
4. **Architectural patterns**: Patterns that span multiple files (e.g., a middleware chain, plugin system, layered architecture).
5. **Module-level gotchas**: Aggregate warnings that emerge from combining individual file gotchas.

### Step 2c: Write Enriched Reports

Overwrite each report file, preserving the original per-file summaries and adding the cross-cutting sections:

**File path**: `docs/.cartographer/reports/<assignment_id>.md`

```markdown
## Module: <module_name>

### <file_path>

- **Purpose**: <one or two sentences — preserved from Pass 1>
- **Exports**: <names with brief descriptions — preserved from Pass 1>
- **Imports**: <names with brief context — preserved from Pass 1>
- **Patterns**: <pattern with one-line explanation — preserved from Pass 1>
- **Gotchas**: <one or two sentences — preserved from Pass 1>

(Repeat for each file — keep Pass 1 content as-is.)

### Module Narrative

<Paragraph describing the module's role and how its files collaborate.>

### Module Connections

- Entry points: <list of entry point files with descriptions>
- Internal data flow: <how data moves between files within this module>
- Cross-module dependencies: <what this module imports from / exports to other modules>
- Configuration dependencies: <environment variables, config files, external settings>

### Module-Level Gotchas

<Warnings that emerge from the combination of individual file behaviors.>
```

## Error Handling

- **Subagent fails to write report to disk**: The subagent may have returned output in its response even if the file write failed. Check the subagent's response text and manually write it to disk if present.
- **Subagent fails entirely**: Record which assignment failed. Retry once. If it fails again, proceed with available reports and flag the gap.
- **All subagents fail**: Do not proceed to the Synthesize phase. Report the failure to the user and suggest checking file accessibility and permissions.
- **Partial report on disk**: If a report file exists but is incomplete (subagent crashed mid-write), keep what's there and flag the incomplete files for the user.

## Output

At the end of this phase:

1. **Report files on disk**: `docs/.cartographer/reports/<id>.md` for each assignment, containing enriched per-file analysis.
2. **Coverage gaps** (if any): A list of assignments that failed both attempts.

The Synthesize & Write phase reads reports from `docs/.cartographer/reports/` rather than from agent context. This means the orchestrator's context stays clean and the reports survive across sessions.

Proceed to the Synthesize & Write phase.
