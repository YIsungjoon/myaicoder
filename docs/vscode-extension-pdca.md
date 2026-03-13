# VSCode Extension PDCA Snapshot

## Current Status

- Feature: `vscode-extension`
- Phase: `Act`
- Latest gap analysis result: `93%` match rate
- Architecture compliance: `100%`
- Convention compliance: `100%`

The current implementation in `apps/vscode-extension` is functionally present and aligned with the design at a high level. The remaining work is concentrated in polish, test completeness, and resilience.

## Implemented So Far

- VS Code activity view container and chat webview are wired in `package.json` and `src/extension.ts`.
- MCP connection lifecycle exists in `src/mcp/client.ts`.
- Executable path resolution exists in `src/config.ts`.
- Agentic and non-agentic branching exists in `src/chat/panel.ts`.
- esbuild watch mode is implemented in `esbuild.config.mjs`.
- Unit tests already exist for:
  - `buildServeArgs`
  - partial `ConfigManager` behavior
  - partial `McpClientManager` behavior

## Remaining Gap

The reported `7%` gap still maps cleanly to the current repository state:

1. `apps/vscode-extension/media/icon.png`
   - Referenced by `package.json`
   - File is currently missing
2. `apps/vscode-extension/test/integration/extension.test.ts`
   - Integration test file is missing
3. `resolveExecutablePath()` happy-path unit tests
   - `test/unit/config.test.ts` only covers default/config getters
4. `connect()` happy-path unit tests
   - `test/unit/client.test.ts` does not validate successful connection flow
5. Process crash auto-restart mechanism
   - `src/mcp/client.ts` supports manual reconnect only
   - no automatic restart or crash detection loop exists

## Improvement Items Already Reflected

These items from the gap analysis appear to be addressed in the current codebase:

- graceful fallback when `agentic_task` is unavailable
- user-facing connection and reconnect error messages
- esbuild watch mode using `context(...).watch()`

This item still needs verification or follow-up:

- HTML escaping / XSS hardening in the webview message rendering path
  - server-side webview HTML shell is fine
  - the effective risk depends on `webview/main.js` rendering behavior

## Recommended Next Cycle

Suggested execution order for the next PDCA loop:

1. Add `media/icon.png`
2. Add happy-path tests for `resolveExecutablePath()`
3. Add happy-path tests for `connect()`
4. Add integration test scaffold for extension activation
5. Implement process crash detection and automatic reconnect
6. Re-run gap analysis
7. Generate final report if match rate remains `>= 90%`

## Repeatable Working Method

Use this workflow whenever continuing the extension work:

### Plan

- Confirm the target feature and intended phase
- Translate gap-analysis items into concrete file-level tasks
- Separate:
  - missing artifacts
  - missing tests
  - behavioral gaps

### Design

- Read the implementation files before changing anything:
  - `src/extension.ts`
  - `src/chat/panel.ts`
  - `src/config.ts`
  - `src/mcp/client.ts`
  - `test/unit/*.test.ts`
- Keep changes aligned with existing structure instead of introducing parallel abstractions

### Do

- Prefer closing small, objective gaps first
- Add tests before or with behavior changes when possible
- Treat resilience work separately from UI polish

### Check

- Run extension tests
- Verify packaging references such as icons and contributed views
- Compare remaining gaps to the original analysis instead of relying on memory

### Act

- If match rate is `>= 90%`, report completion
- If below target, iterate only on the unresolved gaps
- Record what was fixed and what remains, so the next cycle starts from facts instead of rediscovery

## Fast Resume Checklist

When resuming later, check these first:

- Does `apps/vscode-extension/media/icon.png` exist?
- Does `apps/vscode-extension/test/integration/extension.test.ts` exist?
- Do unit tests cover success paths for `resolveExecutablePath()` and `connect()`?
- Does the MCP client auto-recover from process exit?
- Is webview rendering escaped against injected HTML content?
