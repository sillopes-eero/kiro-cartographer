# Requirements Document

## Introduction

Convert the existing Cartographer Claude Code plugin into a Kiro Power. Cartographer maps and documents codebases of any size by orchestrating parallel AI subagents. The conversion must preserve the core scanning, parallel analysis, and synthesis workflow while adapting all Claude-specific concepts (plugin metadata, SKILL.md, CLAUDE.md references, Task tool, model-specific instructions) to Kiro's Power architecture (POWER.md, steering files, subagent invocation via invokeSubAgent, Kiro-native conventions).

## Glossary

- **Power**: A Kiro extension unit consisting of a POWER.md file, optional steering files, and optional MCP servers that provides guided workflows and capabilities to Kiro users
- **POWER.md**: The main descriptor file for a Kiro Power, analogous to SKILL.md in Claude Code plugins, containing metadata and workflow instructions
- **Steering_File**: A markdown file within a Kiro Power that provides guided workflow instructions for specific phases or tasks
- **Scanner**: The Python script (scan-codebase.py) that recursively scans a directory tree, respects .gitignore, and counts tokens per file using tiktoken
- **Codebase_Map**: The generated documentation output, consisting of docs/CODEBASE_MAP.md as the index file with architecture overview and module summaries. When split mode is active, per-module markdown files are placed under docs/codebase_map_modules/
- **Split_Mode**: An optional output mode where the Codebase_Map index links to separate per-module files under docs/codebase_map_modules/. Offered to the user when more than 5 top-level modules are detected
- **Subagent**: A parallel AI worker spawned by Kiro's invokeSubAgent tool to read and analyze a group of files
- **Token_Budget**: The maximum number of tokens assigned to a single subagent for analysis, used to balance workload across parallel agents
- **Update_Mode**: A workflow mode where only changed modules are re-analyzed and merged with the existing Codebase_Map

## Requirements

### Requirement 1: Power Metadata and Structure

**User Story:** As a Kiro user, I want the Cartographer Power to follow Kiro's Power structure conventions, so that Kiro can discover, load, and present the Power correctly.

#### Acceptance Criteria

1. THE Power SHALL include a POWER.md file at the root of the Power directory containing the Power name, description, author, version, trigger phrases, and workflow overview
2. THE Power SHALL include steering files that guide the codebase mapping workflow through its distinct phases (scan, plan, analyze, synthesize, write)
3. THE Power SHALL preserve the scan-codebase.py script in a scripts/ subdirectory relative to the Power root
4. THE Power SHALL NOT contain any references to Claude Code plugin metadata formats (plugin.json, marketplace.json, .claude-plugin directory structure)

### Requirement 2: Scanner Script Preservation

**User Story:** As a developer, I want the Python scanner script to work unchanged within the Kiro Power, so that codebase scanning remains accurate and reliable.

#### Acceptance Criteria

1. THE Scanner SHALL be preserved as a Python script that recursively scans a directory tree, respects .gitignore patterns, and counts tokens per file using tiktoken
2. THE Scanner SHALL support JSON, tree, and compact output formats via the --format argument
3. THE Scanner SHALL skip binary files, files over 1MB, and files exceeding the configurable max-token threshold (default 50,000 tokens)
4. THE Scanner SHALL use UV inline script dependencies for automatic tiktoken installation when run with `uv run`
5. WHEN the Scanner is invoked by the Power workflow, THE Power SHALL reference the script path relative to the Power's own root directory instead of using CLAUDE_PLUGIN_ROOT

### Requirement 3: Subagent Orchestration Adaptation

**User Story:** As a Kiro user, I want the Power to use Kiro's native subagent system for parallel codebase analysis, so that the mapping workflow integrates properly with Kiro's architecture.

#### Acceptance Criteria

1. THE Power steering files SHALL instruct Kiro to use the invokeSubAgent tool instead of Claude's Task tool for spawning parallel analysis workers
2. THE Power SHALL NOT reference Claude-specific model names (Sonnet, Opus, Haiku) or model selection parameters in its workflow instructions
3. THE Power SHALL instruct Kiro to spawn all subagents for a given phase in a single turn to enable parallel execution
4. THE Power SHALL define a default Token_Budget of 150,000 tokens per subagent for workload balancing
5. WHEN the total codebase token count is below 100,000 tokens, THE Power SHALL still delegate file reading to a subagent rather than reading files directly in the orchestrating agent

### Requirement 4: Workflow Phase Translation

**User Story:** As a Kiro user, I want the full Cartographer workflow (check, scan, plan, analyze, synthesize, write) to be expressed as Kiro steering instructions, so that the Power guides me through the mapping process step by step.

#### Acceptance Criteria

1. THE Power SHALL define a workflow that checks for an existing docs/CODEBASE_MAP.md and determines whether to run in full mapping mode or Update_Mode
2. WHEN an existing CODEBASE_MAP.md is detected and a last_mapped_commit hash is present, THE Power SHALL use `git diff --name-only <last_mapped_commit>..HEAD` to identify changed files and only re-analyze affected modules
3. IF the CODEBASE_MAP.md exists but no last_mapped_commit hash is present, THE Power SHALL fall back to using the last_mapped timestamp with `git log --oneline --since="<last_mapped>"` to identify changes
4. THE Power SHALL define a planning phase that groups files by directory/module and balances token counts across subagents with a target of 150,000 tokens per subagent
5. WHEN the planning phase identifies more than 5 top-level modules, THE Power SHALL ask the user whether they want to split the output into separate per-module files (Split_Mode) or keep everything in a single CODEBASE_MAP.md
6. THE Power SHALL define an analysis phase where each subagent receives a list of files and instructions to document purpose, exports, imports, patterns, and gotchas for each file
7. THE Power SHALL define a synthesis phase that merges all subagent reports, deduplicates overlapping analysis, identifies cross-cutting concerns, and builds architecture diagrams
8. THE Power SHALL define a writing phase that creates docs/CODEBASE_MAP.md with frontmatter (last_mapped_commit hash, last_mapped timestamp, total_files, total_tokens, split_mode boolean), system overview with Mermaid diagrams, directory structure, module summaries, data flow diagrams, conventions, gotchas, and navigation guide
9. WHEN Split_Mode is active, THE Power SHALL write only a summary of each module in CODEBASE_MAP.md with links to dedicated files, and create a separate markdown file under docs/codebase_map_modules/ for each top-level module (e.g. docs/codebase_map_modules/api.md) containing the detailed analysis including file purposes, exports, imports, dependencies, dependents, patterns, and gotchas
10. WHEN Split_Mode is not active, THE Power SHALL write the full detailed analysis for all modules directly within CODEBASE_MAP.md

### Requirement 5: Output File Adaptation

**User Story:** As a Kiro user, I want the Power to produce documentation files that reference Kiro conventions instead of Claude conventions, so that the output is consistent with my Kiro-based workflow.

#### Acceptance Criteria

1. THE Power SHALL generate docs/CODEBASE_MAP.md (and optionally docs/codebase_map_modules/ when in Split_Mode) with the same content quality as the original Cartographer plugin output
2. THE Power SHALL NOT generate or update a CLAUDE.md file
3. THE Power SHALL NOT generate or update an AGENTS.md file
4. WHEN writing the Codebase_Map, THE Power SHALL obtain the current git HEAD commit hash via `git rev-parse HEAD` and the actual current UTC timestamp via a shell command, storing both in the CODEBASE_MAP.md frontmatter as last_mapped_commit and last_mapped respectively
5. THE Power SHALL attribute the generated map to "Cartographer (Kiro Power)" instead of referencing Claude Code

### Requirement 6: Trigger Phrase Recognition

**User Story:** As a Kiro user, I want to invoke the Cartographer Power using natural language phrases, so that I can start codebase mapping without memorizing specific commands.

#### Acceptance Criteria

1. THE POWER.md SHALL declare trigger phrases including "map this codebase", "cartographer", "create codebase map", "document the architecture", and "understand this codebase"
2. WHEN a user invokes any declared trigger phrase, THE Power SHALL begin the codebase mapping workflow from the check-for-existing-map step

### Requirement 7: Update Mode Preservation

**User Story:** As a developer with an existing codebase map, I want the Power to detect changes and only re-analyze modified modules, so that subsequent mapping runs are faster and more efficient.

#### Acceptance Criteria

1. WHEN docs/CODEBASE_MAP.md exists and contains a last_mapped_commit hash, THE Power SHALL use `git diff --name-only <last_mapped_commit>..HEAD` to identify changed files since the last mapping
2. IF the Codebase_Map contains a last_mapped timestamp but no last_mapped_commit hash, THE Power SHALL fall back to using `git log --oneline --since="<last_mapped>"` to identify changes
3. IF git is not available, THEN THE Power SHALL fall back to running the Scanner and comparing file paths and counts against the existing map
4. WHEN changed modules are identified, THE Power SHALL spawn subagents only for those modules and update only the affected sections of CODEBASE_MAP.md (or regenerate only the affected per-module files under docs/codebase_map_modules/ when in Split_Mode), leaving unchanged content intact
5. THE Power SHALL update both the last_mapped_commit hash and last_mapped timestamp in the CODEBASE_MAP.md frontmatter after each successful update
6. WHEN updating in Split_Mode, THE Power SHALL also refresh the module summaries in CODEBASE_MAP.md for any modules whose per-module files were regenerated

### Requirement 8: Error Handling and Troubleshooting

**User Story:** As a developer, I want the Power to handle common failure scenarios gracefully, so that I can resolve issues and complete the mapping process.

#### Acceptance Criteria

1. IF the Scanner fails due to a missing tiktoken dependency, THEN THE Power SHALL provide instructions for installing tiktoken via pip or uv
2. IF Python is not found on the system, THEN THE Power SHALL suggest trying python3, python, or uv run as alternatives
3. IF a subagent fails to analyze its assigned files, THEN THE Power SHALL report which file group failed and suggest re-running the mapping
4. IF the codebase exceeds the capacity of the planned subagents, THEN THE Power SHALL suggest increasing the number of subagents or focusing on specific source directories
