# Scan & Plan Phase

Run the codebase scanner to get a file inventory with token counts, then group files into balanced subagent assignments.

## Step 1: Run the Scanner

The scanner script is bundled with this Power at `scripts/scan-codebase.py` relative to the Power's installation directory — **not** the user's project directory. In all commands below, `<POWER_ROOT>` refers to the directory containing POWER.md.

Execute the scanner to produce a JSON inventory of the **user's project** (current working directory). Try each command in order until one succeeds:

1. **Preferred** (auto-installs tiktoken via UV inline dependencies):

   ```bash
   uv run <POWER_ROOT>/scripts/scan-codebase.py . --format json
   ```

2. **Fallback — python3**:

   ```bash
   python3 <POWER_ROOT>/scripts/scan-codebase.py . --format json
   ```

3. **Fallback — python**:

   ```bash
   python <POWER_ROOT>/scripts/scan-codebase.py . --format json
   ```

The `.` argument scans the user's current working directory. The script path must resolve to the Power's installation directory, not the user's project.

### Locale / i18n Files

Locale and internationalization files (e.g., `locales/`, `i18n/`, `translations/`, `*.po`, `*.mo`, `*.xliff`, `messages.json` under `_locales/`) contain repeated strings across languages and add significant token count without meaningful architectural insight. When planning subagent assignments:

- Exclude locale/i18n files from subagent assignments by default.
- Do not count their tokens toward module budgets.
- List them as skipped in the scanner results summary shown to the user.
- If the user explicitly asks to include them, respect that preference.

### Error Handling

- **tiktoken not installed**: If the scanner exits with an error mentioning "tiktoken", suggest the user install it with `pip install tiktoken`, or use the `uv run` invocation which handles installation automatically.
- **Python not found**: If the shell reports "command not found", try the next fallback in the list above. If all three fail, inform the user that Python is required and suggest installing it.
- **Other scanner failures**: Report the error output to the user and suggest verifying the target path exists and is accessible.

## Step 2: Parse Scanner Output

The scanner produces JSON on stdout with this structure:

```json
{
  "root": "<absolute path>",
  "files": [
    { "path": "<relative path>", "tokens": <number>, "size_bytes": <number> }
  ],
  "directories": ["<relative directory paths>"],
  "total_tokens": <number>,
  "total_files": <number>,
  "skipped": [
    { "path": "<relative path>", "reason": "<reason string>" }
  ]
}
```

Parse the JSON output and extract:

- The `files` array — these are the files to assign to subagents.
- The `total_tokens` and `total_files` counts — these go into the final CODEBASE_MAP.md frontmatter.
- The `skipped` array — log any skipped files for the user's awareness but do not assign them to subagents.

## Step 3: Group Files by Module

Group the files from the scanner output by their **top-level directory** (the first path segment). Each top-level directory represents a module.

For example, given these file paths:

```
src/index.ts          → module: src
src/utils/helpers.ts  → module: src
lib/parser.ts         → module: lib
docs/README.md        → module: docs
```

Files at the repository root (no directory prefix) are grouped into a virtual `<root>` module.

For each module, calculate the **module token total** by summing the `tokens` value of all files in that module.

## Step 4: Balance Token Budgets

Target **150,000 tokens per subagent**. Build subagent assignments using these rules:

### 4a. Split Large Modules

If a single module's total tokens exceed 150,000:

- Split the module's files into sub-groups, each targeting ≤150,000 tokens.
- Keep files from the same subdirectory together when possible.
- Each sub-group becomes a separate subagent assignment.

### 4b. Merge Small Modules

If a module's total tokens are well below 150,000:

- Combine it with other small modules into a single subagent assignment, as long as the combined total stays within the 150,000 token budget.
- Prefer merging modules that are logically related (adjacent in the directory tree) when possible.

### 4c. Small Codebase Handling

Even if the entire codebase is under 100,000 tokens, **always create at least one subagent assignment**. The orchestrating agent must never read codebase files directly — file reading is always delegated to subagents.

### 4d. Assignment Structure

Each subagent assignment should include:

| Field              | Description                                    |
| ------------------ | ---------------------------------------------- |
| `id`               | Sequential subagent number (1, 2, 3, …)        |
| `files`            | List of file paths to read and analyze         |
| `directories`      | Top-level modules covered by this assignment   |
| `estimated_tokens` | Sum of token counts for all files in the group |

### Validation

After building all assignments, verify:

- Every non-skipped file from the scanner output appears in **exactly one** assignment.
- No single assignment exceeds 150,000 estimated tokens.

## Step 5: Split_Mode Decision

Count the number of distinct top-level modules (directories) identified in Step 3.

- **If more than 5 top-level modules are detected**: Prompt the user to choose whether to enable Split_Mode.

  > This codebase has **N** top-level modules. Would you like to enable Split_Mode?
  >
  > - **Split_Mode ON**: CODEBASE_MAP.md will contain module summaries with links to detailed per-module files under `docs/codebase_map_modules/`.
  > - **Split_Mode OFF**: All detailed analysis will be written inline in a single CODEBASE_MAP.md.

  Wait for the user's response before proceeding.

- **If 5 or fewer top-level modules**: Do not prompt. Split_Mode defaults to **off** (all analysis inline in CODEBASE_MAP.md).

Record the Split_Mode decision for use in the Synthesize & Write phase.

## Step 6: Update Mode Filtering

If the workflow is running in **Update Mode** (set during the Check phase):

- From the list of changed files identified in the Check phase, determine which modules contain changes.
- Only create subagent assignments for modules that have at least one changed file.
- Unchanged modules will not be re-analyzed — their existing sections in CODEBASE_MAP.md (or their per-module files in Split_Mode) will be preserved as-is.

If the workflow is running in **full mapping mode**, assign all modules to subagents.

## Output

At the end of this phase, you should have:

1. **Scanner results**: The parsed JSON with file list, token counts, and skipped files.
2. **Subagent assignments**: A list of assignments, each with an id, file list, module groupings, and estimated token count.
3. **Split_Mode decision**: Whether the output will be split into per-module files.
4. **Mode**: Full mapping or Update Mode (carried forward from the Check phase).

Proceed to the Analyze phase with these results.
