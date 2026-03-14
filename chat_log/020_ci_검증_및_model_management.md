# 020. CI 검증 및 model-management PDCA 완료

**기록 시점**: 2026-03-14
**세션**: 2026-03-14 (이전 세션 handoff 이후)

---

## 1. CI 첫 실행 검증

### 1.1 첫 CI 실행 (실패)
- `gh` CLI 설치 및 HTTPS 인증 완료
- CI 실행 결과: Python Tests ✓, Gateway Tests ✓, **Extension Tests ✗**
- 원인: `pnpm/action-setup`이 `setup-node` 뒤에 실행됨 → pnpm 바이너리 없음

### 1.2 CI 수정 및 재실행 (성공)
- `.github/workflows/ci.yml`: pnpm setup을 Node setup보다 먼저 실행하도록 순서 변경
- 재실행 결과: 3개 job 모두 통과 (Python 22s, Gateway 14s, Extension 19s)

---

## 2. model-management PDCA 전체 사이클

### 2.1 Plan
- 사용자 요구: 모델을 변경하면서 사용할 수 있는 기능
- 환경별 이중 전략 결정:
  - **DGX Spark (prod, 128GB)**: 3개 모델 Always-on, Gateway 즉시 라우팅
  - **Dev Desktop (dev, 24GB)**: 1개 모델, CLI `model switch`로 stop→start 전환

### 2.2 Design
- 4개 모듈: config.py, scanner.py, process.py, manager.py
- CLI: model {list, switch, status, launch} 서브커맨드
- 사용자 리뷰에서 3가지 사각지대 발견 및 설계 반영:
  - **프로세스 메모리 분리**: CLI↔Gateway 간 HTTP 내부 API로 IPC
  - **Dead Process Fail-fast**: returncode 체크로 즉시 실패
  - **Zombie Process 방지**: signal handler 설치 (SIGINT/SIGTERM)

### 2.3 Do (구현)
- `services/myaicoder/src/myaicoder/models/` — 4개 모듈 신규 생성
- `cli.py` — model 서브커맨드 그룹 추가
- `models.yaml.example` — dev/prod 설정 예시
- `pyproject.toml` — pyyaml 의존성 추가
- 테스트: 32개 신규 (전체 99 passed, 3 skipped)

### 2.4 Check (Gap 분석)
- 초기 Match Rate: 98% (Gap 1건: vLLM 바이너리 사전 검증)
- 사용자 피드백으로 `shutil.which()` 사전 검증 추가
- 최종 Match Rate: **100%**

### 2.5 Report
- 완료 보고서 생성: `docs/pdca/06-report/features/model-management.report.md`
- CI 재검증: 3개 job 모두 통과

---

## 3. rate-limiting PDCA 시작

### 3.1 Plan 작성
- Origin: api-gateway FR-08 (P2에서 승격)
- 알고리즘: Sliding Window Counter
- 역할별 한도: admin 120/분, user 30/분
- 사용자 피드백: **중앙 Config 제어판** (`config/` 디렉토리)
  - 모든 설정 파일을 프로젝트 루트 `config/`에 중앙 집중
  - 운영자가 한 곳에서 전체 시스템 설정 제어

---

## 4. 현재 상태 요약

| Feature | Match Rate | Status |
|---------|-----------|--------|
| ai-coder-cli | 95% | completed |
| mcp-server | 100% | completed |
| myaicoder | 99% | completed |
| vscode-extension | 99% | archived |
| integration-and-ci | 97% | completed |
| api-gateway | 100% | completed |
| **model-management** | **100%** | **completed** |
| **rate-limiting** | - | **plan 완료** |

### 테스트 현황
- Python (myaicoder): 99 passed, 3 skipped
- Gateway: 20 passed
- Extension: 20 passed
- CI: 3개 job 모두 통과
