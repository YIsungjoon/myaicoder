# Design: vscode-extension-root-fix

## Overview
- **Feature**: vscode-extension-root-fix
- **Phase**: Design
- **Date**: 2026-04-22

## Architecture Decision

`MYAICODER_API_KEY` 전달 패턴(환경변수)을 `llmUrl` / `modelName`에도 동일하게 적용.
Python의 `AppConfig._apply_env_overrides`는 `MYAICODER_LLM_URL`, `MYAICODER_LLM_MODEL`을 이미 지원하며, env override는 CLI 인수보다 우선 적용됨.

## FR (Functional Requirements)

| ID | 요구사항 | 파일 |
|----|---------|------|
| FR-01 | `buildServeArgs`에서 `--llm-url`, `--model-name` CLI 인수 제거 | `process.ts` |
| FR-02 | `llmUrl` → `MYAICODER_LLM_URL` env var로 전달 | `process.ts` |
| FR-03 | `modelName` → `MYAICODER_LLM_MODEL` env var로 전달 | `process.ts` |
| FR-04 | `getLlmUrl()` 반환 타입 `string \| undefined` (기본값 제거) | `config.ts` |
| FR-05 | `getModelName()` 반환 타입 `string \| undefined` (기본값 제거) | `config.ts` |
| FR-06 | MCP 상태 트리: 미설정 시 `(server default)` 표시 | `mcp-status.ts` |
| FR-07 | 상태바: 미설정 시 `connected` fallback label 사용 | `statusbar.ts` |
| FR-08 | 진단 로그: 미설정 시 `(server default)` 표시 | `extension.ts` |
| FR-09 | config.test.ts: 미설정 시 `undefined` 기대값 | `config.test.ts` |
| FR-10 | process.test.ts: env var 전달 테스트 추가 | `process.test.ts` |

## Interface Changes

### `config.ts`

```typescript
// Before
getModelName(): string  // 기본값 'qwen3.5-27b'
getLlmUrl(): string     // 기본값 'http://localhost:8080'

// After
getModelName(): string | undefined  // 미설정 시 undefined
getLlmUrl(): string | undefined     // 미설정 시 undefined
```

### `process.ts` — `buildServeArgs` 반환값

```typescript
// Before: CLI 인수로 전달
args.push('--llm-url', options.llmUrl)
args.push('--model-name', options.modelName)

// After: 환경변수로 전달 (apiKey 패턴과 동일)
env['MYAICODER_LLM_URL'] = options.llmUrl
env['MYAICODER_LLM_MODEL'] = options.modelName
```

### Display Fallback

| 위치 | 미설정 시 표시 |
|------|-------------|
| `mcp-status.ts` LLM 행 | `LLM: (server default)` |
| `mcp-status.ts` Model 행 | `Model: (server default)` |
| `statusbar.ts` | `$(check) myAiCoder: connected (N tools)` |
| `extension.ts` 진단 | `LLM URL:    (server default)` |

## Python 연동

`AppConfig._apply_env_overrides` (이미 구현됨):
```python
_ENV_OVERRIDES = [
    ("MYAICODER_API_KEY",   "llm.api_key",  "str"),
    ("MYAICODER_LLM_URL",   "llm.base_url", "url"),  # ← 활용
    ("MYAICODER_LLM_MODEL", "llm.model",    "str"),  # ← 활용
]
```
env override는 CLI 인수 로딩 이후 적용되어 최종 우선순위를 가짐.

## Test Coverage

| 테스트 | 검증 내용 |
|--------|---------|
| `config.test.ts: undefined model name` | 미설정 시 `undefined` 반환 |
| `config.test.ts: undefined LLM URL` | 미설정 시 `undefined` 반환 |
| `config.test.ts: configured model name` | 명시 설정 시 값 반환 |
| `process.test.ts: llmUrl via env` | `MYAICODER_LLM_URL` env var 설정 |
| `process.test.ts: modelName via env` | `MYAICODER_LLM_MODEL` env var 설정 |
| `process.test.ts: no CLI args` | `--llm-url`, `--model-name` 인수 없음 |
