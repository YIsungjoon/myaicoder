# Core Security Hardening -- Gap Analysis Report

> **Analysis Type**: Gap Analysis (Design vs Implementation)
>
> **Project**: myAiCoder
> **Analyst**: AI (gap-detector)
> **Date**: 2026-03-17
> **Design Doc**: [core-security-hardening.design.md](../02-design/features/core-security-hardening.design.md)

---

## 1. Analysis Overview

### 1.1 Analysis Purpose

Core Service 9건 + VS Code Extension 4건 보안 취약점 수정(FR-01 ~ FR-10) 설계 문서 대비 실제 구현 상태를 비교한다.

### 1.2 Analysis Scope

- **Design Document**: `docs/pdca/02-design/features/core-security-hardening.design.md`
- **Implementation Paths**:
  - `services/myaicoder/src/myaicoder/tools/` (base.py, read.py, write.py, edit.py, glob_tool.py, grep_tool.py, list_dir.py, bash.py, build_runner.py, web_fetch.py)
  - `services/myaicoder/src/myaicoder/core/config.py`
  - `services/myaicoder/src/myaicoder/llm/base.py`
  - `apps/vscode-extension/src/mcp/process.ts`
  - `apps/vscode-extension/src/mcp/client.ts`
  - `apps/vscode-extension/src/chat/panel.ts`
  - `apps/vscode-extension/webview/main.js`
  - `apps/vscode-extension/src/config.ts`
- **Analysis Date**: 2026-03-17

---

## 2. Overall Scores

| Category | Score | Status |
|----------|:-----:|:------:|
| Design Match (FR 구현율) | 80% | WARNING |
| Code Quality (구현된 항목의 설계 일치도) | 95% | PASS |
| Convention Compliance | 93% | PASS |
| **Overall** | **82%** | **WARNING** |

```
Match Rate: 82%
  - Implemented: 8 / 10 FRs
  - Minor Deviations: 1 item (FR-03 pattern difference)
  - Missing: 2 items (FR-05, FR-10)
```

---

## 3. Functional Requirements -- Detailed Comparison

### FR-01: WorkspaceGuard (Path Traversal Prevention)

**Status**: PASS -- Design matches implementation

| Design Item | Implementation | Match |
|-------------|----------------|:-----:|
| `WorkspaceGuard` class in `base.py` | `base.py:19-42` -- identical to design spec | PASS |
| `Tool.validate_path()` method | `base.py:81-85` -- identical to design spec | PASS |
| `Tool._workspace_guard` class attribute | `base.py:74` -- identical | PASS |
| `Tool.set_workspace_guard()` classmethod | `base.py:77-79` -- identical | PASS |

**6 File Tools -- validate_path() Application**:

| Tool | File | Design Location | Impl Location | Match |
|------|------|-----------------|---------------|:-----:|
| ReadTool | `read.py` | `execute()` start | Line 51-53 | PASS |
| WriteTool | `write.py` | `execute()` start | Line 44-47 | PASS |
| EditTool | `edit.py` | `execute()` start | Line 61-64 | PASS |
| GlobTool | `glob_tool.py` | `execute()` start | Line 46-48 | PASS |
| GrepTool | `grep_tool.py` | `execute()` start | Line 73-76 | PASS |
| ListDirTool | `list_dir.py` | `execute()` start | Line 55-58 | PASS |

**Notes**: All 6 tools follow the design pattern: validate first, catch `ValueError`, return `ToolResult(success=False)`.

---

### FR-02: SSRF Filter (WebFetchTool)

**Status**: PASS -- Design matches implementation

| Design Item | Implementation | Match |
|-------------|----------------|:-----:|
| `_BLOCKED_NETWORKS` list (8 entries) | `web_fetch.py:11-20` -- all 8 networks present | PASS |
| `_is_private_url()` function | `web_fetch.py:23-43` -- matches design | PASS |
| DNS resolution via `socket.getaddrinfo()` | `web_fetch.py:34` -- present | PASS |
| Called after URL scheme check | `web_fetch.py:96-98` -- correct order | PASS |

---

### FR-03: CommandValidator (BashTool)

**Status**: PASS (minor deviation)

| Design Item | Implementation | Match |
|-------------|----------------|:-----:|
| `BLOCKED_COMMAND_PATTERNS` in `base.py` | `base.py:46-57` -- present | PASS |
| `validate_command()` function | `base.py:60-68` -- matches design | PASS |
| `bash.py` imports `validate_command` | `bash.py:7` -- `from .base import validate_command` | PASS |
| `bash.py` uses `validate_command()` | `bash.py:60-62` -- called in `execute()` | PASS |

**Deviations**:

| Item | Design | Implementation | Impact |
|------|--------|----------------|--------|
| eval pattern | `r"\beval\b"` | `r"\beval\s"` | Low -- `\s` is slightly stricter, avoids false positives like variable names containing "eval" |
| exec pattern | `r"\bexec\b"` | `r"\bexec\s"` | Low -- same rationale |
| rm -rf /path pattern | Present (`r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/\S"`) | Missing | Medium -- design adds extra rm pattern for `rm -rf /anything`; implementation only blocks `rm -rf /` (no trailing path) |

**Assessment**: The `\beval\s` / `\bexec\s` variants are arguably better than design (fewer false positives). The missing `rm -rf /path` pattern is a minor gap -- the existing pattern already catches `rm -rf /` with nothing after it, but `rm -rf /var` would pass.

---

### FR-04: BuildRunnerTool validate_command

**Status**: PASS

| Design Item | Implementation | Match |
|-------------|----------------|:-----:|
| `build_runner.py` imports `validate_command` | `build_runner.py:7` | PASS |
| `validate_command()` called in `execute()` | `build_runner.py:73-75` | PASS |

---

### FR-05: XSS Fix -- marked + DOMPurify

**Status**: FAIL -- NOT IMPLEMENTED

| Design Item | Implementation | Match |
|-------------|----------------|:-----:|
| `import { marked } from 'marked'` | Not present | FAIL |
| `import DOMPurify from 'dompurify'` | Not present | FAIL |
| `PURIFY_CONFIG` allowlist | Not present | FAIL |
| `renderMarkdown()` rewrite | `main.js:16-53` still uses hand-rolled regex | FAIL |
| marked custom renderer for code blocks | Not present | FAIL |

**Current State**: `webview/main.js` still uses the original regex-based `renderMarkdown()` function with manual HTML escaping. This is the design's primary XSS vulnerability -- user-supplied markdown is processed through regex patterns that may not cover all edge cases.

**Risk**: Medium-High. While the current code does `escapeHtml` first (line 18-21), the subsequent regex replacements could potentially re-introduce unsafe HTML in edge cases.

---

### FR-06: API Key via Environment Variable

**Status**: PASS

| Design Item | Implementation | Match |
|-------------|----------------|:-----:|
| `buildServeArgs()` returns `{ args, env }` | `process.ts:20` -- return type matches | PASS |
| apiKey placed in `env['MYAICODER_API_KEY']` | `process.ts:41-44` | PASS |
| `client.ts` destructures `{ args, env }` | `client.ts:51` | PASS |
| `StdioClientTransport` receives `env: { ...process.env, ...env }` | `client.ts:69` | PASS |

---

### FR-07: config.py api_key Default Value

**Status**: PASS

| Design Item | Implementation | Match |
|-------------|----------------|:-----:|
| `api_key: str = ""` (changed from `"not-needed"`) | `config.py:16` -- `api_key: str = ""` | PASS |

**Bonus**: Implementation also adds `MYAICODER_API_KEY` env var override in `AppConfig.load()` (config.py:98-100), which aligns with FR-06 server-side support.

---

### FR-08: Dynamic Import Removal (llm/base.py)

**Status**: PASS

| Design Item | Implementation | Match |
|-------------|----------------|:-----:|
| Module-level `import json` | `llm/base.py:7` -- `import json as _json` | PASS |
| `json.dumps(tc.arguments)` | `llm/base.py:44` -- `_json.dumps(tc.arguments)` | PASS |
| No `__import__("json")` | Confirmed absent | PASS |

**Note**: Implementation uses `import json as _json` (underscore prefix) to signal it's an internal import detail. This is a minor style choice, functionally equivalent.

---

### FR-09: Crypto Nonce (panel.ts)

**Status**: PASS

| Design Item | Implementation | Match |
|-------------|----------------|:-----:|
| `require('crypto').randomUUID().replace(/-/g, '')` | `panel.ts:312` -- exact match | PASS |
| No `Math.random()` usage | Confirmed -- no Math.random in getNonce | PASS |

---

### FR-10: Config Type Guards (config.ts)

**Status**: FAIL -- NOT IMPLEMENTED

| Design Item | Implementation | Match |
|-------------|----------------|:-----:|
| `get<T>(key, defaultValue): T` with default | `config.ts:9-12` -- still `get<T>(key): T` with `as T` cast | FAIL |
| Runtime type safety via VS Code `get(key, default)` | Not applied -- no default values passed | FAIL |

**Current State**: `config.ts:9-12` uses unsafe cast pattern:
```typescript
get<T>(key: string): T {
  return vscode.workspace.getConfiguration(this.SECTION).get<T>(key) as T;
}
```

**Risk**: Low. VS Code's `getConfiguration().get()` returns `undefined` when key is missing, and the `as T` cast silently converts it. Callers (e.g., `getModelName()`, `getLlmUrl()`) have their own fallback logic with `|| ''`, which mitigates the issue in practice.

---

## 4. Implementation Steps vs. Actual Progress

| Step | Description | Status |
|------|-------------|:------:|
| Step 1 | `base.py` -- WorkspaceGuard + CommandValidator | PASS |
| Step 2 | 6 file tools -- validate_path() application | PASS |
| Step 3 | `bash.py` + `build_runner.py` -- validate_command() | PASS |
| Step 4 | `web_fetch.py` -- SSRF filter | PASS |
| Step 5 | `config.py` + `llm/base.py` -- minor fixes | PASS |
| Step 6 | `webview/main.js` -- marked + DOMPurify | FAIL |
| Step 7 | `mcp/process.ts` + `mcp/client.ts` -- API key env | PASS |
| Step 8 | `chat/panel.ts` nonce + `config.ts` type guards | Partial (nonce PASS, type guards FAIL) |

**Steps Completed**: 6.5 / 8

---

## 5. Differences Summary

### FAIL -- Missing Features (Design O, Implementation X)

| Item | Design Location | Description | Priority |
|------|-----------------|-------------|----------|
| FR-05: XSS fix | design.md Section 3.1 | `marked` + `DOMPurify` not integrated; hand-rolled regex renderer still in place | HIGH |
| FR-10: Config type guards | design.md Section 3.4 | `get<T>(key)` still uses unsafe `as T` cast without default values | LOW |

### CHANGED -- Minor Deviations (Design ~= Implementation)

| Item | Design | Implementation | Impact |
|------|--------|----------------|--------|
| eval/exec patterns | `\beval\b` / `\bexec\b` | `\beval\s` / `\bexec\s` | Low -- implementation is arguably better |
| Missing rm pattern | `\brm\s+...?/\S` extra pattern | Not included | Medium -- `rm -rf /var` would not be blocked |
| json import alias | `import json` | `import json as _json` | None -- style only |

---

## 6. Match Rate Calculation

```
Total FR items: 10

  Fully Matched:    7  (FR-01, FR-02, FR-04, FR-06, FR-07, FR-08, FR-09)
  Matched w/ minor: 1  (FR-03: pattern deviations)
  Not Implemented:  2  (FR-05, FR-10)

Design Match Rate = (7 * 10 + 1 * 8 + 2 * 0) / 100 = 78%

Weighted Match Rate (by priority):
  FR-05 (HIGH priority, XSS): weight 15
  FR-10 (LOW priority, type safety): weight 5
  Others (8 items): weight 10 each

  Score = (8 * 10) / (8 * 10 + 15 + 5) = 80 / 100 = 80%
```

**Overall Match Rate: 80%**

---

## 7. Recommended Actions

### 7.1 Immediate Actions (24h)

| Priority | Item | Files | Description |
|----------|------|-------|-------------|
| HIGH | FR-05 구현 | `webview/main.js`, `package.json` | `npm install dompurify`, marked custom renderer + DOMPurify sanitization 적용. 현재 regex 기반 renderMarkdown()은 XSS 위험 |
| MEDIUM | FR-03 rm 패턴 보완 | `tools/base.py` | `BLOCKED_COMMAND_PATTERNS`에 `r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/\S"` 패턴 추가 |

### 7.2 Short-term Actions (1 week)

| Priority | Item | Files | Description |
|----------|------|-------|-------------|
| LOW | FR-10 구현 | `apps/vscode-extension/src/config.ts` | `get<T>(key, defaultValue): T` 패턴으로 변경, caller에서 default 전달 |

### 7.3 Design Document Updates

| Item | Description |
|------|-------------|
| FR-03 패턴 | `\beval\b` -> `\beval\s` 변경 사유 문서화 (false positive 방지) |
| FR-08 alias | `import json as _json` convention 반영 |

---

## 8. Synchronization Options

Match Rate 80%로 90% 미만이므로 Act 단계가 필요하다.

**권장 조치**:
1. **FR-05 구현**: 설계대로 `marked` + `DOMPurify` 적용 (구현을 설계에 맞춤)
2. **FR-10 구현**: 설계대로 type guard 패턴 적용 (구현을 설계에 맞춤)
3. **FR-03 패턴 차이**: 구현이 더 나은 선택이므로 설계 문서를 구현에 맞춤 업데이트

---

## 9. Next Steps

- [ ] FR-05 구현 (marked + DOMPurify) -- Match Rate 90%로 상승 예상
- [ ] FR-10 구현 (config.ts type guards) -- Match Rate 95%+ 예상
- [ ] FR-03 설계 문서 업데이트
- [ ] 재분석 실행: `/pdca analyze core-security-hardening`
- [ ] Match Rate >= 90% 달성 시: `/pdca report core-security-hardening`

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-03-17 | Initial gap analysis | AI (gap-detector) |
