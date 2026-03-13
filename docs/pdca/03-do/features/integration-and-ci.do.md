# Do: integration-and-ci

**Feature**: integration-and-ci
**날짜**: 2026-03-13
**Phase**: Do

---

## 1. 목적

CI 도입 전에 현재 저장소에서 즉시 실패할 기술적 장애물을 제거한다.

## 2. 반영한 변경

### 2.1 VS Code Extension lint 경로 수정

- [package.json](/home/laon/Desktop/myAiCoder/apps/vscode-extension/package.json)
  - `lint` 스크립트를 `eslint src/`에서 `tsc --noEmit -p tsconfig.json`으로 변경
  - 현재 저장소에는 eslint 의존성과 설정이 없으므로, 실행 가능한 타입체크 기반 검증으로 우선 전환

### 2.2 Python ruff 오류 제거

- [chat.py](/home/laon/Desktop/myAiCoder/services/myaicoder/src/myaicoder/ui/chat.py)
- [conftest.py](/home/laon/Desktop/myAiCoder/services/myaicoder/tests/conftest.py)
- [test_config.py](/home/laon/Desktop/myAiCoder/services/myaicoder/tests/test_mcp/test_config.py)
- [test_server.py](/home/laon/Desktop/myAiCoder/services/myaicoder/tests/test_mcp/test_server.py)
- [test_registry.py](/home/laon/Desktop/myAiCoder/services/myaicoder/tests/test_tools/test_registry.py)

미사용 import를 제거해 `ruff check .`가 통과하도록 정리했다.

### 2.3 GitHub Actions CI 추가

- [ci.yml](/home/laon/Desktop/myAiCoder/.github/workflows/ci.yml)
  - `python-tests` job
    - Python 3.12
    - `services/myaicoder` 기준 `uv sync --frozen --extra dev`
    - `ruff check`
    - `pytest`
  - `extension-tests` job
    - Node 20 + pnpm
    - `pnpm install --frozen-lockfile`
    - `pnpm --filter myaicoder lint`
    - `pnpm --filter myaicoder test`

### 2.4 Python 기준 명시

- 루트 [pyproject.toml](/home/laon/Desktop/myAiCoder/pyproject.toml) 과 [.python-version](/home/laon/Desktop/myAiCoder/.python-version) 은 현재 `3.11` 기준으로 정렬됨
- `services/myaicoder`의 실제 지원 범위(`>=3.11`)와 충돌하지 않도록 맞춤
- CI 워크플로는 검증 런타임으로 Python `3.12`를 사용하지만, 지원 범위는 `3.11+`로 유지

## 3. 검증 대상

- `cd apps/vscode-extension && pnpm run lint`
- `cd services/myaicoder && uv run ruff check .`
- `pnpm --filter myaicoder test`
- `cd services/myaicoder && uv run pytest tests -q`
