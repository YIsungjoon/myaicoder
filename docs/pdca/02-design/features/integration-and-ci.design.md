# Design: integration-and-ci

**Feature**: integration-and-ci
**날짜**: 2026-03-13
**Phase**: Design
**Level**: Enterprise
**Plan 참조**: `docs/pdca/01-plan/features/integration-and-ci.plan.md`

---

## 1. 기술 스택

| 영역 | 기술 | 비고 |
|------|------|------|
| CI 플랫폼 | GitHub Actions | 저장소 기본 자동화 기준 |
| Python 환경 | `uv` + Python 3.12 | `services/myaicoder` 테스트 |
| Node 환경 | Node 20 + pnpm | `apps/vscode-extension` 테스트 |
| 테스트 | pytest / vitest | 기존 테스트 러너 유지 |

## 2. 설계 원칙

1. **기존 명령 재사용**
   - 로컬에서 쓰는 명령을 CI에서도 그대로 사용
2. **언어별 분리**
   - Python과 Node 테스트는 설치/캐시/실패 원인이 다르므로 분리
3. **작은 시작**
   - 초기 워크플로는 lint/test 중심
   - 실제 MCP/LLM 서버가 필요한 테스트는 후속 단계로 분리
4. **문서 우선**
   - 루트 또는 `docs/pdca`에 실행 기준을 남겨 다음 사람이 바로 재현 가능하게 함

## 3. 대상 경로

```text
repo root
├── services/myaicoder/
│   ├── pyproject.toml
│   └── tests/
├── apps/vscode-extension/
│   ├── package.json
│   └── test/
└── .github/workflows/
    └── ci.yml
```

## 4. CI 파이프라인 구조

### 4.1 Trigger

- `push`
- `pull_request`

### 4.2 Jobs

#### Job A: `python-tests`

- checkout
- Python 3.12 setup
- `uv` 설치
- `services/myaicoder` 의존성 동기화
- `uv run pytest tests -q`

#### Job B: `extension-tests`

- checkout
- Node 20 setup
- pnpm setup
- workspace install
- `pnpm --filter myaicoder test`

### 4.3 향후 확장 지점

- `lint-python`
- `lint-extension`
- `mcp-integration`
- `security-scan`

## 5. 로컬 실행 기준

Python:

```bash
cd services/myaicoder
uv run pytest tests -q
```

Extension:

```bash
pnpm --filter myaicoder test
```

## 6. 리스크와 대응

| 리스크 | 대응 |
|--------|------|
| CI 환경에서 의존성 설치 시간 증가 | language별 캐시 사용 |
| MCP/LLM 실서버 없는 테스트 한계 | 초기 CI는 unit/integration-lite까지만 포함 |
| monorepo 루트/하위 경로 혼동 | 문서와 workflow에서 working directory 명시 |

## 7. Check 단계에서 볼 항목

- GitHub Actions 문법과 경로가 올바른가
- 로컬 실행 명령과 CI 명령이 일치하는가
- 테스트 스킵이 의도된 범위에 머무는가
- 저장소 신규 기여자가 문서만 보고 재현 가능한가
