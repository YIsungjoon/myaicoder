"""Grep tool — search file contents by regex pattern."""

import re
from pathlib import Path

from myaicoder.tools.base import Tool, ToolResult


class GrepTool(Tool):
    @property
    def name(self) -> str:
        return "Grep"

    @property
    def description(self) -> str:
        return (
            "Search file contents using regex patterns. "
            "Returns matching lines with file paths and line numbers. "
            "Supports context lines and output modes (matches/files/count)."
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for.",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory to search in. Defaults to current directory.",
                },
                "glob": {
                    "type": "string",
                    "description": 'File glob filter (e.g., "*.py").',
                },
                "case_insensitive": {
                    "type": "boolean",
                    "description": "Case insensitive search (default: false).",
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Lines of context before/after match (default: 0, max: 5).",
                },
                "output_mode": {
                    "type": "string",
                    "description": "Output mode: 'matches' (default), 'files', 'count'.",
                    "enum": ["matches", "files", "count"],
                },
            },
            "required": ["pattern"],
        }

    async def execute(self, **kwargs) -> ToolResult:
        pattern = kwargs.get("pattern", "")
        search_path = kwargs.get("path", ".")
        file_glob = kwargs.get("glob", None)
        case_insensitive = kwargs.get("case_insensitive", False)
        context_lines = min(kwargs.get("context_lines", 0), 5)
        output_mode = kwargs.get("output_mode", "matches")

        if not pattern:
            return ToolResult(success=False, output="", error="pattern is required")

        try:
            flags = re.IGNORECASE if case_insensitive else 0
            regex = re.compile(pattern, flags)
        except re.error as e:
            return ToolResult(success=False, output="", error=f"Invalid regex: {e}")

        try:
            base = self.validate_path(search_path)
        except ValueError as e:
            return ToolResult(success=False, output="", error=str(e))

        skip_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            ".next", "dist", ".mypy_cache", ".ruff_cache",
        }

        # Collect files to search
        if base.is_file():
            files = [base]
        elif base.is_dir():
            glob_pattern = file_glob or "**/*"
            files = [
                f for f in base.glob(glob_pattern)
                if f.is_file()
                and not any(p in skip_dirs for p in f.relative_to(base).parts)
            ]
        else:
            return ToolResult(
                success=False, output="", error=f"Path not found: {search_path}"
            )

        max_results = 500
        binary_exts = {".png", ".jpg", ".gif", ".ico", ".woff", ".ttf", ".zip", ".gz", ".tar", ".pyc"}

        # ── Output mode: files ──
        if output_mode == "files":
            matched_files = set()
            for filepath in sorted(files):
                if filepath.suffix in binary_exts:
                    continue
                try:
                    text = filepath.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                if regex.search(text):
                    matched_files.add(str(filepath))
                if len(matched_files) >= max_results:
                    break

            if not matched_files:
                return ToolResult(success=True, output="No matches found.")
            return ToolResult(success=True, output="\n".join(sorted(matched_files)))

        # ── Output mode: count ──
        if output_mode == "count":
            file_counts: dict[str, int] = {}
            for filepath in sorted(files):
                if filepath.suffix in binary_exts:
                    continue
                try:
                    text = filepath.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                count = len(regex.findall(text))
                if count > 0:
                    file_counts[str(filepath)] = count

            if not file_counts:
                return ToolResult(success=True, output="No matches found.")
            output = "\n".join(f"{path}: {c}" for path, c in file_counts.items())
            return ToolResult(success=True, output=output)

        # ── Output mode: matches (default) ──
        if context_lines > 0:
            return self._search_with_context(files, regex, context_lines, max_results, binary_exts)

        return self._search_simple(files, regex, max_results, binary_exts)

    def _search_simple(self, files, regex, max_results, binary_exts) -> ToolResult:
        """Simple line-by-line search (backward compatible)."""
        results = []
        for filepath in sorted(files):
            if filepath.suffix in binary_exts:
                continue
            try:
                text = filepath.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            for lineno, line in enumerate(text.splitlines(), 1):
                if regex.search(line):
                    display = line.rstrip()
                    if len(display) > 500:
                        display = display[:500] + "..."
                    results.append(f"{filepath}:{lineno}: {display}")
                    if len(results) >= max_results:
                        break
            if len(results) >= max_results:
                break

        if not results:
            return ToolResult(success=True, output="No matches found.")

        output = "\n".join(results)
        if len(results) >= max_results:
            output += f"\n... (truncated at {max_results} results)"
        return ToolResult(success=True, output=output)

    def _search_with_context(self, files, regex, context_lines, max_results, binary_exts) -> ToolResult:
        """Search with context lines and '--' separators between blocks (FB-C)."""
        all_blocks: list[str] = []
        total_matches = 0

        for filepath in sorted(files):
            if filepath.suffix in binary_exts:
                continue
            try:
                lines = filepath.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                continue

            # Find all matching line numbers
            match_linenos = set()
            for lineno, line in enumerate(lines):
                if regex.search(line):
                    match_linenos.add(lineno)

            if not match_linenos:
                continue

            # Build context ranges
            ranges: list[tuple[int, int, set[int]]] = []
            for lineno in sorted(match_linenos):
                start = max(0, lineno - context_lines)
                end = min(len(lines), lineno + context_lines + 1)
                ranges.append((start, end, {lineno}))

            # Merge overlapping ranges
            merged = _merge_ranges(ranges)

            # Build blocks
            for start, end, matched in merged:
                block_lines = []
                for i in range(start, end):
                    prefix = ">" if i in matched else " "
                    display = lines[i].rstrip()
                    if len(display) > 500:
                        display = display[:500] + "..."
                    block_lines.append(f"{filepath}:{i + 1}:{prefix} {display}")
                all_blocks.append("\n".join(block_lines))
                total_matches += len(matched)

            if total_matches >= max_results:
                break

        if not all_blocks:
            return ToolResult(success=True, output="No matches found.")

        # FB-C: Join blocks with '--' separator
        output = "\n--\n".join(all_blocks)
        if total_matches >= max_results:
            output += f"\n... (truncated at {max_results} results)"
        return ToolResult(success=True, output=output)


def _merge_ranges(ranges: list[tuple[int, int, set[int]]]) -> list[tuple[int, int, set[int]]]:
    """Merge overlapping (start, end, matched_lines) ranges."""
    if not ranges:
        return []

    merged: list[tuple[int, int, set[int]]] = []
    current_start, current_end, current_matched = ranges[0]

    for start, end, matched in ranges[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
            current_matched = current_matched | matched
        else:
            merged.append((current_start, current_end, current_matched))
            current_start, current_end, current_matched = start, end, matched

    merged.append((current_start, current_end, current_matched))
    return merged
