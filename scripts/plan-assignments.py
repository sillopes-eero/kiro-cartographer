#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Subagent Assignment Planner for Cartographer

Takes scanner JSON output (from scan-codebase.py) and produces deterministic
subagent assignments, respecting both token budget and file count limits.

Usage:
    uv run scripts/plan-assignments.py <scanner-output.json>
    uv run scripts/plan-assignments.py <scanner-output.json> --max-tokens 80000 --max-files 40
    cat scanner-output.json | uv run scripts/plan-assignments.py -

Output: JSON array of assignments to stdout.
"""

import argparse
import json
import sys
from pathlib import PurePosixPath


# Directories/files commonly used for locale/i18n that should be excluded
LOCALE_DIRS = {"locales", "locale", "i18n", "translations", "_locales", "l10n"}
LOCALE_EXTENSIONS = {".po", ".mo", ".xliff", ".xlf", ".pot"}


def is_locale_file(path: str) -> bool:
    """Check if a file path is a locale/i18n file."""
    parts = PurePosixPath(path).parts
    for part in parts:
        if part.lower() in LOCALE_DIRS:
            return True
    ext = PurePosixPath(path).suffix.lower()
    return ext in LOCALE_EXTENSIONS


def get_top_level_module(path: str) -> str:
    """Extract the top-level directory as the module name."""
    parts = PurePosixPath(path).parts
    if len(parts) <= 1:
        return "<root>"
    return parts[0]


def split_file_list(files: list[dict], max_tokens: int, max_files: int) -> list[list[dict]]:
    """
    Split a list of files into groups that respect both limits.
    Uses a simple greedy bin-packing: add files to the current group
    until either limit is hit, then start a new group.
    """
    if not files:
        return []

    groups: list[list[dict]] = []
    current_group: list[dict] = []
    current_tokens = 0

    for f in files:
        file_tokens = f.get("tokens", 0)

        # If adding this file would exceed either limit, start a new group
        # (unless the current group is empty — always add at least one file)
        if current_group and (
            current_tokens + file_tokens > max_tokens
            or len(current_group) >= max_files
        ):
            groups.append(current_group)
            current_group = []
            current_tokens = 0

        current_group.append(f)
        current_tokens += file_tokens

    if current_group:
        groups.append(current_group)

    return groups


def plan_assignments(
    scan_result: dict,
    max_tokens: int = 80_000,
    max_files: int = 40,
    exclude_locale: bool = True,
) -> dict:
    """
    Produce deterministic subagent assignments from scanner output.

    Returns a dict with:
    - assignments: list of assignment objects
    - excluded: list of excluded file paths (locale, etc.)
    - summary: human-readable summary
    """
    all_files = scan_result.get("files", [])

    # Separate locale files
    excluded = []
    included = []
    for f in all_files:
        if exclude_locale and is_locale_file(f["path"]):
            excluded.append(f["path"])
        else:
            included.append(f)

    # Group files by top-level module, preserving scanner order within each module
    modules: dict[str, list[dict]] = {}
    for f in included:
        mod = get_top_level_module(f["path"])
        if mod not in modules:
            modules[mod] = []
        modules[mod].append(f)

    # Build assignments: split each module that exceeds limits,
    # then merge small modules together
    raw_groups: list[tuple[list[str], list[dict]]] = []  # (module_names, files)

    for mod_name in sorted(modules.keys()):
        mod_files = modules[mod_name]
        mod_tokens = sum(f.get("tokens", 0) for f in mod_files)

        if mod_tokens > max_tokens or len(mod_files) > max_files:
            # Split this module into sub-groups
            sub_groups = split_file_list(mod_files, max_tokens, max_files)
            for sg in sub_groups:
                raw_groups.append(([mod_name], sg))
        else:
            raw_groups.append(([mod_name], mod_files))

    # Merge small groups together (greedy, in order)
    merged: list[tuple[list[str], list[dict]]] = []
    current_mods: list[str] = []
    current_files: list[dict] = []
    current_tokens = 0

    for mods, files in raw_groups:
        group_tokens = sum(f.get("tokens", 0) for f in files)
        group_file_count = len(files)

        can_merge = (
            current_files
            and current_tokens + group_tokens <= max_tokens
            and len(current_files) + group_file_count <= max_files
        )

        if can_merge:
            current_mods.extend(m for m in mods if m not in current_mods)
            current_files.extend(files)
            current_tokens += group_tokens
        else:
            if current_files:
                merged.append((current_mods, current_files))
            current_mods = list(mods)
            current_files = list(files)
            current_tokens = group_tokens

    if current_files:
        merged.append((current_mods, current_files))

    # Ensure at least one assignment even for empty/tiny codebases
    if not merged and included:
        merged.append(([get_top_level_module(included[0]["path"])], included))

    # Build final assignment objects
    assignments = []
    for i, (mods, files) in enumerate(merged, start=1):
        assignments.append({
            "id": i,
            "modules": mods,
            "files": [f["path"] for f in files],
            "file_count": len(files),
            "estimated_tokens": sum(f.get("tokens", 0) for f in files),
        })

    total_tokens = sum(a["estimated_tokens"] for a in assignments)
    total_files = sum(a["file_count"] for a in assignments)

    summary = (
        f"{len(assignments)} assignments, "
        f"{total_files} files, "
        f"{total_tokens:,} tokens"
    )
    if excluded:
        summary += f", {len(excluded)} locale files excluded"

    return {
        "assignments": assignments,
        "excluded": excluded,
        "summary": summary,
        "config": {
            "max_tokens": max_tokens,
            "max_files": max_files,
            "exclude_locale": exclude_locale,
        },
    }


def generate_report_skeletons(plan_result: dict, output_dir: str = "docs/.cartographer/reports") -> list[str]:
    """
    Create report skeleton files with checkbox file lists.

    Each report file gets:
    - Module header(s)
    - Checkbox list of files to analyze
    - Placeholder sections for the subagent to fill in

    Returns list of created file paths.
    """
    from pathlib import Path

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    created = []
    for assignment in plan_result["assignments"]:
        aid = assignment["id"]
        modules = assignment["modules"]
        files = assignment["files"]
        tokens = assignment["estimated_tokens"]
        file_count = assignment["file_count"]
        report_path = out / f"{aid}.md"

        lines = [
            f"# Report {aid}",
            f"",
            f"**Modules**: {', '.join(modules)}",
            f"**Files**: {file_count} | **Tokens**: {tokens:,}",
            f"",
            f"## File Checklist",
            f"",
        ]

        # Group files by module for the checklist
        files_by_module: dict[str, list[str]] = {}
        for fp in files:
            mod = get_top_level_module(fp)
            if mod not in files_by_module:
                files_by_module[mod] = []
            files_by_module[mod].append(fp)

        for mod in modules:
            mod_files = files_by_module.get(mod, [])
            if len(modules) > 1:
                lines.append(f"### {mod}")
                lines.append("")
            for fp in mod_files:
                lines.append(f"- [ ] `{fp}`")
            lines.append("")

        # Add placeholder sections for each module
        lines.append("---")
        lines.append("")
        lines.append("## Analysis")
        lines.append("")

        for mod in modules:
            mod_files = files_by_module.get(mod, [])
            lines.append(f"## Module: {mod}")
            lines.append("")
            for fp in mod_files:
                lines.append(f"### {fp}")
                lines.append(f"- **Purpose**: ")
                lines.append(f"- **Exports**: ")
                lines.append(f"- **Imports**: ")
                lines.append(f"- **Patterns**: ")
                lines.append(f"- **Gotchas**: ")
                lines.append("")

            lines.append("### Module Connections")
            lines.append("- Entry points: ")
            lines.append("- Key data flows: ")
            lines.append("- Config dependencies: ")
            lines.append("")

        report_path.write_text("\n".join(lines), encoding="utf-8")
        created.append(str(report_path))

    return created


def build_subagent_prompt(assignment: dict, report_dir: str) -> str:
    """Build the exact prompt string for a subagent."""
    aid = assignment["id"]
    modules = assignment["modules"]
    files = assignment["files"]
    report_path = f"{report_dir}/{aid}.md"

    file_list = "\n".join(f"- {fp}" for fp in files)

    return f"""You are scanning part of a codebase to produce concise file summaries.

A report skeleton already exists at `{report_path}` with a file checklist and empty sections for each file.

## CRITICAL: Work One File at a Time

Process files **one at a time** using this loop:

1. Read the next unchecked file from the checklist
2. Analyze it (5–8 lines total)
3. Use strReplace to fill in that file's empty section in the report
4. Use strReplace to check off that file's checkbox: replace `- [ ]` with `- [x]`
5. Move to the next unchecked file

DO NOT try to write the entire report at once. Each file gets its own small write immediately after reading it.

## Files to Analyze (in order)

{file_list}

## Per-File Analysis Format

For each file, fill in the empty fields in the report skeleton:

- **Purpose**: One or two sentences describing what the file does and its role in the module.
- **Exports**: Key functions, classes, types with brief descriptions (e.g., `createUser (async, takes UserInput, returns User)`).
- **Imports**: Notable dependencies with brief context (e.g., `express (routing), ./db (database connection)`).
- **Patterns**: Design patterns with one-line explanation (e.g., `factory — creates service instances based on config`). Write "—" if none.
- **Gotchas**: One or two sentences about non-obvious behavior. Write "None" if nothing stands out.

## After All Files

Once every file checkbox is checked, fill in the Module Connections section at the bottom:

- Entry points: <list of entry point files>
- Key data flows: <one sentence>
- Config dependencies: <list or "None">"""


def generate_subagent_commands(plan_result: dict, report_dir: str = "docs/.cartographer/reports") -> list[dict]:
    """
    Generate the exact invokeSubAgent call parameters for each assignment.

    Returns a list of dicts, each with: name, prompt, explanation, contextFiles.
    """
    commands = []
    for assignment in plan_result["assignments"]:
        aid = assignment["id"]
        modules = assignment["modules"]
        files = assignment["files"]
        tokens = assignment["estimated_tokens"]
        report_path = f"{report_dir}/{aid}.md"

        prompt = build_subagent_prompt(assignment, report_dir)

        context_files = [{"path": report_path}]
        context_files.extend({"path": fp} for fp in files)

        commands.append({
            "name": "general-task-execution",
            "prompt": prompt,
            "explanation": f"Pass 1: Analyze {len(files)} files for modules: {', '.join(modules)} ({tokens:,} tokens), fill report at {report_path}",
            "contextFiles": context_files,
        })

    return commands


def main():
    parser = argparse.ArgumentParser(
        description="Plan subagent assignments from scanner output"
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="Path to scanner JSON output, or - for stdin (default: stdin)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=80_000,
        help="Max tokens per subagent assignment (default: 80000)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=40,
        help="Max files per subagent assignment (default: 40)",
    )
    parser.add_argument(
        "--include-locale",
        action="store_true",
        help="Include locale/i18n files (excluded by default)",
    )
    parser.add_argument(
        "--output-reports",
        metavar="DIR",
        default=None,
        help="Create report skeleton files in DIR (e.g., docs/.cartographer/reports)",
    )

    args = parser.parse_args()

    if args.input == "-":
        scan_data = json.load(sys.stdin)
    else:
        with open(args.input, "r", encoding="utf-8") as f:
            scan_data = json.load(f)

    result = plan_assignments(
        scan_data,
        max_tokens=args.max_tokens,
        max_files=args.max_files,
        exclude_locale=not args.include_locale,
    )

    if args.output_reports:
        created = generate_report_skeletons(result, args.output_reports)
        result["report_files"] = created
        result["subagent_commands"] = generate_subagent_commands(result, args.output_reports)
    else:
        result["subagent_commands"] = generate_subagent_commands(result)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
