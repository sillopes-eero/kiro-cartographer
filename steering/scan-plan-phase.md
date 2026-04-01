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

## Step 3: Plan Subagent Assignments

Run the assignment planner script to deterministically split files into subagent groups. The planner respects both token budget and file count limits.

Pipe the scanner output directly into the planner:

```bash
uv run <POWER_ROOT>/scripts/scan-codebase.py . --format json | uv run <POWER_ROOT>/scripts/plan-assignments.py - --output-reports docs/.cartographer/reports
```

Or if you saved the scanner output to a file:

```bash
uv run <POWER_ROOT>/scripts/plan-assignments.py scanner-output.json --output-reports docs/.cartographer/reports
```

Fallbacks follow the same pattern as the scanner (try `python3`, then `python`).

### Planner Options

| Flag               | Default | Description                                         |
| ------------------ | ------- | --------------------------------------------------- |
| `--max-tokens`     | 80000   | Max tokens per subagent assignment                  |
| `--max-files`      | 40      | Max files per subagent assignment                   |
| `--include-locale` | off     | Include locale/i18n files (excluded by default)     |
| `--output-reports` | off     | Create report skeleton files in the given directory |

### Planner Output

The planner outputs JSON with this structure:

```json
{
  "assignments": [
    {
      "id": 1,
      "modules": ["src"],
      "files": ["src/index.ts", "src/app.ts"],
      "file_count": 2,
      "estimated_tokens": 5400
    }
  ],
  "excluded": ["locales/en.json", "locales/fr.json"],
  "summary": "3 assignments, 45 files, 72,000 tokens, 2 locale files excluded",
  "config": {
    "max_tokens": 80000,
    "max_files": 40,
    "exclude_locale": true
  }
}
```

Parse this JSON and use the `assignments` array directly — each entry is a ready-to-use subagent assignment. Do **not** re-plan or rebalance the assignments; the script output is deterministic and final.

### How the Planner Works

The planner uses a deterministic algorithm:

1. Excludes locale/i18n files by default.
2. Groups files by top-level directory (module).
3. Splits any module that exceeds 80k tokens or 40 files into sub-groups.
4. Merges small modules together (greedy, in sorted order) as long as both limits hold.
5. Guarantees at least one assignment even for tiny codebases.

## Step 4: Split_Mode Decision

Count the number of distinct top-level modules from the planner output (unique values across all assignment `modules` arrays).

- **If more than 5 top-level modules are detected**: Prompt the user to choose whether to enable Split_Mode.

  > This codebase has **N** top-level modules. Would you like to enable Split_Mode?
  >
  > - **Split_Mode ON**: CODEBASE_MAP.md will contain module summaries with links to detailed per-module files under `docs/codebase_map_modules/`.
  > - **Split_Mode OFF**: All detailed analysis will be written inline in a single CODEBASE_MAP.md.

  Wait for the user's response before proceeding.

- **If 5 or fewer top-level modules**: Do not prompt. Split_Mode defaults to **off** (all analysis inline in CODEBASE_MAP.md).

Record the Split_Mode decision for use in the Synthesize & Write phase.

## Step 5: Update Mode Filtering

If the workflow is running in **Update Mode** (set during the Check phase):

Run the planner with `--update-mode` passing the comma-separated list of changed files (directly changed + indirectly affected from the semantic diff):

```bash
uv run <POWER_ROOT>/scripts/scan-codebase.py . --format json | uv run <POWER_ROOT>/scripts/plan-assignments.py - --output-reports docs/.cartographer/reports --update-mode "<file1>,<file2>,..."
```

The planner will:

1. **Not overwrite** any existing report files.
2. Find which existing reports contain the changed files.
3. Generate targeted `subagent_commands` that only re-analyze those specific files within their reports.
4. Report any `orphaned_files` — changed files not found in any existing report (these are new files that need a fresh report).

Use the `update.subagent_commands` from the output (not the top-level `subagent_commands`).

For orphaned files (new files not in any report), create a new report skeleton manually or re-run in full mode.

If the workflow is running in **full mapping mode**, use the regular planner invocation without `--update-mode`.

## Output

At the end of this phase, you should have:

1. **Scanner results**: The parsed JSON with file list, token counts, and skipped files.
2. **Subagent assignments**: A list of assignments, each with an id, file list, module groupings, and estimated token count.
3. **Split_Mode decision**: Whether the output will be split into per-module files.
4. **Mode**: Full mapping or Update Mode (carried forward from the Check phase).

Proceed to the Analyze phase with these results.
