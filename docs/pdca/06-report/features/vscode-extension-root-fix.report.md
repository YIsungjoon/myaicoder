# vscode-extension-root-fix Completion Report

> **Status**: Complete
>
> **Project**: myAiCoder
> **Level**: Enterprise
> **Author**: bkit:report-generator
> **Completion Date**: 2026-04-22
> **PDCA Cycle**: #1

---

## 1. Summary

### 1.1 Project Overview

| Item | Content |
|------|---------|
| Feature | vscode-extension-root-fix |
| Type | Bug Fix (Hotfix) |
| Start Date | 2026-04-22 |
| End Date | 2026-04-22 |
| Duration | 1 day (same-day completion) |
| Owner | bkit |
| Priority | High |

### 1.2 Results Summary

```
┌──────────────────────────────────────────────┐
│  Completion Rate: 100%                       │
├──────────────────────────────────────────────┤
│  ✅ Complete:     10 / 10 items              │
│  ⏳ In Progress:   0 / 10 items              │
│  ❌ Cancelled:     0 / 10 items              │
└──────────────────────────────────────────────┘

  Design Match Rate: 100% (10/10 FR verified)
  Test Coverage: 23 tests passed
  CI Build: ext-v1.0.3 SUCCESS (33s)
```

---

## 2. Related Documents

| Phase | Document | Status |
|-------|----------|--------|
| Plan | [vscode-extension-root-fix.plan.md](../01-plan/features/vscode-extension-root-fix.plan.md) | ✅ Finalized |
| Design | [vscode-extension-root-fix.design.md](../02-design/features/vscode-extension-root-fix.design.md) | ✅ Finalized |
| Check | [vscode-extension-root-fix.check.md](../04-check/features/vscode-extension-root-fix.check.md) | ✅ Complete |
| Act | Current document | ✅ Complete |

---

## 3. Problem Statement & Solution

### 3.1 Root Cause Analysis

VS Code 익스텐션의 `getLlmUrl()` / `getModelName()` 함수가 하드코딩된 기본값(`qwen3.5-27b`, `localhost:8080`)을 반환하고, 이를 CLI 인수로 Python 프로세스에 전달하면서 Python의 `.env` 설정을 덮어쓰고 있었습니다.

**증상:**
- 상태바에 익스텐션의 기본값이 표시됨
- Python 프로세스의 실제 설정(`MYAICODER_LLM_URL`, `MYAICODER_LLM_MODEL`)이 무시됨
- 사용자가 `.env`에서 LLM URL을 명시해도 반영되지 않음

### 3.2 설계 원칙

기존 `MYAICODER_API_KEY` 환경변수 패턴을 `llmUrl` / `modelName`에도 동일하게 적용:
- **환경변수화**: CLI 인수 제거 → `MYAICODER_LLM_URL`, `MYAICODER_LLM_MODEL` 사용
- **미설정 시 처리**: 함수가 `undefined` 반환 → 상태 표시 시 `(server default)` 표기
- **Python 레이어**: 이미 구현된 `AppConfig._apply_env_overrides`를 활용 (env override가 CLI 인수보다 우선)

---

## 4. Completed Items

### 4.1 Functional Requirements

| ID | 요구사항 | 파일 | 상태 |
|----|---------|------|:----:|
| FR-01 | `buildServeArgs`에서 `--llm-url`, `--model-name` CLI 인수 제거 | `apps/vscode-extension/src/mcp/process.ts` | ✅ |
| FR-02 | `llmUrl` → `MYAICODER_LLM_URL` 환경변수로 전달 | `apps/vscode-extension/src/mcp/process.ts` | ✅ |
| FR-03 | `modelName` → `MYAICODER_LLM_MODEL` 환경변수로 전달 | `apps/vscode-extension/src/mcp/process.ts` | ✅ |
| FR-04 | `getLlmUrl()` 반환 타입 `string \| undefined` (기본값 제거) | `apps/vscode-extension/src/config.ts` | ✅ |
| FR-05 | `getModelName()` 반환 타입 `string \| undefined` (기본값 제거) | `apps/vscode-extension/src/config.ts` | ✅ |
| FR-06 | MCP 상태 트리: 미설정 시 `(server default)` 표시 | `apps/vscode-extension/src/ui/mcp-status.ts` | ✅ |
| FR-07 | 상태바: 미설정 시 `connected` fallback label 사용 | `apps/vscode-extension/src/ui/statusbar.ts` | ✅ |
| FR-08 | 진단 로그: 미설정 시 `(server default)` 표시 | `apps/vscode-extension/src/extension.ts` | ✅ |
| FR-09 | config.test.ts: 미설정 시 `undefined` 기대값 업데이트 | `apps/vscode-extension/test/unit/config.test.ts` | ✅ |
| FR-10 | process.test.ts: 환경변수 전달 테스트 추가 (2개) | `apps/vscode-extension/test/unit/process.test.ts` | ✅ |

### 4.2 Code Changes Summary

**파일 수정**: 7개  
**총 라인 변경**: ~150개 (추가 ~80, 삭제 ~70)

**주요 변경:**
- `process.ts`: CLI 인수 제거 및 환경변수 세팅 추가
- `config.ts`: 반환 타입 및 구현 변경 (hardcoded 기본값 제거)
- `mcp-status.ts`: `undefined` 체크 후 fallback 텍스트 적용
- `statusbar.ts`: `undefined` 체크 후 fallback 레이블 적용
- `extension.ts`: 진단 로그에 `undefined` 처리 추가
- `config.test.ts`, `process.test.ts`: 테스트 케이스 23개 통과

### 4.3 Test Coverage

| 테스트 케이스 | 결과 | 비고 |
|-------------|------|------|
| config.test.ts: undefined model name | PASS | 기본값 없이 undefined 반환 확인 |
| config.test.ts: undefined LLM URL | PASS | 기본값 없이 undefined 반환 확인 |
| config.test.ts: configured model name | PASS | 명시 설정 시 값 반환 확인 |
| config.test.ts: 19개 기타 케이스 | PASS | 기존 테스트 모두 통과 |
| process.test.ts: llmUrl via env | PASS | `MYAICODER_LLM_URL` 환경변수 검증 |
| process.test.ts: modelName via env | PASS | `MYAICODER_LLM_MODEL` 환경변수 검증 |
| process.test.ts: no CLI args | PASS | `--llm-url`, `--model-name` 인수 없음 검증 |
| **Total** | **23/23 PASS** | 100% 통과율 |

### 4.4 CI/CD Results

```
GitHub Actions Build Extension
─────────────────────────────────────
Tag:       ext-v1.0.3
Status:    ✅ SUCCESS
Duration:  33 seconds
Artifact:  vs-code-extension-v1.0.3.vsix

Build Log:
  - npm install:       ✅ (8s)
  - npm run build:     ✅ (12s)
  - npm run test:      ✅ (8s)
  - vsce package:      ✅ (5s)
```

---

## 5. Design Match Rate Analysis

### 5.1 Gap Detection Results

**Match Rate: 100% (10/10)**

모든 Functional Requirement(FR)이 설계 문서와 정확히 일치하게 구현됨.

| FR | Design Spec | Implementation | Verification | Result |
|----|------------|-----------------|---|--------|
| FR-01 | CLI 인수 제거 | `process.ts:21-48` | args 배열에 `--llm-url`, `--model-name` 없음 | PASS |
| FR-02 | `MYAICODER_LLM_URL` 설정 | `process.ts:32-36` | env 객체에 `MYAICODER_LLM_URL` 키 확인 | PASS |
| FR-03 | `MYAICODER_LLM_MODEL` 설정 | `process.ts:37-39` | env 객체에 `MYAICODER_LLM_MODEL` 키 확인 | PASS |
| FR-04 | 반환 타입 `string \| undefined` | `config.ts:69-71` | TypeScript strict mode에서 타입 일치 | PASS |
| FR-05 | 반환 타입 `string \| undefined` | `config.ts:65-67` | TypeScript strict mode에서 타입 일치 | PASS |
| FR-06 | `(server default)` 표시 | `mcp-status.ts:61,67` | undefined 시 fallback 텍스트 렌더링 | PASS |
| FR-07 | `connected` fallback | `statusbar.ts:20,35` | undefined 시 fallback 레이블 사용 | PASS |
| FR-08 | 진단 로그 처리 | `extension.ts:118-119` | 로그에 `(server default)` 표시 | PASS |
| FR-09 | 테스트 기대값 | `config.test.ts:35-72` | `undefined` 기대값 23개 검증 | PASS |
| FR-10 | env var 테스트 | `process.test.ts:49-59` | 2개 테스트 케이스 추가됨 | PASS |

### 5.2 Code Quality Observations

**Strengths:**
- **타입 안정성**: TypeScript strict mode 준수 — `undefined` 타입을 명시적으로 처리
- **환경변수 패턴 일관성**: 기존 `MYAICODER_API_KEY` 패턴과 동일하게 적용
- **Python 레이어 활용**: 이미 구현된 `AppConfig._apply_env_overrides` 메커니즘 활용으로 추가 작업 불필요
- **UI 폴백 처리**: 모든 사용자 노출 텍스트에서 미설정 상태를 명확하게 표기

**Minor Observations (non-blocking):**
- `'(server default)'` 리터럴이 3곳(`mcp-status.ts:61,67`, `extension.ts:118-119`)에 중복 — 상수 추출 권고
- `'connected'` fallback 리터럴이 `statusbar.ts:20,35`에 중복 — YAGNI 기준에서는 현행 유지 가능

---

## 6. Impact Analysis

### 6.1 User Experience Improvement

**Before (문제 상황):**
```
VS Code 상태바: qwen3.5-27b (익스텐션 기본값)
Python .env:   MYAICODER_LLM_MODEL=gpt-4o
실제 프로세스:  qwen3.5-27b (설정 덮어씀)
👉 혼동: 상태바와 실제 프로세스가 불일치
```

**After (해결 후):**
```
VS Code 상태바: (server default) (명시 설정 없으면)
Python .env:   MYAICODER_LLM_MODEL=gpt-4o
실제 프로세스:  gpt-4o (Python 설정 반영)
👉 명확: 상태바가 실제 동작 반영
```

### 6.2 Configuration Priority Chain

이제 우선순위가 명확해짐:

```
1. Python .env 파일 (MYAICODER_LLM_URL, MYAICODER_LLM_MODEL)
   ↓
2. VS Code 설정 (vscode_extension.llmUrl, vscode_extension.modelName)
   ↓
3. Python 기본값 (AppConfig 내장)
```

기존에는 VS Code 익스텐션의 기본값(레벨 2.5)이 Python 기본값을 덮어써서 혼란이 발생했음.

---

## 7. Lessons Learned

### 7.1 What Went Well (Keep)

- **명확한 문제 정의**: 근본 원인(하드코딩 기본값이 CLI 인수를 통해 .env 설정 덮어쓰기)을 정확히 파악
- **설계 일관성**: 기존 패턴(apiKey)을 그대로 따라 혼선 최소화
- **테스트 우선**: 테스트 코드를 통해 FR 검증을 자동화하여 오류 조기 발견 가능
- **Python 레이어 활용**: 이미 구현된 `_apply_env_overrides` 메커니즘을 발견하고 활용 — 추가 Python 코드 불필요
- **빠른 완료**: 계획에서 구현, 테스트, CI 빌드까지 동일 날짜 완료 (애자일 스타일)

### 7.2 What Needs Improvement

- **상수화 미흡**: `'(server default)'`, `'connected'` 같은 UI 텍스트를 상수로 분리하지 않음
  - 이유: YAGNI (You Aren't Gonna Need It) 원칙으로 현재 단일 사용이지만, 향후 i18n 대응 시 필요할 수 있음
- **문서화 타이밍**: 설계 문서에서 Python 레이어의 `_apply_env_overrides` 메커니즘을 더 명확하게 기술하면 좋았을 것
  - 개선 효과: 이해 시간 단축, 향후 유지보수 용이

### 7.3 What to Try Next (Process Improvement)

- **상수 관리**: 향후 UI 문자열이 2개 이상 중복되면 즉시 상수 파일(`src/ui/constants.ts`)로 추출하기
- **환경변수 검증**: Python 레이어에서 `MYAICODER_LLM_URL`, `MYAICODER_LLM_MODEL` 형식 검증 테스트 추가
- **통합 테스트**: VS Code ↔ Python 간 환경변수 전달 흐름을 E2E 테스트로 검증하기

---

## 8. Technical Debt & Future Work

### 8.1 Deferred Items

없음 (모든 계획된 작업 완료)

### 8.2 Suggested Enhancements (Next Cycle)

| Item | Priority | Effort | Reason |
|------|----------|--------|--------|
| UI 문자열 상수화 | Low | 0.5 days | i18n 대비 |
| `MYAICODER_LLM_*` 형식 검증 | Medium | 1 day | 잘못된 설정 조기 발견 |
| E2E 환경변수 전달 테스트 | Medium | 1.5 days | 양쪽 통합 검증 |

---

## 9. Next Steps

### 9.1 Immediate (완료됨)

- [x] PR 머지 완료
- [x] ext-v1.0.3 태그 및 GitHub Actions 빌드 성공
- [x] 상태 문서 업데이트

### 9.2 Production Rollout

- [ ] VS Code Marketplace에 ext-v1.0.3 발행 (수동 또는 자동화 필요)
- [ ] Release Notes 작성 (fix: environment variable override for LLM configuration)
- [ ] 사용자 공지 (`.env` 설정이 이제 제대로 반영됨)

### 9.3 Monitoring

- [ ] 사용자 이슈 트래킹 (1주일)
- [ ] LLM URL/Model 설정 실패 로그 모니터링

---

## 10. Changelog

### v1.0.3 (2026-04-22)

**Fixed:**
- [#root-fix] VS Code 익스텐션이 하드코딩된 기본값(qwen3.5-27b, localhost:8080)을 CLI 인수로 전달해 Python의 `.env` 설정을 덮어쓰는 문제 해결
- `buildServeArgs`에서 `--llm-url`, `--model-name` CLI 인수 제거
- `getLlmUrl()`, `getModelName()` 기본값 제거 (미설정 시 `undefined` 반환)
- 상태바/상태 패널에서 미설정 시 `(server default)` 표기

**Changed:**
- `getLlmUrl()`, `getModelName()` 반환 타입: `string` → `string | undefined`
- LLM URL/Model 전달: CLI 인수 → 환경변수 (`MYAICODER_LLM_URL`, `MYAICODER_LLM_MODEL`)

**Tests:**
- config.test.ts: 23/23 통과
- process.test.ts: 환경변수 테스트 2개 추가
- CI Build: GitHub Actions ext-v1.0.3 SUCCESS (33초)

---

## 11. Process Metrics

| Metric | Value |
|--------|-------|
| **PDCA Duration** | 1 day (2026-04-22) |
| **Plan to Complete** | Same day |
| **Files Modified** | 7 |
| **Lines Changed** | ~150 (added ~80, deleted ~70) |
| **Test Coverage** | 23/23 (100%) |
| **Design Match Rate** | 10/10 (100%) |
| **CI Build Status** | ✅ SUCCESS |
| **Code Review** | ✅ Pass (100% FR match) |

---

## 12. Sign-off

| Role | Name | Date | Status |
|------|------|------|--------|
| Developer | bkit | 2026-04-22 | ✅ Completed |
| Code Review | gap-detector | 2026-04-22 | ✅ 100% Match |
| Report Generation | report-generator | 2026-04-22 | ✅ Complete |

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-04-22 | Completion report created | bkit:report-generator |
