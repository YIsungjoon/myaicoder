# Session Handoff - 2026-03-14 (Session 2)

## 1. 현재 완료 상태

완료된 PDCA feature (11개):

| # | Feature | Match Rate | 상태 | 세션 |
|---|---------|-----------|------|------|
| 1 | ai-coder-cli | 95% | completed | 세션 1 (03-13) |
| 2 | mcp-server | 100% | completed | 세션 1 |
| 3 | myaicoder | 99% | completed | 세션 1 |
| 4 | vscode-extension | 99% | archived | 세션 1 |
| 5 | integration-and-ci | 97% | completed | 세션 1 |
| 6 | api-gateway | 100% | completed | 세션 2 (03-14) |
| 7 | model-management | 100% | completed | 세션 3 (이번) |
| 8 | rate-limiting | 99% | completed | 세션 3 |
| 9 | gateway-internal-api | 100% | completed | 세션 3 |
| 10 | integration-testing | 95% | completed | 세션 3 |
| 11 | context-management | 100% | completed | 세션 3 |

평균 Match Rate: **98.5%**

## 2. 이번 세션에서 한 일

### 2.1 CI 첫 실행 검증
- GitHub Actions CI 첫 실행 → Extension Tests 실패 (pnpm 순서 문제)
- `.github/workflows/ci.yml` 수정 → 3/3 통과
- `gh` CLI 설치 + HTTPS 인증

### 2.2 model-management PDCA 완료
- 환경별 이중 전략: prod (DGX 128GB, 3개 Always-on) / dev (24GB, switch)
- 4개 모듈: config, scanner, process, manager (facade pattern)
- 안전 기능: dead process fail-fast, signal handler (zombie prevention), rollback
- 사용자 피드백 3가지 사각지대 반영 (프로세스 분리, dead process, zombie)
- CLI: model {list, switch, status, launch}
- 32개 테스트

### 2.3 rate-limiting PDCA 완료
- Sliding Window Counter 알고리즘
- Dependency(차단) + Middleware(헤더 주입) 분리 패턴
- 메모리 누수 방지 (lazy eviction), 동시성 안전 (await-free)
- 중앙 config/ 디렉토리 도입 (사용자 피드백)
- 역할별 한도: admin 120/분, user 30/분
- 17개 테스트

### 2.4 gateway-internal-api PDCA 완료
- POST /internal/routes/reload — CLI↔Gateway 상태 동기화 고리 완결
- X-Internal-Token 인증, ModelRouter.reload()
- model-management P1 후속 해소
- 6개 테스트

### 2.5 실환경 통합 테스트 (integration-testing) PDCA 완료
- 추론 엔진 전환: vLLM 0.17.1 → llama.cpp 직접 빌드 (Qwen3.5 qwen35 아키텍처)
- CUDA 12.0 → 12.8 업그레이드 (Blackwell GPU compute_120)
- ProcessManager 이중 백엔드 추상화 (llama-cpp / vllm)
- 통합 테스트 20/20 PASS (T1~T4)
- skip 테스트 환경변수 전환 (VLLM_INTEGRATION, MCP_INTEGRATION)
- config/ 실환경 설정 파일 생성 (.gitignore 보호)

### 2.6 context-management PDCA 완료
- Turn 기반 원자적 그루핑 (도구 호출 체인 안전성)
- Sliding Window + 규칙 기반 압축 (LLM 호출 없이, 0ms)
- Oldest-first drop (summary 2000자 초과 시 최신 보존)
- ContextConfig 활성화 (dead config 해소)
- CLI /compact, /tokens 명령
- 22개 테스트

## 3. 현재 기술 기준

### 3.1 테스트 현황

| 서비스 | 결과 |
|--------|------|
| Python (myaicoder) | 120 passed, 4 skipped |
| Gateway | 43 passed |
| Extension | 20 passed |
| **총합** | **183 passed** |
| CI | 3/3 통과 |
| Ruff | All checks passed |

### 3.2 테스트 명령

```bash
# 일반 테스트
cd services/myaicoder && uv run pytest tests -q    # 120 passed, 4 skipped
cd services/gateway && uv run pytest tests -q      # 43 passed
pnpm --filter myaicoder test                        # 20 passed

# 실환경 통합 테스트 (llama.cpp 서버 실행 중일 때)
cd services/myaicoder && VLLM_INTEGRATION=1 uv run pytest tests/test_llm -q
bash scripts/integration_test.sh
```

### 3.3 서버 시작 명령

```bash
# LLM 서버 (llama.cpp)
~/llm-server-env/llama.cpp/build/bin/llama-server \
  --model ~/models/Qwen3.5-9B-Q4_K_M.gguf \
  --host 0.0.0.0 --port 8001 \
  --n-gpu-layers -1 --ctx-size 32768

# Gateway
cd services/gateway
GATEWAY_CONFIG=../../config/gateway.yaml uv run uvicorn app.main:create_app \
  --factory --host 0.0.0.0 --port 8080
```

## 4. 인프라 현황

### 4.1 하드웨어
- GPU: NVIDIA RTX PRO 4000 Blackwell (24GB VRAM)
- Compute Capability: 12.0
- CUDA: 12.8 (/usr/local/cuda-12.8/)

### 4.2 소프트웨어
- 추론 엔진: llama.cpp (직접 빌드, ~/llm-server-env/llama.cpp/)
- vLLM 0.17.1: Qwen3.5 미지원 (사용 안 함)
- llama-cpp-python 0.3.16: Qwen3.5 미지원 (사용 안 함)

### 4.3 모델
- ~/models/Qwen3.5-9B-Q4_K_M.gguf (5.3GB) — 기본 (dev)
- ~/models/Qwen3.5-27B-Q4_K_M.gguf (16GB) — 고품질
- ~/models/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf (18GB) — 코딩 특화

### 4.4 설정 파일
- config/gateway.yaml — Gateway 전체 설정 (API key, rate limit 포함)
- config/models.yaml — 모델 프로필 (backend: llama-cpp)
- .gitignore에 config/*.yaml 추가 (secrets 보호)

## 5. 해소된 리스크

| 리스크 | 해소 방법 |
|--------|----------|
| CI 미실행 | ci.yml 수정 + 3/3 통과 |
| Gateway 실환경 연동 미검증 | llama.cpp + Gateway 실연동 통과 |
| SSE 스트리밍 미검증 | 18 SSE chunks 정상 수신 |
| Model switch E2E 미검증 | launch/switch (9B↔27B) 성공 |
| MCP 실서버 미검증 | stdio 통신, 5개 도구 정상 |
| 추론 엔진 호환성 | llama.cpp 직접 빌드로 해결 |
| 컨텍스트 윈도우 초과 | Turn 기반 압축 구현 |
| CLI↔Gateway 상태 동기화 | internal API 완결 |

## 6. 남아있는 작업

### 6.1 이연된 P2 항목
- Token-based Rate Limiting (응답 파싱 필요)
- 대화 저장/로드 (파일 기반 세션 지속)
- LLM 기반 요약 (규칙 기반 → LLM 호출 압축 업그레이드)
- tiktoken 토큰 카운팅 (chars//4 → 정확한 토큰 수)

### 6.2 다음 피처 후보
- **Marketplace 배포**: VS Code Extension 마켓플레이스 배포
- **Performance Tuning**: Gateway + LLM 성능 최적화
- **Observability**: 분산 로깅 + 메트릭 수집
- **Multi-model Inference**: prod 환경 다중 모델 동시 로드

## 7. 다음 세션에서 먼저 볼 파일

- `~/.claude/projects/.../memory/MEMORY.md`
- `docs/session-handoff-2026-03-14-session2.md` (이 파일)
- `docs/.pdca-status.json`
- `config/gateway.yaml` (실환경 설정)
- `config/models.yaml` (모델 프로필)

## 8. chat_log 기록

이번 세션의 상세 기록:
- `chat_log/020_ci_검증_및_model_management.md`
- `chat_log/021_통합테스트_및_추론엔진_전환.md`
- `chat_log/022_llama_cpp_백엔드_추상화.md`
- `chat_log/023_T3_E2E_model_management.md`
- `chat_log/024_T4_MCP_통합테스트.md`
