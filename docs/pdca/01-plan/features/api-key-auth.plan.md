# Plan: API Key Auth — CLI/Extension 인증 지원

- **Feature**: api-key-auth
- **Level**: Enterprise
- **Created**: 2026-03-15
- **Status**: Draft

---

## 1. 배경 및 목표

### 1.1 문제
DGX Gateway는 API 키 인증(`Authorization: Bearer <key>`)을 요구하지만, CLI의 `VLLMProvider`가 `api_key="not-needed"`로 하드코딩되어 있어 **403 Forbidden** 에러가 발생한다.

**영향 범위:**
- `VLLMProvider.__init__()` — `api_key="not-needed"` 하드코딩 (L23)
- `VLLMProvider._raw_chat()` — httpx 직접 호출 시 Authorization 헤더 미전송 (L109-113)
- `cli.py` — `VLLMProvider` 생성 시 `api_key` 미전달 (L62-66)
- `cli.py serve` — agentic 모드에서도 `api_key` 미전달 (L478-482)
- `AppConfig.LLMConfig` — `api_key` 필드 없음

### 1.2 목표
- CLI와 Extension이 DGX Gateway에 API 키로 인증하여 정상 접속
- 기존 로컬 모드 (인증 불필요) 호환성 유지
- API 키를 안전하게 관리 (코드에 하드코딩 금지)

### 1.3 핵심 가치
| 가치 | 설명 |
|------|------|
| **DGX 접속** | 403 에러 해결, 원격 Gateway 인증 |
| **하위 호환** | 로컬 모드에서는 기존처럼 `api_key` 없이 동작 |
| **보안** | API 키는 config 파일/환경변수로만 관리 |

---

## 2. 범위 (Scope)

### 2.1 In-Scope

| # | 작업 | 설명 |
|---|------|------|
| S1 | `LLMConfig`에 `api_key` 필드 추가 | `core/config.py` AppConfig 확장 |
| S2 | `VLLMProvider` api_key 전달 | 하드코딩 제거, config에서 읽기 |
| S3 | `_raw_chat()` Authorization 헤더 | httpx 직접 호출 시 Bearer 토큰 전송 |
| S4 | CLI `--api-key` 옵션 | 커맨드라인에서 오버라이드 가능 |
| S5 | `serve` 명령 api_key 전달 | agentic 모드에서도 인증 지원 |
| S6 | Extension `apiKey` 설정 | VS Code settings에 `myaicoder.apiKey` 추가 |
| S7 | config.json 예시 업데이트 | `config.json.example`에 `api_key` 필드 추가 |

### 2.2 Out-of-Scope
- Gateway 코드 수정 (Gateway는 정상 동작)
- YAML 환경변수 치환 (P2로 별도 관리)
- API 키 발급/관리 UI

---

## 3. 기술 분석

### 3.1 현재 인증 흐름 (실패)
```
CLI (api_key="not-needed")
  → VLLMProvider → AsyncOpenAI(api_key="not-needed")
    → Gateway: Authorization: Bearer not-needed
      → AuthStore.authenticate("not-needed") → hash 불일치 → 403
```

### 3.2 목표 인증 흐름
```
CLI (--api-key 또는 config.json의 llm.api_key)
  → VLLMProvider → AsyncOpenAI(api_key="myaicoder-dev-key-2026")
    → Gateway: Authorization: Bearer myaicoder-dev-key-2026
      → AuthStore.authenticate() → hash 일치 → 200 OK
```

### 3.3 API 키 우선순위 (3-tier fallback)
1. CLI 옵션: `--api-key <key>` (최우선)
2. 환경변수: `MYAICODER_API_KEY`
3. Config 파일: `myaicoder.json` → `llm.api_key`
4. 기본값: `"not-needed"` (로컬 모드 호환)

### 3.4 수정 대상 파일

| # | 파일 | 변경 내용 |
|---|------|----------|
| F1 | `services/myaicoder/src/myaicoder/core/config.py` | `LLMConfig.api_key` 필드 추가 |
| F2 | `services/myaicoder/src/myaicoder/llm/vllm_provider.py` | api_key 파라미터 활용, _raw_chat에 헤더 추가 |
| F3 | `services/myaicoder/src/myaicoder/cli.py` | `--api-key` 옵션, VLLMProvider에 전달 |
| F4 | `apps/vscode-extension/src/config.ts` | `getApiKey()` 메서드 추가 |
| F5 | `apps/vscode-extension/src/mcp/process.ts` | `--api-key` 옵션 전달 |
| F6 | `apps/vscode-extension/package.json` | `myaicoder.apiKey` 설정 항목 추가 |
| F7 | `config/config.json.example` | 예시 업데이트 |

---

## 4. 성공 기준

| # | 기준 | 측정 방법 |
|---|------|----------|
| C1 | DGX Gateway 인증 성공 | `myaicoder --api-key <key> --vllm-url http://DGX:8080/v1` → 200 OK |
| C2 | config.json으로 인증 | `llm.api_key` 설정 후 `myaicoder chat` → 200 OK |
| C3 | 로컬 모드 호환 | api_key 미설정 시 `"not-needed"`로 기존처럼 동작 |
| C4 | Extension 인증 | VS Code 설정에서 `apiKey` 입력 후 DGX 접속 성공 |
| C5 | 기존 테스트 통과 | 241/241 PASS, 0 regression |

---

## 5. 리스크

| # | 리스크 | 대응 |
|---|--------|------|
| R1 | API 키가 config.json에 평문 저장 | .gitignore에 myaicoder.json 포함 확인, 환경변수 대안 제공 |
| R2 | _raw_chat의 httpx와 AsyncOpenAI의 이중 경로 | 둘 다 같은 api_key 사용하도록 통일 |

---

## 6. 산출물

| # | 파일 | 설명 |
|---|------|------|
| D1 | `core/config.py` 수정 | LLMConfig.api_key 필드 |
| D2 | `llm/vllm_provider.py` 수정 | api_key 전달 + _raw_chat 헤더 |
| D3 | `cli.py` 수정 | --api-key 옵션 + 환경변수 + 전달 |
| D4 | `apps/vscode-extension/src/config.ts` 수정 | getApiKey() |
| D5 | `apps/vscode-extension/src/mcp/process.ts` 수정 | --api-key 전달 |
| D6 | `apps/vscode-extension/package.json` 수정 | apiKey 설정 |
| D7 | `config/config.json.example` 수정 | api_key 예시 |
