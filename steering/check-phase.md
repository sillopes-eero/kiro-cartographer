# Check Phase

Determine whether to run a full codebase mapping or an incremental update.

## Step 1: Look for Existing Map

Check if `docs/CODEBASE_MAP.md` exists in the workspace root.

- **If it does NOT exist** → proceed to full mapping mode. Skip to the Scan phase.
- **If it exists** → read the file and extract its YAML frontmatter, then continue to Step 2.

## Step 2: Parse Frontmatter

Read the YAML frontmatter block (between the opening and closing `---` lines) at the top of `docs/CODEBASE_MAP.md`. Extract these fields:

| Field                | Type    | Description                                |
| -------------------- | ------- | ------------------------------------------ |
| `last_mapped_commit` | string  | Git commit hash from the last mapping run  |
| `last_mapped`        | string  | UTC ISO 8601 timestamp of the last mapping |
| `total_files`        | number  | File count from the last mapping           |
| `total_tokens`       | number  | Token count from the last mapping          |
| `split_mode`         | boolean | Whether per-module files were generated    |

If the frontmatter is missing or cannot be parsed (malformed YAML, no `---` delimiters), treat this as a **full remap** — proceed to the Scan phase in full mapping mode.

## Step 3: Detect Changes

Use the following fallback chain to determine if the codebase has changed since the last mapping. Try each method in order; move to the next only if the current one fails.

### 3a. Git Commit Hash (preferred)

If `last_mapped_commit` is present in the frontmatter:

```bash
git diff --name-only <last_mapped_commit>..HEAD
```

- If the command succeeds and returns **one or more file paths** → changes detected. Proceed to Step 4 with the list of changed files.
- If the command succeeds and returns **no output** → no changes. Proceed to Step 5.
- If the command fails (e.g., `unknown revision`, git not installed, not a git repo) → fall through to **3b**.

### 3b. Git Timestamp Fallback

If `last_mapped_commit` is not present, or if 3a failed, and `last_mapped` timestamp is present:

```bash
git log --oneline --since="<last_mapped>"
```

- If the command succeeds and returns **one or more lines** → changes detected. Proceed to Step 4. Note: this method identifies commits, not individual files. The Scan phase will determine which modules are affected.
- If the command succeeds and returns **no output** → no changes. Proceed to Step 5.
- If the command fails → fall through to **3c**.

### 3c. Scanner Diff Fallback

If both git-based methods fail (git unavailable, not a git repository, etc.):

1. Run the scanner to get the current file list and counts (script is in the Power's installation directory at `<POWER_ROOT>/scripts/scan-codebase.py`):

   ```bash
   uv run <POWER_ROOT>/scripts/scan-codebase.py . --format json
   ```

   (Fall back to `python3 <POWER_ROOT>/scripts/scan-codebase.py . --format json` or `python <POWER_ROOT>/scripts/scan-codebase.py . --format json` if `uv` is not available.)

2. Compare the scanner output against the frontmatter values:
   - Compare `total_files` from the scanner against the frontmatter `total_files`
   - Compare `total_tokens` from the scanner against the frontmatter `total_tokens`
   - Compare the set of file paths from the scanner against the file paths listed in the existing map

3. If file count changed, token count changed significantly, or new/removed files are detected → changes detected. Proceed to Step 4.
4. If everything matches → no changes. Proceed to Step 5.

## Step 4: Enter Update Mode

Changes have been detected. Set the workflow to **Update Mode**:

- Record the list of changed files (from git diff) or changed modules (from git log / scanner diff).

### 4a. Semantic Diff Analysis

The file list from `git diff --name-only` tells you _which_ files changed, but not _what_ changed inside them. A renamed export can break consumers that didn't change in git. To catch ripple effects:

1. Run a content-aware diff for each changed file:

   ```bash
   git diff <last_mapped_commit>..HEAD -- <changed_file>
   ```

2. From the diff output, extract:
   - **Renamed symbols**: Functions, classes, types, or constants that were renamed (old name on `-` lines, new name on `+` lines).
   - **Removed exports**: Symbols that appear on `-` lines but have no corresponding `+` line.
   - **New exports**: Symbols that appear on `+` lines but have no corresponding `-` line.

3. For each renamed or removed symbol, search the codebase for references:

   ```bash
   grep -rl "<old_symbol_name>" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" .
   ```

4. Any file that references a renamed/removed symbol is an **indirectly affected file**. Add its module to the list of modules that need re-analysis, even if the file itself didn't change in git.

5. Record the list of renamed symbols (old name → new name) and removed symbols. Pass this to the Synthesize & Write phase for stale reference scanning in docs.

### 4b. Proceed to Scan Phase

- Proceed to the Scan phase. During the Plan phase, modules containing changed files **and** indirectly affected files will be assigned to subagents for re-analysis.
- If `split_mode` is `true` in the frontmatter, only the affected per-module files under `docs/codebase_map_modules/` will be regenerated, and their corresponding summaries in `CODEBASE_MAP.md` will be refreshed.

### 4c. Protect Existing Reports

In Update Mode, the planner script must **not** overwrite existing report files in `docs/.cartographer/reports/`. Only create new skeleton files for assignments that don't already have a report, or for modules that need re-analysis. Pass `--update-mode` to the planner to enable this behavior (the planner will skip writing skeletons for reports that already exist and aren't in the re-analysis list).

## Step 5: Map Is Current

No changes were detected since the last mapping. Inform the user:

> The codebase map at `docs/CODEBASE_MAP.md` is up to date (last mapped at `<last_mapped>`). No changes detected since commit `<last_mapped_commit>`.

Do not proceed to the Scan phase. The workflow is complete.
