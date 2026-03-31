# Analyze Phase

Spawn subagents in parallel to read and analyze the files assigned during the Plan phase. Each subagent receives a group of files and returns a structured markdown report.

## Principles

- The orchestrating agent **never reads codebase files directly**. All file reading is delegated to subagents.
- All subagents for this phase are spawned **in a single turn** so they execute in parallel.
- Do **not** specify a model name — Kiro handles model selection automatically.
- Even for small codebases (under 100,000 tokens), at least one subagent must be used.

## Step 1: Build Subagent Prompts

For each subagent assignment produced by the Plan phase, construct a prompt using the template below. Fill in the file list and module names from the assignment.

### Prompt Template

```
You are analyzing part of a codebase for documentation purposes. Read and analyze every file listed below.

## Files to Analyze

<for each file in the assignment>
- <file_path>
</for each>

## Instructions

For **each file**, document the following:

1. **Purpose**: A single-line description of what the file does.
2. **Exports**: Key functions, classes, types, or constants exported by the file.
3. **Imports**: Notable dependencies — both internal (other project files) and external (third-party packages).
4. **Patterns**: Design patterns, conventions, or architectural choices used (e.g., factory pattern, middleware chain, singleton, observer).
5. **Gotchas**: Non-obvious behavior, edge cases, implicit assumptions, or anything a developer new to this code should watch out for.

After analyzing all files, also identify:

- **Entry points**: Which files serve as entry points for this module (e.g., index files, main exports, route definitions).
- **Data flow**: How data moves between the files — what calls what, what feeds into what.
- **Configuration dependencies**: Any environment variables, config files, or external settings these files depend on.

## Output Format

Return your analysis as structured markdown using exactly this format:

## Module: <module_name>

### <file_path>
- **Purpose**: <one-line description>
- **Exports**: <key functions, classes, types>
- **Imports**: <notable dependencies>
- **Patterns**: <design patterns, conventions>
- **Gotchas**: <non-obvious behavior, edge cases>

(Repeat the above section for each file.)

### Module Connections
- Entry points: <list of entry point files>
- Data flow: <description of how data moves between files>
- Configuration dependencies: <environment variables, config files, external settings>

If the assignment covers multiple modules, include a separate `## Module: <name>` section for each one, each with its own file analyses and Module Connections block.
```

### Filling in the Template

- Replace `<file_path>` entries with the actual file paths from the assignment's `files` list.
- Replace `<module_name>` with the top-level directory name(s) from the assignment's `directories` field. If the assignment covers multiple modules, instruct the subagent to group its output by module.
- Do not add any model selection parameters to the invocation.
- Skip locale/i18n files (e.g., files under `locales/`, `i18n/`, `translations/`, or `_locales/` directories, and files like `*.po`, `*.mo`, `*.xliff`). These contain repeated translated strings across languages and don't provide architectural insight.

## Step 2: Spawn All Subagents in Parallel

Use the `invokeSubAgent` tool to spawn every subagent **in a single turn**. This means all `invokeSubAgent` calls must appear in the same message so Kiro can execute them concurrently.

For each assignment, invoke a subagent like this:

```
invokeSubAgent(
  name: "general-task-execution",
  prompt: "<filled-in prompt template from Step 1>",
  explanation: "Analyze files for modules: <module names> (<estimated_tokens> tokens)",
  contextFiles: [{"path": "<file_path>"}, {"path": "<file_path>"}, ...]
)
```

All four parameters are **required**:

- `name`: Always `"general-task-execution"` — this gives the subagent access to file reading tools.
- `prompt`: The fully filled-in template from Step 1.
- `explanation`: A brief description of which modules and how many tokens the subagent covers. **This parameter is required and must not be omitted.**
- `contextFiles`: An array of objects with `path` keys for each file the subagent should analyze. This ensures the subagent has access to the files. List every file from the assignment's `files` list.

### Example

If the Plan phase produced three assignments:

| ID  | Modules                   | Files | Est. Tokens |
| --- | ------------------------- | ----- | ----------- |
| 1   | src/api, src/middleware   | 12    | 130,000     |
| 2   | src/components, src/hooks | 18    | 145,000     |
| 3   | lib, tests                | 9     | 85,000      |

Then spawn three `invokeSubAgent` calls in a single turn — one per assignment. Each call uses the filled-in prompt template with that assignment's file list and module names.

## Step 3: Collect Subagent Reports

After all subagents complete, gather their responses. Each subagent returns a markdown report following the format specified in the prompt template.

### Expected Report Structure

Each report contains one or more module sections:

```markdown
## Module: <module_name>

### <file_path>

- **Purpose**: <one-line description>
- **Exports**: <key functions, classes, types>
- **Imports**: <notable dependencies>
- **Patterns**: <design patterns, conventions>
- **Gotchas**: <non-obvious behavior, edge cases>

### Module Connections

- Entry points: <list>
- Data flow: <description>
- Configuration dependencies: <list>
```

### Validation

For each subagent report, verify:

- Every file from the assignment appears in the report with all five analysis fields (Purpose, Exports, Imports, Patterns, Gotchas).
- A Module Connections section is present for each module covered.
- The report uses the expected markdown structure.

If a subagent's report is missing files or sections, note the gaps — the Synthesize phase will need to account for incomplete coverage.

## Error Handling

- **Subagent fails to return a report**: Record which assignment (ID, modules, files) failed. Report the failure to the user and suggest re-running the mapping for the affected modules.
- **Subagent returns partial analysis**: Proceed with what was returned. Flag the missing files in the synthesis phase so the user is aware of gaps.
- **All subagents fail**: Do not proceed to the Synthesize phase. Report the failure to the user and suggest checking file accessibility and permissions.

## Output

At the end of this phase, you should have:

1. **Subagent reports**: One structured markdown report per assignment, covering all analyzed files.
2. **Coverage gaps** (if any): A list of files or modules that were not successfully analyzed.

Proceed to the Synthesize & Write phase with these reports.
