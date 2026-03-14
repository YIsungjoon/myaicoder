# Design: advanced-mcp-tools

**Feature**: advanced-mcp-tools
**Date**: 2026-03-14
**Phase**: Design
**Level**: Enterprise
**Plan**: `docs/pdca/01-plan/features/advanced-mcp-tools.plan.md`
**Depends on**: tools/base.py (Tool ABC), tools/registry.py, mcp/server.py

---

## 1. Overview

기존 6개 도구에 3개 신규 도구(BuildRunner, WebFetch, ListDir)를 추가하고 2개 기존 도구(Bash, Grep)를 개선한다. 사전 피드백 3가지(FB-A/B/C)를 설계 단계에서 반영한다.

### 피드백 반영 사항

| # | 피드백 | 설계 반영 |
|---|--------|----------|
| FB-A | ListDir .gitignore 존중 | 재귀 탐색 진입 전 폴더명 필터 최우선 배치, `.` 시작 폴더 전체 스킵 |
| FB-B | WebFetch script/style 전처리 | HTML→text 변환 시 `<script>`, `<style>` 블록 먼저 제거 후 태그 제거 |
| FB-C | Grep context 구분선 | context_lines > 0일 때 블록 간 `--` 구분선 삽입 |

---

## 2. Module Structure

```
services/myaicoder/src/myaicoder/tools/
├── base.py            ← [변경 없음]
├── registry.py        ← [수정] 새 도구 3개 등록
├── bash.py            ← [수정] working_dir, env, 위험 명령 차단
├── grep_tool.py       ← [수정] context_lines, output_mode, 구분선 (FB-C)
├── build_runner.py    ← [신규] 빌드/테스트 실행 + 에러 구조화
├── web_fetch.py       ← [신규] URL→텍스트 (FB-B 반영)
└── list_dir.py        ← [신규] 디렉토리 트리 (FB-A 반영)
```

---

## 3. 신규 도구 상세 설계

### 3.1 BuildRunner (`tools/build_runner.py`)

```python
class BuildRunnerTool(Tool):
    name = "BuildRunner"

    parameters_schema = {
        "properties": {
            "command": {"type": "string", "description": "Build/test command"},
            "working_dir": {"type": "string", "description": "Working directory"},
            "parse_errors": {"type": "boolean", "description": "Parse errors (default: true)"},
            "timeout": {"type": "integer", "description": "Timeout seconds (default: 300)"},
        },
        "required": ["command"],
    }
```

#### 실행 흐름

```
execute(command, working_dir, parse_errors, timeout)
  ↓
1. asyncio.create_subprocess_shell(command, cwd=working_dir)
2. stdout, stderr = await wait_for(proc.communicate(), timeout)
3. if parse_errors:
     errors = _parse_errors(stdout + stderr)
4. 구조화된 출력 생성
```

#### 에러 파싱 (`_parse_errors`)

```python
ERROR_PATTERNS = [
    # pytest: FAILED tests/foo.py::test_name - ErrorType: msg
    re.compile(r"FAILED\s+(.+?)::(\S+)\s*-\s*(.+)"),
    # Python: File "path", line N
    re.compile(r'File "(.+?)", line (\d+)'),
    # TypeScript: path(line,col): error TSxxxx: msg
    re.compile(r"(.+?)\((\d+),\d+\):\s*error\s+(.+)"),
    # Generic: path:line:col: error/warning: msg
    re.compile(r"(.+?):(\d+):\d+:\s*(error|warning):\s*(.+)"),
]

def _parse_errors(output: str) -> list[dict]:
    """Parse structured errors from build output.

    Returns:
        [{"file": "...", "line": N, "message": "..."}]

    Falls back to empty list if no patterns match (raw output always included).
    """
```

#### 출력 형식

```
exit_code: 1
summary: 2 failed, 18 passed

errors:
  [1] tests/test_foo.py:42 — AssertionError: expected 3, got 5
  [2] tests/test_bar.py:17 — ImportError: No module named 'xyz'

raw_output:
  (원본 stdout+stderr, 최대 30000자)
```

### 3.2 WebFetch (`tools/web_fetch.py`) — FB-B 반영

```python
class WebFetchTool(Tool):
    name = "WebFetch"

    parameters_schema = {
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "max_length": {"type": "integer", "description": "Max chars (default: 20000)"},
        },
        "required": ["url"],
    }
```

#### HTML→Text 변환 순서 (FB-B 핵심)

```python
def _html_to_text(html: str) -> str:
    """Convert HTML to plain text.

    Order matters (FB-B):
    1. Remove <script>...</script> blocks (JS code)
    2. Remove <style>...</style> blocks (CSS code)
    3. Remove <nav>, <footer>, <header> blocks (비본문)
    4. Replace <br>, <p>, <div>, <li> with newlines
    5. Remove remaining HTML tags
    6. Decode HTML entities (&amp; → &, etc.)
    7. Collapse multiple whitespace/newlines
    """
    # Step 1-2: FB-B — script/style 먼저 제거 (DOTALL로 멀티라인 매칭)
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Step 3: 비본문 태그 제거
    for tag in ("nav", "footer", "header"):
        text = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Step 4: 블록 태그 → 줄바꿈
    text = re.sub(r"<(?:br|p|div|li|h[1-6])[^>]*>", "\n", text, flags=re.IGNORECASE)

    # Step 5: 나머지 태그 제거
    text = re.sub(r"<[^>]+>", "", text)

    # Step 6: HTML 엔티티 디코딩
    import html as html_module
    text = html_module.unescape(text)

    # Step 7: 공백 정리
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()
```

#### 실행 흐름

```
execute(url, max_length)
  ↓
1. URL 유효성 검사 (http/https만)
2. httpx.AsyncClient.get(url, timeout=10, follow_redirects=True)
3. content_type 확인 (text/html, text/plain, application/json만)
4. _html_to_text(response.text)  ← FB-B 적용
5. text[:max_length] 잘라서 반환
```

#### 안전 장치

| 항목 | 값 |
|------|-----|
| 타임아웃 | 10초 |
| 최대 응답 크기 | 5MB (`response.content` 체크) |
| User-Agent | `myaicoder/1.0 (Documentation Fetcher)` |
| 허용 스킴 | http, https만 (file:// 차단) |
| 허용 Content-Type | text/html, text/plain, application/json |

### 3.3 ListDir (`tools/list_dir.py`) — FB-A 반영

```python
class ListDirTool(Tool):
    name = "ListDir"

    parameters_schema = {
        "properties": {
            "path": {"type": "string", "description": "Directory path"},
            "max_depth": {"type": "integer", "description": "Max depth (default: 3)"},
            "show_hidden": {"type": "boolean", "description": "Show hidden files (default: false)"},
        },
        "required": ["path"],
    }
```

#### 탐색 로직 (FB-A 핵심)

```python
SKIP_DIRS = {
    "node_modules", "__pycache__", "venv", ".venv",
    ".next", "dist", ".mypy_cache", ".ruff_cache",
    ".tox", ".eggs", "build", ".build",
}

def _build_tree(root: Path, max_depth: int, show_hidden: bool) -> list[str]:
    """Build directory tree with FB-A filtering.

    FB-A: 폴더 진입 전 필터 체크 — 최상단에 배치
    """
    lines = []
    count = 0
    MAX_ITEMS = 500

    def _walk(dir_path: Path, prefix: str, depth: int):
        nonlocal count
        if depth > max_depth or count >= MAX_ITEMS:
            return

        try:
            entries = sorted(dir_path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return

        # Filter entries
        visible = []
        for entry in entries:
            # FB-A: 최우선 필터 — 숨김 폴더/파일 스킵
            if not show_hidden and entry.name.startswith("."):
                continue
            # FB-A: 하드코딩 무시 목록
            if entry.is_dir() and entry.name in SKIP_DIRS:
                continue
            visible.append(entry)

        for i, entry in enumerate(visible):
            if count >= MAX_ITEMS:
                lines.append(f"{prefix}... ({MAX_ITEMS} items limit)")
                return

            is_last = i == len(visible) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
            count += 1

            if entry.is_dir():
                extension = "    " if is_last else "│   "
                _walk(entry, prefix + extension, depth + 1)

    lines.append(f"{root.name}/")
    count += 1
    _walk(root, "", 1)
    return lines
```

---

## 4. 기존 도구 개선

### 4.1 Bash 고도화 (`tools/bash.py`)

#### 추가 파라미터

```python
# parameters_schema에 추가
"working_dir": {
    "type": "string",
    "description": "Working directory for the command.",
},
"env": {
    "type": "object",
    "description": "Additional environment variables.",
},
```

#### 위험 명령 차단

```python
import re

BLOCKED_PATTERNS = [
    re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?/(?!\S)"),  # rm -rf /
    re.compile(r"\bmkfs\b"),                                      # filesystem format
    re.compile(r"\bdd\s+.*of=/dev/"),                             # disk overwrite
    re.compile(r":\(\)\s*\{.*\}\s*;"),                            # fork bomb
    re.compile(r"\bshutdown\b"),                                  # system shutdown
    re.compile(r"\breboot\b"),                                    # system reboot
]

def _is_dangerous(command: str) -> str | None:
    """Check if command matches any blocked pattern.
    Returns the pattern description if blocked, None otherwise.
    """
    for pattern in BLOCKED_PATTERNS:
        if pattern.search(command):
            return f"Blocked: matches dangerous pattern '{pattern.pattern}'"
    return None
```

#### 수정된 execute

```python
async def execute(self, **kwargs) -> ToolResult:
    command = kwargs.get("command", "")
    timeout = kwargs.get("timeout", 120)
    working_dir = kwargs.get("working_dir", None)
    env = kwargs.get("env", None)

    # 위험 명령 차단
    danger = _is_dangerous(command)
    if danger:
        return ToolResult(success=False, output="", error=danger)

    # working_dir 유효성
    cwd = None
    if working_dir:
        cwd = Path(working_dir)
        if not cwd.is_dir():
            return ToolResult(success=False, output="", error=f"Not a directory: {working_dir}")

    # env 병합
    import os
    proc_env = None
    if env:
        proc_env = {**os.environ, **env}

    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
        env=proc_env,
    )
    # ... 기존 timeout/output 로직 유지
```

### 4.2 Grep 개선 (`tools/grep_tool.py`) — FB-C 반영

#### 추가 파라미터

```python
"context_lines": {
    "type": "integer",
    "description": "Lines of context before/after match (default: 0, max: 5).",
},
"output_mode": {
    "type": "string",
    "description": "Output mode: 'matches' (default), 'files', 'count'.",
    "enum": ["matches", "files", "count"],
},
```

#### Context Lines 로직 (FB-C 핵심)

```python
# output_mode == "matches" and context_lines > 0:
def _search_with_context(filepath, lines, regex, context_lines):
    """Search with context, adding '--' separators between blocks (FB-C)."""
    blocks = []
    matched_ranges = set()

    for lineno, line in enumerate(lines):
        if regex.search(line):
            start = max(0, lineno - context_lines)
            end = min(len(lines), lineno + context_lines + 1)
            matched_ranges.add((start, end, lineno))

    # Merge overlapping ranges
    merged = _merge_ranges(sorted(matched_ranges))

    for start, end, match_lines in merged:
        block = []
        for i in range(start, end):
            prefix = ">" if i in match_lines else " "
            block.append(f"{filepath}:{i+1}:{prefix} {lines[i].rstrip()}")
        blocks.append("\n".join(block))

    # FB-C: 블록 간 구분선
    return "\n--\n".join(blocks)
```

#### Output Mode

```python
if output_mode == "files":
    # 파일 경로만 반환 (중복 제거)
    return "\n".join(sorted(set(matched_files)))

if output_mode == "count":
    # 파일별 매칭 수
    return "\n".join(f"{path}: {count}" for path, count in file_counts.items())
```

---

## 5. Registry 및 MCP 등록

### 5.1 Registry 수정 (`tools/registry.py`)

```python
def create_default_registry() -> ToolRegistry:
    from myaicoder.tools.bash import BashTool
    from myaicoder.tools.build_runner import BuildRunnerTool
    from myaicoder.tools.edit import EditTool
    from myaicoder.tools.glob_tool import GlobTool
    from myaicoder.tools.grep_tool import GrepTool
    from myaicoder.tools.list_dir import ListDirTool
    from myaicoder.tools.read import ReadTool
    from myaicoder.tools.web_fetch import WebFetchTool
    from myaicoder.tools.write import WriteTool

    registry = ToolRegistry()
    registry.register(ReadTool())
    registry.register(WriteTool())
    registry.register(EditTool())
    registry.register(GlobTool())
    registry.register(GrepTool())
    registry.register(BashTool())
    registry.register(BuildRunnerTool())   # 신규
    registry.register(WebFetchTool())      # 신규
    registry.register(ListDirTool())       # 신규
    return registry
```

### 5.2 MCP Server 노출

신규 도구는 `mcp/server.py`의 기존 동적 등록 메커니즘으로 자동 노출된다.
이름 매핑(`TOOL_NAME_MAP`)은 기존 도구와의 일관성을 위해 사용되지만,
신규 도구는 `tool.name.lower()` 폴백으로 충분하므로 별도 매핑을 추가하지 않는다.

---

## 6. Implementation Order

| # | 파일 | 작업 | 의존 |
|---|------|------|------|
| 1 | `tools/list_dir.py` | ListDir 신규 (FB-A) | base.py |
| 2 | `tools/web_fetch.py` | WebFetch 신규 (FB-B) | base.py |
| 3 | `tools/build_runner.py` | BuildRunner 신규 | base.py |
| 4 | `tools/bash.py` | working_dir, env, 위험 차단 | 없음 |
| 5 | `tools/grep_tool.py` | context_lines, output_mode, 구분선 (FB-C) | 없음 |
| 6 | `tools/registry.py` | 새 도구 3개 등록 | 1, 2, 3 |
| 7 | `tests/test_tools/test_list_dir.py` | ListDir 테스트 | 1 |
| 8 | `tests/test_tools/test_web_fetch.py` | WebFetch 테스트 | 2 |
| 9 | `tests/test_tools/test_build_runner.py` | BuildRunner 테스트 | 3 |
| 10 | `tests/test_tools/test_bash.py` | Bash 개선 테스트 | 4 |
| 11 | `tests/test_tools/test_grep.py` | Grep 개선 테스트 | 5 |

---

## 7. Test Plan

### 7.1 ListDir 테스트 (`test_list_dir.py`)

| # | 테스트 | 검증 |
|---|--------|------|
| T1 | `test_basic_tree` | 기본 디렉토리 트리 출력 |
| T2 | `test_skip_hidden_dirs` | `.git`, `.venv` 등 숨김 폴더 스킵 (FB-A) |
| T3 | `test_skip_node_modules` | node_modules, __pycache__ 스킵 (FB-A) |
| T4 | `test_show_hidden_flag` | `show_hidden=True`면 숨김 파일 표시 |
| T5 | `test_max_depth` | depth 제한 동작 |
| T6 | `test_max_items_limit` | 500개 항목 제한 |
| T7 | `test_nonexistent_path` | 존재하지 않는 경로 에러 |

### 7.2 WebFetch 테스트 (`test_web_fetch.py`)

| # | 테스트 | 검증 |
|---|--------|------|
| T8 | `test_html_to_text_basic` | 기본 태그 제거 |
| T9 | `test_html_to_text_removes_script` | `<script>` 블록 제거 (FB-B) |
| T10 | `test_html_to_text_removes_style` | `<style>` 블록 제거 (FB-B) |
| T11 | `test_html_to_text_preserves_content` | 본문 텍스트 보존 |
| T12 | `test_html_entities` | `&amp;` → `&` 변환 |
| T13 | `test_invalid_url_scheme` | `file://` 차단 |
| T14 | `test_max_length_truncation` | max_length 잘림 |

### 7.3 BuildRunner 테스트 (`test_build_runner.py`)

| # | 테스트 | 검증 |
|---|--------|------|
| T15 | `test_successful_command` | 성공 명령 (exit 0) |
| T16 | `test_failed_command` | 실패 명령 (exit != 0) |
| T17 | `test_parse_pytest_errors` | pytest FAILED 파싱 |
| T18 | `test_parse_python_traceback` | Python File "..." 파싱 |
| T19 | `test_parse_generic_errors` | path:line:col 파싱 |
| T20 | `test_working_dir` | working_dir 동작 |
| T21 | `test_timeout` | 타임아웃 처리 |

### 7.4 Bash 개선 테스트 (`test_bash.py`)

| # | 테스트 | 검증 |
|---|--------|------|
| T22 | `test_working_dir` | cwd 변경 동작 |
| T23 | `test_env_variables` | 환경변수 주입 |
| T24 | `test_block_rm_rf_root` | `rm -rf /` 차단 |
| T25 | `test_block_mkfs` | `mkfs` 차단 |
| T26 | `test_block_fork_bomb` | fork bomb 차단 |
| T27 | `test_allow_normal_rm` | 일반 `rm` 허용 |

### 7.5 Grep 개선 테스트 (`test_grep.py`)

| # | 테스트 | 검증 |
|---|--------|------|
| T28 | `test_context_lines` | context_lines=2 전후 2줄 표시 |
| T29 | `test_context_separator` | 블록 간 `--` 구분선 (FB-C) |
| T30 | `test_output_mode_files` | files 모드 |
| T31 | `test_output_mode_count` | count 모드 |
| T32 | `test_backward_compat` | 기존 파라미터로 동일 동작 |

### 7.6 테스트 예상 수량

- test_list_dir.py: 7개 (T1~T7)
- test_web_fetch.py: 7개 (T8~T14)
- test_build_runner.py: 7개 (T15~T21)
- test_bash.py: 6개 (T22~T27)
- test_grep.py: 5개 (T28~T32)
- **총 신규 테스트: 32개**

---

## 8. Success Criteria

- [ ] BuildRunner가 pytest 에러를 구조화된 형태로 반환한다
- [ ] WebFetch가 script/style 태그를 제거한 후 텍스트를 추출한다 (FB-B)
- [ ] Bash가 working_dir을 지원하고 위험 명령을 차단한다
- [ ] ListDir이 .git/node_modules 등을 탐색하지 않는다 (FB-A)
- [ ] Grep context_lines > 0일 때 블록 간 `--` 구분선이 포함된다 (FB-C)
- [ ] 모든 새 도구가 create_default_registry()에 등록된다
- [ ] 모든 새 도구가 MCP Server에 노출된다
- [ ] 테스트 32개가 `uv run pytest tests -q`로 통과한다
- [ ] 기존 145개 테스트가 깨지지 않는다 (하위 호환)

---

## 9. Risk

| 리스크 | 영향 | 대응 |
|--------|------|------|
| 에러 파싱 정확도 | 구조화 실패 | raw_output 항상 포함 (폴백) |
| WebFetch 외부 네트워크 | 테스트에서 실제 HTTP 필요 | `_html_to_text` 단위 테스트 + HTTP는 mock |
| 위험 명령 우회 | 보안 문제 | 블록리스트 + require_approval 유지 |
| ListDir 심볼릭 링크 루프 | 무한 재귀 | `resolve()` 안 함, 심볼릭은 표시만 |
| Grep context 성능 | 대량 매칭 시 느림 | max_results 500 유지 |

---

## 10. Out of Scope

| 항목 | 사유 |
|------|------|
| PythonAST 도구 | 복잡도 높음, 별도 feature |
| 웹 검색 (Google API) | API key 필요, 별도 feature |
| MCP server.py 수정 | 기존 동적 등록으로 자동 노출됨 |
| beautifulsoup4 의존성 | regex로 충분, 외부 의존성 최소화 |
