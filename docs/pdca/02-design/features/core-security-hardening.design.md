# Core Security Hardening — Design Document

> **Feature**: core-security-hardening
> **Project**: myAiCoder
> **Date**: 2026-03-17
> **Status**: Draft
> **Plan**: `docs/pdca/01-plan/features/core-security-hardening.plan.md`

---

## 1. 설계 개요

Core Service 9건 + VS Code Extension 4건의 보안 취약점을 수정한다.
공통 모듈(WorkspaceGuard, CommandValidator)을 먼저 만들고, 개별 도구/컴포넌트에 적용하는 방식으로 진행한다.

---

## 2. Core Service 설계

### 2.1 WorkspaceGuard (FR-01)

**목적**: 모든 파일 도구가 워크스페이스 루트 내에서만 동작하도록 제한

**위치**: `services/myaicoder/src/myaicoder/tools/base.py`

```python
import os
from pathlib import Path

class WorkspaceGuard:
    """Validate file paths are within the allowed workspace root."""

    def __init__(self, workspace_root: str | None = None):
        self._root = Path(workspace_root or os.getcwd()).resolve()

    @property
    def root(self) -> Path:
        return self._root

    def validate(self, file_path: str) -> Path:
        """Resolve and validate path is within workspace.

        Returns the resolved Path if valid.
        Raises ValueError if path escapes workspace.
        """
        target = Path(file_path).resolve()
        try:
            target.relative_to(self._root)
        except ValueError:
            raise ValueError(
                f"Access denied: '{file_path}' is outside workspace '{self._root}'"
            )
        return target
```

**적용 방법**: `Tool` ABC에 `workspace_guard` 속성 추가

```python
class Tool(ABC):
    _workspace_guard: WorkspaceGuard | None = None

    @classmethod
    def set_workspace_guard(cls, guard: WorkspaceGuard) -> None:
        cls._workspace_guard = guard

    def validate_path(self, file_path: str) -> Path:
        """Validate path against workspace guard. Call from file tools."""
        if self._workspace_guard is None:
            return Path(file_path)  # No guard = unrestricted (CLI mode)
        return self._workspace_guard.validate(file_path)
```

**핵심 설계 결정**:
- `Path.resolve()` 사용 → symlink 자동 해석, `..` 정규화
- guard가 None이면 제한 없음 (기존 CLI 모드 호환성 유지)
- MCP 서버 모드 시작 시 `--workspace-root` 옵션으로 guard 설정

**적용 대상 도구 (6개)**:

| 도구 | 파일 | 적용 위치 |
|------|------|----------|
| ReadTool | `tools/read.py` | `execute()` 시작부에 `self.validate_path(file_path)` |
| WriteTool | `tools/write.py` | `execute()` 시작부에 `self.validate_path(file_path)` |
| EditTool | `tools/edit.py` | `execute()` 시작부에 `self.validate_path(file_path)` |
| GlobTool | `tools/glob_tool.py` | `execute()` 시작부에 `self.validate_path(path)` |
| GrepTool | `tools/grep_tool.py` | `execute()` 시작부에 `self.validate_path(path)` |
| ListDirTool | `tools/list_dir.py` | `execute()` 시작부에 `self.validate_path(path)` |

**적용 패턴** (모든 파일 도구 공통):

```python
async def execute(self, **kwargs) -> ToolResult:
    file_path = kwargs.get("file_path", "")
    if not file_path:
        return ToolResult(success=False, output="", error="file_path is required")

    try:
        path = self.validate_path(file_path)
    except ValueError as e:
        return ToolResult(success=False, output="", error=str(e))

    # ... 기존 로직 (Path(file_path) → path 변수 사용)
```

---

### 2.2 CommandValidator (FR-03, FR-04)

**목적**: BashTool과 BuildRunnerTool이 공유하는 명령어 안전 검사 모듈

**위치**: `services/myaicoder/src/myaicoder/tools/base.py` (WorkspaceGuard와 같은 파일)

```python
import re

# Existing patterns from bash.py + new patterns
BLOCKED_COMMAND_PATTERNS = [
    # 기존 (bash.py에서 이동)
    re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/(?!\S)"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bdd\s+.*of=/dev/"),
    re.compile(r":\(\)\s*\{.*\}\s*;"),
    re.compile(r"\bshutdown\b"),
    re.compile(r"\breboot\b"),
    # 신규 추가 (C-01 수정)
    re.compile(r"\beval\b"),               # eval 실행
    re.compile(r"\bexec\b"),               # exec 실행
    re.compile(r"\$\("),                    # command substitution
    re.compile(r"`[^`]+`"),                # backtick substitution
    re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/\S"),  # rm -rf /anything
]


def validate_command(command: str) -> str | None:
    """Check if command matches any blocked pattern.

    Returns error message if blocked, None if safe.
    """
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if pattern.search(command):
            return f"Blocked: command matches safety pattern '{pattern.pattern}'"
    return None
```

**적용**:
- `bash.py`: 기존 `BLOCKED_PATTERNS` + `_is_dangerous()` 삭제 → `from .base import validate_command` 사용
- `build_runner.py`: `execute()` 시작부에 `validate_command(command)` 호출 추가

---

### 2.3 SSRF 필터 (FR-02)

**목적**: WebFetchTool이 내부 네트워크 IP 대역에 접근하지 못하도록 차단

**위치**: `services/myaicoder/src/myaicoder/tools/web_fetch.py`

```python
import ipaddress
import socket

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # loopback
    ipaddress.ip_network("10.0.0.0/8"),        # private A
    ipaddress.ip_network("172.16.0.0/12"),     # private B
    ipaddress.ip_network("192.168.0.0/16"),    # private C
    ipaddress.ip_network("169.254.0.0/16"),    # link-local
    ipaddress.ip_network("::1/128"),           # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),          # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),         # IPv6 link-local
]


def _is_private_url(url: str) -> str | None:
    """Check if URL resolves to a private/loopback IP.

    Returns error message if blocked, None if safe.
    DNS resolution happens here to prevent DNS rebinding.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return "Invalid URL: no hostname"

    try:
        # Resolve DNS to get actual IP (prevents DNS rebinding)
        infos = socket.getaddrinfo(hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
        for family, _, _, _, sockaddr in infos:
            ip = ipaddress.ip_address(sockaddr[0])
            for network in _BLOCKED_NETWORKS:
                if ip in network:
                    return f"Blocked: URL resolves to private IP {ip}"
    except socket.gaierror:
        return f"DNS resolution failed for: {hostname}"

    return None
```

**적용**: `web_fetch.py`의 `execute()` 메서드에서 URL scheme 체크 직후에 호출

```python
# Validate URL scheme (기존)
if not url.startswith(("http://", "https://")):
    ...

# SSRF check (신규)
ssrf_error = _is_private_url(url)
if ssrf_error:
    return ToolResult(success=False, output="", error=ssrf_error)
```

---

### 2.4 소소한 수정 (FR-07, FR-08)

**FR-07**: `core/config.py:16` — `api_key: str = "not-needed"` → `api_key: str = ""`

**FR-08**: `llm/base.py:43` — `__import__("json").dumps(tc.arguments)` → module-level `import json` + `json.dumps(tc.arguments)`

---

## 3. VS Code Extension 설계

### 3.1 XSS 수정 — marked + DOMPurify (FR-05)

**목적**: hand-rolled regex 마크다운 렌더링을 안전한 라이브러리로 교체

**위치**: `apps/vscode-extension/webview/main.js`

**의존성 추가**:
```bash
cd apps/vscode-extension
npm install marked dompurify
```
참고: `marked`는 이미 package.json에 존재 (unused). `dompurify`만 신규 추가.

**변경 내용**:

기존 `renderMarkdown()` 함수 전체를 교체:

```javascript
import { marked } from 'marked';
import DOMPurify from 'dompurify';

// Configure marked
marked.setOptions({
  breaks: true,
  gfm: true,
});

// Configure DOMPurify: allow safe HTML tags only
const PURIFY_CONFIG = {
  ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li',
                 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'blockquote',
                 'div', 'span', 'button', 'table', 'thead', 'tbody', 'tr', 'th', 'td'],
  ALLOWED_ATTR: ['class', 'id', 'href', 'data-block-id', 'data-file', 'target'],
  ALLOW_DATA_ATTR: true,
};

function renderMarkdown(text) {
  const rawHtml = marked.parse(text);
  return DOMPurify.sanitize(rawHtml, PURIFY_CONFIG);
}
```

**주의**: webview는 ES module이 아니므로, esbuild 번들링 또는 CDN script 태그 방식 중 선택 필요.
현재 `esbuild.config.mjs`가 존재하므로 **esbuild 번들링 권장**.

**코드 블록 Apply 버튼**: marked의 custom renderer를 사용하여 코드 블록에 Apply 버튼 삽입:

```javascript
const renderer = new marked.Renderer();
renderer.code = function(code, lang) {
  const blockId = 'code-' + crypto.randomUUID().slice(0, 8);
  // lang이 "typescript:src/foo.ts" 형태인 경우 파싱
  let langLabel = lang || 'text';
  let filePath = '';
  if (lang && lang.includes(':')) {
    [langLabel, filePath] = lang.split(':', 2);
  }
  const escapedFp = filePath ? escapeHtml(filePath) : '';
  const applyBtn = escapedFp
    ? `<button class="apply-btn" data-block-id="${blockId}" data-file="${escapedFp}">Apply to ${escapedFp}</button>`
    : `<button class="apply-btn" data-block-id="${blockId}">Apply to Editor</button>`;

  // code.text is already escaped by marked
  return `<div class="code-block-wrapper"><div class="code-block-header"><span class="code-lang">${langLabel}</span>${applyBtn}</div><pre><code id="${blockId}" class="language-${langLabel}">${code}</code></pre></div>`;
};

marked.setOptions({ renderer });
```

---

### 3.2 API 키 환경변수 전달 (FR-06)

**목적**: `--api-key` CLI 인자 → 환경변수로 전달하여 `ps aux` 노출 방지

**변경 파일 1**: `src/mcp/process.ts`

```typescript
// Before
if (options.apiKey) {
  args.push('--api-key', options.apiKey);
}

// After: apiKey를 args에서 제거
// apiKey는 별도 env 객체로 반환
export function buildServeArgs(options: { ... }): { args: string[]; env: Record<string, string> } {
  const args = ['serve'];
  const env: Record<string, string> = {};
  // ... 기존 args 로직 (apiKey 제외)
  if (options.apiKey) {
    env['MYAICODER_API_KEY'] = options.apiKey;
  }
  return { args, env };
}
```

**변경 파일 2**: `src/mcp/client.ts`

```typescript
// StdioClientTransport 생성 시 env 전달
const { args, env } = buildServeArgs({ ... });

this.transport = new StdioClientTransport({
  command: execPath,
  args,
  cwd: cwd ?? undefined,
  stderr: 'pipe',
  env: { ...process.env, ...env },
});
```

**변경 파일 3**: `services/myaicoder/src/myaicoder/cli.py`

```python
# --api-key 옵션 유지 (하위 호환) + 환경변수 우선
api_key = os.environ.get("MYAICODER_API_KEY") or args.api_key
```

---

### 3.3 Nonce 생성 강화 (FR-09)

**목적**: `Math.random()` → `crypto.randomUUID()`

**위치**: `apps/vscode-extension/src/chat/panel.ts:311-318`

```typescript
// Before
function getNonce(): string {
  const chars = 'ABCDEF...';
  let result = '';
  for (let i = 0; i < 32; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

// After
function getNonce(): string {
  return require('crypto').randomUUID().replace(/-/g, '');
}
```

---

### 3.4 Config 타입 가드 (FR-10)

**목적**: `get<T>(key) as T` → 런타임 검증

**위치**: `apps/vscode-extension/src/config.ts`

```typescript
// 타입 안전한 getter 패턴
get<T>(key: string, defaultValue: T): T {
  const value = vscode.workspace.getConfiguration('myaicoder').get<T>(key, defaultValue);
  return value;
}
```

VS Code의 `get<T>(key, defaultValue)` 시그니처는 이미 타입 안전하며 default를 보장한다.
기존 `get<T>(key)` 호출부에 default 인자 추가.

---

## 4. 테스트 설계

### 4.1 Core Service 테스트

| 테스트 | 파일 | 검증 내용 |
|--------|------|----------|
| `test_workspace_guard.py` | 신규 | resolve, symlink, `../` 탈출, 정상 경로 |
| `test_command_validator.py` | 신규 | eval, exec, $(), backtick, 정상 명령 허용 |
| `test_ssrf_filter.py` | 신규 | 127.0.0.1, 10.x, 172.16.x, 192.168.x, localhost 차단 |
| 기존 178개 테스트 | 변경 없음 | 회귀 없음 확인 |

### 4.2 VS Code Extension 테스트

| 테스트 | 파일 | 검증 내용 |
|--------|------|----------|
| `test/process.test.ts` | 수정 | buildServeArgs가 apiKey를 env로 반환하는지 |
| 기존 20개 테스트 | 변경 없음 | 회귀 없음 확인 |

---

## 5. 구현 순서

```
Step 1: base.py — WorkspaceGuard + CommandValidator + validate_command()
  ↓
Step 2: read.py, write.py, edit.py, glob_tool.py, grep_tool.py, list_dir.py — validate_path() 적용
  ↓
Step 3: bash.py — BLOCKED_PATTERNS 삭제, validate_command() 사용
         build_runner.py — validate_command() 추가
  ↓
Step 4: web_fetch.py — _is_private_url() SSRF 필터
  ↓
Step 5: config.py — api_key 기본값 수정
         llm/base.py — 동적 import 제거
  ↓
Step 6: webview/main.js — marked + DOMPurify (npm install 필요)
  ↓
Step 7: mcp/process.ts + mcp/client.ts — API 키 환경변수
  ↓
Step 8: chat/panel.ts — crypto nonce
         config.ts — 타입 가드
```

---

## 6. 롤백 계획

모든 변경은 git commit 단위로 추적. 문제 발생 시 `git revert`로 개별 롤백 가능.

| Step | 영향 범위 | 롤백 위험 |
|------|----------|----------|
| 1-2 | 파일 도구 | 낮음 — guard=None이면 기존 동작 |
| 3 | 명령 실행 | 중간 — 정상 명령 차단 가능성 |
| 4 | WebFetch | 낮음 — 외부 URL 영향 없음 |
| 5 | Config/LLM | 낮음 — 동작 변경 없음 |
| 6 | Webview | 중간 — 마크다운 렌더링 변경 |
| 7 | MCP 연결 | 중간 — 인터페이스 변경 |
| 8 | UI | 낮음 — 내부 변경만 |

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-03-17 | Initial design | AI |
