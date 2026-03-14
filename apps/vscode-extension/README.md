# myAiCoder

> AI coding assistant powered by local LLM via MCP

myAiCoder is a VS Code extension that connects to your local LLM server through the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), giving you an AI coding assistant that runs entirely on your machine.

## Features

- **Local LLM Integration** — Connect to any OpenAI-compatible LLM server (llama.cpp, vLLM, etc.)
- **MCP Tool Execution** — 9 built-in tools: file read/write/edit, search (glob/grep), bash, build runner, web fetch, directory listing
- **Activity Bar Chat Panel** — Dedicated chat interface in the VS Code sidebar
- **Send Selection** — Send selected code to chat with `Ctrl+Shift+L` (`Cmd+Shift+L` on macOS)
- **Agent Mode** — Optional multi-step autonomous execution for complex tasks
- **Code Highlighting** — Syntax highlighting in chat responses
- **Auto CLI Detection** — Automatically finds myaicoder CLI in PATH or virtualenv

## Requirements

- **myaicoder CLI** — Install from source (`pip install -e .` in `services/myaicoder/`)
- **Local LLM server** — Any OpenAI-compatible API (default: `http://localhost:8080`)
  - Recommended: [llama.cpp](https://github.com/ggerganov/llama.cpp) with GGUF models
  - Also supports: vLLM, Ollama, or any OpenAI-compatible endpoint

## Quick Start

1. Install the extension
2. Install myaicoder CLI: `pip install -e services/myaicoder/`
3. Start your LLM server (e.g., `llama-server --model your-model.gguf --port 8001`)
4. Start the gateway: `cd services/gateway && uvicorn app.main:create_app --factory --port 8080`
5. Click the myAiCoder icon in the Activity Bar to open the chat panel

## Extension Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `myaicoder.executablePath` | *(auto-detect)* | Path to myaicoder CLI executable |
| `myaicoder.llmUrl` | `http://localhost:8080` | LLM server URL (Gateway endpoint) |
| `myaicoder.modelName` | `qwen3.5-27b` | Model name displayed in status bar |
| `myaicoder.allowBash` | `false` | Allow Bash tool execution (security risk) |
| `myaicoder.maxConcurrent` | `1` | Max concurrent MCP requests |
| `myaicoder.enableAgentic` | `false` | Enable agent mode for multi-step execution |

## Commands

| Command | Keybinding | Description |
|---------|-----------|-------------|
| `myAiCoder: New Chat` | — | Start a new chat session |
| `myAiCoder: Reconnect MCP Server` | — | Reconnect to the MCP server |
| `myAiCoder: Send Selection to Chat` | `Ctrl+Shift+L` | Send selected code to chat |

## Architecture

```
VS Code Extension
    │
    ├─ Chat Panel (WebView)
    │     ├─ Markdown rendering (marked)
    │     └─ Syntax highlighting (highlight.js)
    │
    └─ MCP Client (stdio)
          │
          └─ myaicoder serve (Python subprocess)
                │
                ├─ 9 Built-in Tools
                └─ Gateway → Local LLM Server
```

<!-- NOTE: When adding images to this README, use absolute URLs
     (https://raw.githubusercontent.com/myaicoder/myaicoder/main/apps/vscode-extension/media/...)
     Relative paths break on the VS Code Marketplace web page. -->

## Privacy

myAiCoder runs entirely on your local machine. No data is sent to external servers. Your code and conversations stay on your device.

## License

[MIT](LICENSE)
