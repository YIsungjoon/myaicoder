# myAiCoder 로드맵 — 2026년 3월~

**작성**: 2026-03-14
**기준**: 11개 PDCA 피처 완료, 핵심 파이프라인 동작

---

## 현재 위치

```
Core System ✅ → Gateway ✅ → Model Mgmt ✅ → Intelligence ✅ → QA ✅
                                                                    │
                                                              ── 여기 ──
```

핵심 기능 모두 구현 완료. 이제 **제품화 + 고도화 + 운영** 단계.

---

## Track A: 사용자 경험(UX) 완성 및 제품화

> 사용자가 직접 체감하는 불편함을 제거하고, 세상에 내놓는다.

### A-1. 대화 저장/로드 (Conversation Persistence)

**목적**: IDE를 껐다 켜도 이전 대화 + 컨텍스트 압축 상태 유지

| 항목 | 내용 |
|------|------|
| 저장소 | SQLite 또는 JSON 파일 (~/.config/myaicoder/sessions/) |
| 저장 대상 | 대화 히스토리, summary, compression_count |
| CLI 명령 | `/save`, `/load`, `/sessions` (목록) |
| 자동 저장 | 종료 시 자동 저장 (opt-in) |
| 의존 | context-management (Turn 구조 활용) |
| 우선순위 | **높음** — context-management 직후 자연스러운 연장 |

### A-2. Marketplace 배포

**목적**: VS Code Extension 공식 배포

| 항목 | 내용 |
|------|------|
| 패키징 | vsce package (.vsix) |
| 필수 작업 | 아이콘, README, CHANGELOG, 라이선스 |
| 보안 검토 | API key 노출 방지, 권한 최소화 |
| 배포 대상 | VS Code Marketplace |
| 의존 | vscode-extension 안정화 완료 |
| 우선순위 | **중간** — 내부 사용 안정화 후 |

---

## Track B: 에이전트 능력 극대화

> 단순 파일 읽기를 넘어, 복잡한 추론과 자원 정밀 제어.

### B-1. 고급 MCP 도구 확장

**목적**: 1인 게임 개발자/범용 앱 개발 지원을 위한 강력한 도구

| 도구 | 설명 | 복잡도 |
|------|------|--------|
| 터미널 명령 실행 | Bash 도구 고도화 (타임아웃, 샌드박싱) | 중 |
| AST 코드 분석 | Python/JS AST 파싱 → 구조 분석 | 높 |
| 컴파일 에러 피드백 | 빌드 에러 파싱 → LLM에 피드백 루프 | 높 |
| 웹 검색/브라우징 | 문서 검색 → 컨텍스트 주입 | 중 |
| 의존 | MCP 서버 (이미 동작) |
| 우선순위 | **중간** — 사용 사례에 따라 선택적 |

### B-2. Token-based Rate Limiting

**목적**: 요청 횟수(RPM) → 실제 토큰 소비량 기반 제한

| 항목 | 내용 |
|------|------|
| 방식 | LLM 응답의 usage.total_tokens를 파싱하여 누적 |
| 한도 | 사용자별 일/월 토큰 할당량 |
| 구현 위치 | Gateway proxy.py (응답 파싱) + rate_limiter.py 확장 |
| 의존 | rate-limiting (이미 완료), Gateway 로깅 |
| 우선순위 | **낮음** — RPM 제한으로 현재 충분 |

---

## Track C: 엔터프라이즈 운영 및 최적화

> 시스템 내부를 투명하게 들여다보고, 극한의 성능을 달성.

### C-1. Observability (로깅/메트릭)

**목적**: Gateway 트래픽, LLM 응답 시간, 메모리 사용량 시각화

| 항목 | 내용 |
|------|------|
| 스택 | OpenTelemetry + Prometheus + Grafana |
| 메트릭 | TTFT, 요청/초, 토큰/초, GPU 메모리, 에러율 |
| 로깅 | structlog → OTLP exporter |
| 대시보드 | Grafana (로컬 또는 클라우드) |
| 우선순위 | **중간** — 다중 사용자 운영 시 필수 |

### C-2. Performance Tuning

**목적**: Blackwell GPU + CUDA 12.8 + llama.cpp 조합 최적화

| 항목 | 내용 |
|------|------|
| KV Cache | 크기 조정, 재사용 전략 |
| 배치 사이즈 | 동시 요청 처리 최적화 |
| Flash Attention | llama.cpp --flash-attn 활성화 |
| TTFT 최적화 | prompt caching, speculative decoding |
| 벤치마크 | 토큰/초, TTFT, 메모리 프로파일링 |
| 우선순위 | **낮음** — 현재 성능 충분, 다중 사용자 시 필요 |

---

## 권장 실행 순서

```
즉시 (다음 세션):
  A-1. 대화 저장/로드 ← context-management 직후, 가장 자연스러운 연장

이후 (우선순위순):
  B-1. 고급 MCP 도구 ← 에이전트 실용성 극대화
  A-2. Marketplace 배포 ← 내부 안정화 후
  C-1. Observability ← 다중 사용자 운영 준비
  B-2. Token Rate Limiting ← 필요 시
  C-2. Performance Tuning ← 필요 시
```

---

## 참고: 완료된 피처 (11개)

| # | Feature | Match Rate |
|---|---------|-----------|
| 1 | ai-coder-cli | 95% |
| 2 | mcp-server | 100% |
| 3 | myaicoder | 99% |
| 4 | vscode-extension | 99% |
| 5 | integration-and-ci | 97% |
| 6 | api-gateway | 100% |
| 7 | model-management | 100% |
| 8 | rate-limiting | 99% |
| 9 | gateway-internal-api | 100% |
| 10 | integration-testing | 95% |
| 11 | context-management | 100% |
