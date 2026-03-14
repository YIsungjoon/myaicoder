# Plan: advanced-mcp-tools

**Feature**: advanced-mcp-tools
**Date**: 2026-03-14
**Phase**: Plan
**Level**: Enterprise
**Parent Context**: Track B-1 — 에이전트 능력 극대화
**Roadmap**: `docs/roadmap-2026-03.md` Track B-1

---

## 1. Overview

기존 6개 MCP 도구(Read, Write, Edit, Glob, Grep, Bash)를 넘어, **에이전트가 실제 코딩 작업에서 자립적으로 문제를 해결**할 수 있도록 고급 도구를 추가한다.

### 현재 상태

| 도구 | 기능 | 상태 |
|------|------|------|
| Read | 파일 읽기 | ✅ 구현 완료 |
| Write | 파일 쓰기 | ✅ 구현 완료 |
| Edit | 문자열 치환 | ✅ 구현 완료 |
| Glob | 파일 검색 | ✅ 구현 완료 |
| Grep | 내용 검색 | ✅ 구현 완료 |
| Bash | 명령 실행 | ✅ 구현 완료 (--allow-bash 필요) |

### 부족한 점

| 시나리오 | 현재 | 문제 |
|----------|------|------|
| 빌드 에러 피드백 | Bash로 빌드 → 에러 텍스트만 반환 | 에러 위치/원인 구조화 안 됨 |
| 컴파일/테스트 루프 | 수동으로 Bash 반복 | 자동 피드백 루프 없음 |
| 웹 문서 참조 | 불가능 | 외부 문서 검색 못 함 |
| 코드 구조 파악 | Grep으로 텍스트 검색만 | 함수/클래스 구조 이해 못 함 |

## 2. 핵심 요구사항

### 2.1 새 도구 후보 (우선순위 평가)

| ID | 도구 | 설명 | 복잡도 | 가치 | 우선순위 |
|----|------|------|--------|------|----------|
| T1 | **BuildRunner** | 빌드/테스트 실행 + 구조화된 에러 파싱 | 중 | 높 | **P0** |
| T2 | **WebFetch** | URL → 텍스트 추출 (문서 참조) | 낮 | 높 | **P0** |
| T3 | **ListDir** | 디렉토리 구조 트리 (depth 제한) | 낮 | 중 | **P1** |
| T4 | **PythonAST** | Python AST 파싱 → 함수/클래스 구조 | 높 | 중 | **P2** |

### 2.2 기존 도구 개선

| ID | 도구 | 개선 | 우선순위 |
|----|------|------|----------|
| E1 | **Bash 고도화** | working_dir 지원, 환경변수 주입, 위험 명령 차단 | **P0** |
| E2 | **Grep 개선** | context lines (-A/-B), output_mode (files_only/count) | **P1** |

## 3. Scope

### 3.1 In Scope (이번 PDCA)

| # | 항목 | 우선순위 |
|---|------|----------|
| 1 | BuildRunner 도구 (빌드/테스트 + 에러 파싱) | P0 |
| 2 | WebFetch 도구 (URL → 텍스트 추출) | P0 |
| 3 | Bash 도구 고도화 (working_dir, 위험 명령 차단) | P0 |
| 4 | ListDir 도구 (디렉토리 트리) | P1 |
| 5 | Grep 개선 (context lines) | P1 |
| 6 | ToolRegistry에 등록 + MCP Server 노출 | P0 |
| 7 | pytest 테스트 | P0 |

### 3.2 Out of Scope

| 항목 | 사유 |
|------|------|
| PythonAST 도구 | 복잡도 높음, 별도 feature |
| 웹 검색 (Google) | API key 필요, 별도 feature |
| 파일 감시 (inotify) | 실시간 모니터링은 별도 feature |
| 도구 체인 자동화 | AgentEngine의 기존 루프로 충분 |

## 4. 사전 피드백 반영 사항

| # | 피드백 | 핵심 | 반영 위치 |
|---|--------|------|----------|
| FB-A | ListDir .gitignore 존중 | `.`으로 시작하는 폴더, node_modules 등은 **탐색 진입 자체를 스킵** (continue) — 무시 패턴 체크를 재귀 최상단에 배치 | §5.4 ListDir |
| FB-B | WebFetch script/style 전처리 | `<script>.*?</script>`, `<style>.*?</style>` 블록을 **태그 제거 전에 먼저 완전 삭제** — JS/CSS가 텍스트로 노출되어 토큰 예산 낭비 방지 | §5.2 WebFetch |
| FB-C | Grep context 구분선 | context_lines > 0일 때 매칭 블록 사이에 **`--` 구분선** 삽입 — LLM이 다른 파일/위치 코드를 하나로 착각하는 것 방지 | §5.5 Grep |

---

## 5. 도구 상세

### 5.1 BuildRunner

**목적**: 빌드/테스트 명령을 실행하고, 에러를 구조화된 형태로 반환한다.

```python
# 사용 예
result = await build_runner.execute(
    command="pytest tests/ -q",
    working_dir="/path/to/project",
    parse_errors=True,
)
# 결과: success=False
# output:
#   exit_code: 1
#   summary: "2 failed, 18 passed"
#   errors:
#     - file: tests/test_foo.py
#       line: 42
#       message: "AssertionError: expected 3, got 5"
#     - file: tests/test_bar.py
#       line: 17
#       message: "ImportError: No module named 'xyz'"
#   raw_output: "..."
```

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| command | string | ✅ | 빌드/테스트 명령 |
| working_dir | string | - | 작업 디렉토리 |
| parse_errors | bool | - | 에러 구조화 (기본 true) |
| timeout | int | - | 초 단위 타임아웃 (기본 300) |

**에러 파싱 패턴**:
- Python: `File "path", line N, ...` + traceback
- pytest: `FAILED tests/xxx.py::test_name - ErrorType: message`
- TypeScript/Node: `path(line,col): error TS...`
- 일반: `path:line:col: error/warning: message`

### 5.2 WebFetch

**목적**: URL에서 텍스트 콘텐츠를 추출한다 (HTML → plain text).

```python
result = await web_fetch.execute(
    url="https://docs.python.org/3/library/ast.html",
    max_length=10000,
)
# 결과: success=True
# output: "ast — Abstract Syntax Trees\n\nSource code: ...\n..."
```

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| url | string | ✅ | 가져올 URL |
| max_length | int | - | 최대 문자 수 (기본 20000) |
| selector | string | - | CSS 선택자 (기본 body) |

**구현**: `httpx` (이미 gateway 의존성) + 간단한 HTML→text 변환 (태그 제거).
외부 의존성 최소화: `beautifulsoup4`는 선택적(있으면 사용, 없으면 regex 폴백).

**⚠️ FB-B: script/style 전처리 (필수)**
HTML 태그 제거 전에 반드시 `<script>.*?</script>`, `<style>.*?</style>` 블록을 먼저 완전 삭제해야 한다.
그렇지 않으면 방대한 JS/CSS 코드가 일반 텍스트로 노출되어 토큰 예산을 낭비한다.
```python
# 올바른 순서:
# 1. <script>...</script> 제거
# 2. <style>...</style> 제거
# 3. <nav>, <footer>, <header> 등 비본문 태그 제거 (선택)
# 4. 나머지 HTML 태그 제거
# 5. 연속 공백/줄바꿈 정리
```

### 5.3 Bash 고도화

**현재**: command + timeout만 지원.

**추가**:

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| working_dir | string | 작업 디렉토리 (기본 cwd) |
| env | dict | 추가 환경변수 |

**위험 명령 차단**:
```python
BLOCKED_PATTERNS = [
    r"\brm\s+-rf\s+/",          # rm -rf /
    r"\bmkfs\b",                 # filesystem format
    r"\bdd\s+.*of=/dev/",       # disk overwrite
    r":(){.*};:",                # fork bomb
]
```

차단 시 `ToolResult(success=False, error="Blocked: dangerous command")`

### 5.4 ListDir

**목적**: 디렉토리 구조를 트리 형태로 반환한다.

```python
result = await list_dir.execute(
    path="/home/user/project",
    max_depth=2,
)
# 결과:
# project/
# ├── src/
# │   ├── main.py
# │   └── utils.py
# ├── tests/
# │   └── test_main.py
# └── README.md
```

| 파라미터 | 타입 | 필수 | 설명 |
|----------|------|------|------|
| path | string | ✅ | 디렉토리 경로 |
| max_depth | int | - | 최대 깊이 (기본 3) |
| show_hidden | bool | - | 숨김 파일 표시 (기본 false) |

**제한**: 최대 500개 항목

**⚠️ FB-A: 탐색 스킵 로직 최우선 배치 (필수)**
재귀 탐색 시 폴더 진입 **전에** 다음 패턴을 체크하여 해당 하위 트리 전체를 스킵(continue):
1. `.`으로 시작하는 폴더 (`.git`, `.venv`, `.mypy_cache` 등)
2. 하드코딩 무시 목록: `node_modules`, `__pycache__`, `venv`, `.next`, `dist`, `.ruff_cache`
3. `show_hidden=False`(기본)이면 `.`으로 시작하는 파일도 제외

이 체크를 재귀 **최상단**에 배치하지 않으면 .git 폴더(수만 개 파일)를 탐색하다 항목 제한에 도달하여 실제 프로젝트 파일을 못 보게 된다.

### 5.5 Grep 개선

**추가 파라미터**:

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| context_lines | int | 전후 문맥 줄 수 (기본 0, 최대 5) |
| output_mode | string | "matches" (기본), "files", "count" |

**⚠️ FB-C: 매칭 블록 간 구분선 (필수)**
`context_lines > 0`일 때 여러 매칭 결과가 반환되면, 블록 사이에 `--` 구분선을 삽입한다.
구분선이 없으면 LLM이 서로 다른 파일/위치의 코드를 하나로 이어진 것으로 착각한다.
```
path/foo.py:10: def hello():
path/foo.py:11:     return "world"
--
path/bar.py:25: def goodbye():
path/bar.py:26:     return "farewell"
```

## 6. 성공 기준

- [ ] BuildRunner가 pytest 에러를 구조화된 형태로 반환한다
- [ ] WebFetch가 URL에서 텍스트를 추출한다 (HTML 태그 제거)
- [ ] Bash 도구가 working_dir을 지원하고 위험 명령을 차단한다
- [ ] ListDir이 트리 형태 디렉토리 구조를 반환한다
- [ ] Grep이 context lines를 지원한다
- [ ] ListDir이 .git/node_modules 등을 탐색하지 않는다 (FB-A)
- [ ] WebFetch가 script/style 태그를 제거한 후 텍스트를 추출한다 (FB-B)
- [ ] Grep context_lines > 0일 때 블록 간 `--` 구분선이 포함된다 (FB-C)
- [ ] 모든 새 도구가 MCP Server에 노출된다
- [ ] 테스트가 `uv run pytest tests -q`로 통과한다

## 7. 의존 관계

```
advanced-mcp-tools (이번 feature)
  ├── depends on: tools/base.py (Tool ABC, ToolResult)
  ├── depends on: tools/registry.py (create_default_registry)
  ├── depends on: mcp/server.py (FastMCP 도구 등록)
  ├── modifies: tools/bash.py (working_dir, env, 위험 차단)
  ├── modifies: tools/grep_tool.py (context_lines, output_mode)
  ├── new: tools/build_runner.py
  ├── new: tools/web_fetch.py
  ├── new: tools/list_dir.py
  └── modifies: tools/registry.py (새 도구 등록)
```

## 8. 기술 결정 사항

| 항목 | 결정 | 근거 |
|------|------|------|
| HTTP 클라이언트 | httpx | 이미 gateway 의존성, async 지원 |
| HTML 파싱 | regex 기반 (bs4 없이) | 외부 의존성 최소화, 태그 제거만 필요 |
| 에러 파싱 | regex 패턴 매칭 | 언어별 에러 형식이 정형화됨 |
| 위험 명령 차단 | 정규식 블록리스트 | 간단하고 확장 가능 |
| 디렉토리 트리 | pathlib 재귀 탐색 | 표준 라이브러리만 사용 |

## 9. 리스크

| 리스크 | 영향 | 대응 |
|--------|------|------|
| 에러 파싱 정확도 | 잘못된 파싱 | 구조화 실패 시 raw output 폴백 |
| WebFetch 타임아웃 | 느린 사이트 | 10초 타임아웃 + 에러 메시지 |
| WebFetch 차단(robots.txt) | 일부 사이트 접근 불가 | User-Agent 설정 + 에러 반환 |
| 대용량 디렉토리 | ListDir 느림/OOM | max_depth + 항목 수 제한 (500) |
| Bash 위험 차단 우회 | 보안 문제 | 블록리스트 + 사용자 승인 기본 유지 |
