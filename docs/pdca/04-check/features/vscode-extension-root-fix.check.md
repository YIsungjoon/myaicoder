# Check: vscode-extension-root-fix

## Overview
- **Feature**: vscode-extension-root-fix
- **Phase**: Check (Gap Analysis)
- **Date**: 2026-04-22
- **Analyst**: bkit:gap-detector
- **Match Rate**: **100% (10/10)**

## FR Verification

| FR | 요구사항 | 파일 | 상태 |
|----|---------|------|:----:|
| FR-01 | `--llm-url`, `--model-name` CLI 인수 제거 | `process.ts:21-48` | PASS |
| FR-02 | `llmUrl` → `MYAICODER_LLM_URL` env var | `process.ts:32-36` | PASS |
| FR-03 | `modelName` → `MYAICODER_LLM_MODEL` env var | `process.ts:37-39` | PASS |
| FR-04 | `getLlmUrl()` 반환 타입 `string \| undefined` | `config.ts:69-71` | PASS |
| FR-05 | `getModelName()` 반환 타입 `string \| undefined` | `config.ts:65-67` | PASS |
| FR-06 | MCP 상태 트리 `(server default)` 표시 | `mcp-status.ts:61,67` | PASS |
| FR-07 | 상태바 `connected` fallback | `statusbar.ts:20,35` | PASS |
| FR-08 | 진단 로그 `(server default)` 표시 | `extension.ts:118-119` | PASS |
| FR-09 | config.test.ts `undefined` 기대값 | `config.test.ts:35-72` | PASS |
| FR-10 | process.test.ts env var 테스트 추가 | `process.test.ts:49-59` | PASS |

## Gap 목록

없음 (0건)

## 비고 (non-blocking)

- `'(server default)'` 리터럴이 3곳(`mcp-status.ts:61,67`, `extension.ts:118-119`)에 중복 — 상수 추출 권고 (YAGNI 기준 선택적)
- `'connected'` fallback 리터럴이 `statusbar.ts:20,35`에 중복 — 동일하게 상수 추출 가능

## 결론

Match Rate 100% — `/pdca report` 진행 가능
