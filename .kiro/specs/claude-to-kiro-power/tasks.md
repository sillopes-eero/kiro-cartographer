# Implementation Plan: Claude-to-Kiro Power Conversion

## Overview

Convert the Cartographer Claude Code plugin into a Kiro Power by creating the Power directory layout, POWER.md descriptor, four steering files, and copying the scanner script. All Claude-specific references are replaced with Kiro-native equivalents. Tests use Python with Hypothesis for property-based testing and pytest for unit tests.

## Tasks

- [x] 1. Create Power directory structure and POWER.md
  - [x] 1.1 Create the `cartographer-power/` directory layout with `steering/` and `scripts/` subdirectories
    - Create `cartographer-power/`, `cartographer-power/steering/`, `cartographer-power/scripts/`
    - _Requirements: 1.1, 1.2, 1.3_

  - [x] 1.2 Create `cartographer-power/POWER.md` with frontmatter metadata and workflow overview
    - Include YAML frontmatter with name, description, author, version, and trigger phrases
    - Include workflow overview referencing the four steering files and the scanner script
    - Reference `scripts/scan-codebase.py` relative to Power root (no CLAUDE_PLUGIN_ROOT)
    - _Requirements: 1.1, 1.4, 2.5, 6.1, 6.2_

  - [x] 1.3 Copy `plugins/cartographer/skills/cartographer/scripts/scan-codebase.py` to `cartographer-power/scripts/scan-codebase.py`
    - Preserve the script exactly as-is with no modifications
    - _Requirements: 1.3, 2.1, 2.4_

  - [ ]\* 1.4 Write unit tests for Power structure validation
    - Verify POWER.md exists and contains required frontmatter fields (name, description, author, version, triggers)
    - Verify all trigger phrases are present: "map this codebase", "cartographer", "create codebase map", "document the architecture", "understand this codebase"
    - Verify directory layout matches expected structure (POWER.md, steering/, scripts/)
    - _Requirements: 1.1, 6.1_

- [x] 2. Create check-phase steering file
  - [x] 2.1 Create `cartographer-power/steering/check-phase.md`
    - Instructions to check for existing `docs/CODEBASE_MAP.md`
    - Change detection logic: git commit hash → git timestamp → scanner diff fallback chain
    - Determine full mapping mode vs Update_Mode
    - No Claude-specific references (no CLAUDE.md, AGENTS.md, Task tool, model names)
    - _Requirements: 4.1, 4.2, 4.3, 7.1, 7.2, 7.3_

  - [ ]\* 2.2 Write unit tests for change detection flow
    - Test: commit hash present → git diff path
    - Test: timestamp only → git log path
    - Test: no git → scanner diff fallback
    - Test: no frontmatter → full remap
    - _Requirements: 4.2, 4.3, 7.1, 7.2, 7.3_

- [x] 3. Create scan-plan-phase steering file
  - [x] 3.1 Create `cartographer-power/steering/scan-plan-phase.md`
    - Instructions to run scanner via `uv run scripts/scan-codebase.py . --format json` (with python3/python fallbacks)
    - Script path relative to Power root directory
    - Planning phase: group files by directory/module, balance token budgets at 150k per subagent
    - Split_Mode prompt when >5 top-level modules detected
    - Small codebase handling: still use at least one subagent even for <100k tokens
    - _Requirements: 2.2, 2.5, 3.4, 3.5, 4.4, 4.5_

  - [ ]\* 3.2 Write property test for token budget balancing (Property 4)
    - **Property 4: Subagent token budget balancing**
    - Generate random file lists with token counts, verify all assignments ≤150k and every file covered exactly once
    - **Validates: Requirements 4.4**

  - [ ]\* 3.3 Write property test for Split_Mode threshold (Property 5)
    - **Property 5: Split_Mode threshold**
    - Generate scan results with varying module counts (1-20), verify threshold behavior at boundary of 5
    - **Validates: Requirements 4.5**

- [x] 4. Create analyze-phase steering file
  - [x] 4.1 Create `cartographer-power/steering/analyze-phase.md`
    - Subagent prompt template using `invokeSubAgent` (not Claude Task tool)
    - Instructions for each subagent: read assigned files, document purpose, exports, imports, patterns, gotchas
    - Structured markdown output format for subagent reports
    - Spawn all subagents in a single turn for parallel execution
    - No model name specification (Kiro handles model selection)
    - _Requirements: 3.1, 3.2, 3.3, 4.6_

  - [ ]\* 4.2 Write property test for no Claude-specific references (Property 1)
    - **Property 1: No Claude-specific references in Power files**
    - Scan all Power text files for forbidden strings: CLAUDE_PLUGIN_ROOT, plugin.json, marketplace.json, .claude-plugin, CLAUDE.md, AGENTS.md, Task tool, subagent_type, Sonnet, Opus, Haiku, Claude Code
    - Verify invokeSubAgent is used and attribution reads "Cartographer (Kiro Power)"
    - **Validates: Requirements 1.4, 2.5, 3.1, 3.2, 5.2, 5.3, 5.5**

- [x] 5. Checkpoint - Verify Power structure and steering files
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Create synthesize-write-phase steering file
  - [x] 6.1 Create `cartographer-power/steering/synthesize-write-phase.md`
    - Synthesis instructions: merge subagent reports, deduplicate, identify cross-cutting concerns, build Mermaid diagrams
    - Writing instructions for CODEBASE_MAP.md with full frontmatter (last_mapped_commit, last_mapped, total_files, total_tokens, split_mode)
    - File writing strategy: use Python `pathlib.Path.write_text()` via `executeBash` as primary method, bash heredoc as fallback, `fsWrite`/`fsAppend` only for files under ~50 lines
    - Required sections: System Overview, Directory Structure, Module Guide, Data Flow, Conventions, Gotchas, Navigation Guide
    - Split_Mode output: summary in index with links to per-module files under docs/codebase_map_modules/
    - Non-Split_Mode: full detailed analysis inline
    - Attribution line: "Cartographer (Kiro Power)"
    - Update mode: only update affected module sections, refresh summaries for regenerated modules
    - No CLAUDE.md or AGENTS.md updates
    - _Requirements: 4.7, 4.8, 4.9, 4.10, 5.1, 5.2, 5.3, 5.4, 5.5, 7.4, 7.5, 7.6_

  - [ ]\* 6.2 Write property test for CODEBASE_MAP.md completeness (Property 6)
    - **Property 6: CODEBASE_MAP.md completeness**
    - Verify frontmatter contains all required fields and all required sections are present
    - **Validates: Requirements 4.8, 5.4, 7.5**

  - [ ]\* 6.3 Write property test for Split_Mode output correctness (Property 7)
    - **Property 7: Split_Mode output correctness**
    - When split_mode=true: index has summaries with links, per-module files exist with detailed analysis
    - When split_mode=false: full analysis inline, no codebase_map_modules references
    - **Validates: Requirements 4.9, 4.10**

  - [ ]\* 6.4 Write property test for update mode targeting (Property 8)
    - **Property 8: Update mode targets only changed modules**
    - Given existing map + changed file list, verify only affected modules are re-analyzed
    - **Validates: Requirements 7.4**

  - [ ]\* 6.5 Write property test for Split_Mode update summaries (Property 9)
    - **Property 9: Split_Mode update refreshes affected summaries**
    - When a per-module file is regenerated, the corresponding summary in CODEBASE_MAP.md is also refreshed
    - **Validates: Requirements 7.6**

- [x] 7. Create test infrastructure and remaining tests
  - [x] 7.1 Set up test infrastructure with pytest and Hypothesis
    - Create `tests/` directory with `property/` and `unit/` subdirectories
    - Create `tests/conftest.py` with shared fixtures (Power directory path, file readers)
    - _Requirements: (testing infrastructure)_

  - [ ]\* 7.2 Write property test for scanner format output validity (Property 2)
    - **Property 2: Scanner format output validity**
    - Generate random directory trees, run scanner with each format, validate output schema
    - **Validates: Requirements 2.2**

  - [ ]\* 7.3 Write property test for scanner skip rules (Property 3)
    - **Property 3: Scanner skip rules**
    - Generate files with varying sizes/types/token counts, verify correct skip/include classification
    - **Validates: Requirements 2.3**

  - [ ]\* 7.4 Write unit tests for steering file content validation
    - Verify each steering file exists and contains key phase-specific instructions
    - Verify scanner invocation uses relative paths (no CLAUDE_PLUGIN_ROOT)
    - _Requirements: 1.2, 2.5, 3.1_

  - [ ]\* 7.5 Write unit tests for frontmatter parsing and error handling
    - Test valid frontmatter extraction from POWER.md and CODEBASE_MAP.md templates
    - Test missing fields and malformed YAML handling
    - Test error scenario instructions: tiktoken missing, Python not found, subagent failure
    - _Requirements: 5.4, 8.1, 8.2, 8.3, 8.4_

- [x] 8. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The scanner script (scan-codebase.py) is copied as-is with zero modifications
- All property tests use Python with Hypothesis (minimum 100 iterations each)
- Each property test is tagged with `# Feature: claude-to-kiro-power, Property N: <description>`
- Checkpoints ensure incremental validation of the Power structure
