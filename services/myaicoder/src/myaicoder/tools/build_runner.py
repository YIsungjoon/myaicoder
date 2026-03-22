"""Backward compatibility shim — imports from myaicoder.tools.external.build_runner."""

from myaicoder.tools.external.build_runner import (
    BuildRunnerTool,
    _extract_summary,
    _parse_errors,
)

__all__ = ["BuildRunnerTool", "_extract_summary", "_parse_errors"]
