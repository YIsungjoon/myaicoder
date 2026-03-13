"""Tests for MCP config loading."""

import json

from myaicoder.mcp.config import MCPConfig


class TestMCPConfig:
    def test_load_empty(self, tmp_path, monkeypatch):
        """No .mcp.json → empty config."""
        monkeypatch.chdir(tmp_path)
        cfg = MCPConfig.load()
        assert len(cfg.servers) == 0

    def test_load_claude_code_format(self, tmp_path, monkeypatch):
        """Load Claude Code .mcp.json format."""
        monkeypatch.chdir(tmp_path)
        mcp_json = {
            "mcpServers": {
                "github": {
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_TOKEN": "test-token"},
                },
                "remote": {
                    "transport": "http",
                    "url": "https://mcp.example.com/sse",
                },
            }
        }
        (tmp_path / ".mcp.json").write_text(json.dumps(mcp_json))

        cfg = MCPConfig.load()
        assert len(cfg.servers) == 2

        github = cfg.servers["github"]
        assert github.transport == "stdio"
        assert github.command == "npx"
        assert github.args == ["-y", "@modelcontextprotocol/server-github"]
        assert github.env == {"GITHUB_TOKEN": "test-token"}

        remote = cfg.servers["remote"]
        assert remote.transport == "http"
        assert remote.url == "https://mcp.example.com/sse"

    def test_load_explicit_path(self, tmp_path):
        """Load from explicit path."""
        cfg_file = tmp_path / "custom.json"
        cfg_file.write_text(json.dumps({
            "mcpServers": {
                "test": {
                    "transport": "stdio",
                    "command": "echo",
                    "args": ["hello"],
                }
            }
        }))
        cfg = MCPConfig.load(str(cfg_file))
        assert "test" in cfg.servers

    def test_env_variable_resolution(self, tmp_path, monkeypatch):
        """Resolve ${VAR} references in env."""
        monkeypatch.setenv("MY_SECRET", "resolved-value")
        cfg_file = tmp_path / "mcp.json"
        cfg_file.write_text(json.dumps({
            "mcpServers": {
                "svc": {
                    "transport": "stdio",
                    "command": "test",
                    "env": {"TOKEN": "${MY_SECRET}"},
                }
            }
        }))
        cfg = MCPConfig.load(str(cfg_file))
        assert cfg.servers["svc"].env["TOKEN"] == "resolved-value"
