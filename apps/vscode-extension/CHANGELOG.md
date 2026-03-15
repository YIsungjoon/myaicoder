# Changelog

All notable changes to "myAiCoder" will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.1] - 2026-03-15

### Added

- Workspace integration: AI recognizes open files, tabs, and project structure
- [Apply to Editor] button on code blocks with Diff View preview
- Conversation memory within session (persistent AgentEngine)
- Chat preservation when switching sidebar views (restoreMessages)
- Windows compatibility (where, path.normalize, .venv/Scripts)
- --llm-url and --model-name CLI options for remote LLM
- Korean as default response language
- Tool usage priority guide in system prompt
- Windows command guide in system prompt

### Changed

- Chat panel moved to auxiliary sidebar (right side, Copilot-style 3-pane view)
- enableAgentic default changed to true
- Version bump to 1.0.1

## [0.1.0] - 2026-03-14

### Added

- Activity Bar chat panel with WebView-based UI
- MCP protocol integration via stdio transport (9 tools supported)
- Send selection to chat (`Ctrl+Shift+L` / `Cmd+Shift+L`)
- Automatic CLI detection (PATH, virtualenv, manual path)
- Status bar connection status indicator
- Agent mode for multi-step autonomous execution (opt-in)
- Code syntax highlighting with highlight.js
- Markdown rendering with marked
- Configurable LLM server URL and model name
- Process crash auto-restart with reconnection
