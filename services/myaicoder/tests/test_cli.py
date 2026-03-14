"""Tests for CLI commands (conversation-persistence feature)."""

from unittest.mock import MagicMock


def test_help_includes_session_commands():
    """T25: /help output includes session commands."""
    from myaicoder.cli import _handle_command

    engine = MagicMock()
    ui = MagicMock()
    ui.console = MagicMock()

    _handle_command("/help", engine, ui)

    # Check that console.print was called with session commands
    call_args = ui.console.print.call_args[0][0]
    assert "/sessions" in call_args
    assert "/new" in call_args
    assert "/load" in call_args
