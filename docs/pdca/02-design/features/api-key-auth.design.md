# Design: API Key Auth — CLI/Extension 인증 지원

- **Feature**: api-key-auth
- **Level**: Enterprise
- **Created**: 2026-03-16
- **Plan Reference**: `docs/pdca/01-plan/features/api-key-auth.plan.md`

---

## 1. 설계 개요

CLI와 VS Code Extension이 DGX Gateway의 API 키 인증을 통과할 수 있도록 `api_key`를 설정/전달하는 경로를 추가한다. 기존 로컬 모드 (인증 불필요)와의 하위 호환성을 유지한다.

### 1.1 산출물 매핑

| # | 산출물 | Plan 참조 | 설계 섹션 |
|---|--------|----------|----------|
| D1 | `core/config.py` 수정 | S1 | §2 |
| D2 | `llm/vllm_provider.py` 수정 | S2, S3 | §3 |
| D3 | `cli.py` 수정 | S4, S5 | §4 |
| D4 | `apps/vscode-extension/src/config.ts` 수정 | S6 | §5 |
| D5 | `apps/vscode-extension/src/mcp/process.ts` 수정 | S6 | §5 |
| D6 | `apps/vscode-extension/src/mcp/client.ts` 수정 | S6 | §5 |
| D7 | `apps/vscode-extension/package.json` 수정 | S6 | §5 |
| D8 | `config/config.json.example` 수정/생성 | S7 | §6 |

---

## 2. D1: core/config.py — LLMConfig에 api_key 필드 추가

### 2.1 변경 내용

`LLMConfig` dataclass에 `api_key` 필드를 추가한다.

```python
@dataclass
class LLMConfig:
    provider: str = "vllm"
    base_url: str = "http://localhost:8080/v1"
    model: str = "qwen3.5-9b"
    temperature: float = 0.0
    max_tokens: int = 8192
    api_key: str = "not-needed"  # NEW: Gateway 인증용 API 키
```

### 2.2 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D1-1 | 필드 이름 | `api_key` (OpenAI SDK와 동일한 명명) |
| D1-2 | 기본값 | `"not-needed"` — 로컬 모드 하위 호환 |
| D1-3 | 로드 경로 | `AppConfig.load()` → `myaicoder.json` → `llm.api_key` |
| D1-4 | 환경변수 | `MYAICODER_API_KEY` 환경변수 지원 (config보다 우선) |

### 2.3 환경변수 지원

`AppConfig.load()` 내에서 환경변수 오버라이드를 추가한다:

```python
import os

# After loading from file
env_api_key = os.environ.get("MYAICODER_API_KEY", "").strip()
if env_api_key:
    config.llm.api_key = env_api_key
```

### 2.4 엣지 케이스

| # | 상황 | 대응 |
|---|------|------|
| EC-D1-A | api_key가 빈 문자열 | `"not-needed"`로 fallback |
| EC-D1-B | 환경변수 + config 둘 다 설정 | 환경변수 우선 |

---

## 3. D2: llm/vllm_provider.py — api_key 활용

### 3.1 변경 내용

두 곳을 수정한다:
1. `__init__()`: api_key 저장 (이미 파라미터 있으나 기본값 변경)
2. `_raw_chat()`: httpx 요청 시 Authorization 헤더 추가

### 3.2 __init__ 변경

```python
def __init__(
    self,
    base_url: str = "http://localhost:8080/v1",
    model: str = "Qwen3.5-27B-Q4_0.gguf",
    api_key: str = "not-needed",
    max_tokens: int = 8192,
):
    self.model = model
    self.max_tokens = max_tokens
    self.base_url = base_url
    self.api_key = api_key  # NEW: 저장
    self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
```

### 3.3 _raw_chat 변경

```python
async def _raw_chat(self, messages: list[dict], kwargs: dict) -> dict:
    headers = {}
    if self.api_key and self.api_key.strip() and self.api_key != "not-needed":
        headers["Authorization"] = f"Bearer {self.api_key}"

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,  # NEW
        )
```

### 3.4 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D2-1 | self.api_key 저장 | `__init__`에서 인스턴스 변수로 저장 |
| D2-2 | AsyncOpenAI 전달 | 기존과 동일 — `AsyncOpenAI(api_key=api_key)` |
| D2-3 | _raw_chat 헤더 | `api_key != "not-needed"`일 때만 Bearer 헤더 추가 |
| D2-4 | 조건부 헤더 | 로컬 모드에서는 헤더 미전송 (기존 동작 유지) |
| D2-5 | 빈 문자열 방어 | `self.api_key.strip()` — 빈 문자열/공백만 있는 경우 `Bearer ` 헤더 전송 방지 |

### 3.5 엣지 케이스

| # | 상황 | 대응 |
|---|------|------|
| EC-D2-A | api_key="not-needed"로 DGX 접속 | 기존과 동일하게 403 발생 — 사용자가 api_key 설정 필요 |
| EC-D2-B | AsyncOpenAI와 _raw_chat의 키 불일치 | 동일한 self.api_key를 사용하므로 불일치 없음 |
| EC-D2-C | api_key가 빈 문자열 `""` 또는 공백 `"  "` | `.strip()` 체크로 `Bearer ` 빈 헤더 전송 방지, `"not-needed"` fallback |

---

## 4. D3: cli.py — --api-key 옵션 추가

### 4.1 main() 변경

```python
@click.group(invoke_without_command=True)
@click.option("--model", default=None, help="Model name")
@click.option("--vllm-url", default=None, help="vLLM server URL")
@click.option("--api-key", default=None, help="API key for Gateway authentication")  # NEW
@click.option("--no-stream", is_flag=True)
@click.option("--no-tools", is_flag=True)
@click.option("--verbose", is_flag=True)
@click.option("-p", "--prompt", default=None)
@click.version_option(version=__version__)
@click.pass_context
def main(ctx, model, vllm_url, api_key, no_stream, no_tools, verbose, prompt):
    ...
    asyncio.run(_run_chat(model, vllm_url, api_key, no_stream, no_tools, verbose, prompt))
```

### 4.2 _run_chat() 변경

```python
async def _run_chat(
    model, vllm_url, api_key, no_stream, no_tools, verbose, prompt,
):
    config = AppConfig.load()

    # CLI overrides
    if model:
        config.llm.model = model
    if vllm_url:
        config.llm.base_url = vllm_url
    if api_key:
        config.llm.api_key = api_key

    llm = VLLMProvider(
        base_url=config.llm.base_url,
        model=config.llm.model,
        api_key=config.llm.api_key,  # NEW
        max_tokens=config.llm.max_tokens,
    )
```

### 4.3 serve 명령 변경

```python
@main.command()
@click.option("--api-key", default=None, help="API key for Gateway authentication")  # NEW
...
def serve(transport, port, allow_bash, working_dir, max_concurrent, agentic, llm_url, model_name, api_key):
    ...
    if agentic:
        config = AppConfig.load()
        base_url = llm_url or config.llm.base_url
        model = model_name or config.llm.model
        resolved_api_key = api_key or config.llm.api_key  # NEW
        llm_provider = VLLMProvider(
            base_url=base_url,
            model=model,
            api_key=resolved_api_key,  # NEW
            max_tokens=config.llm.max_tokens,
        )
```

### 4.4 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D3-1 | CLI 옵션 | `--api-key` (main, serve 둘 다) |
| D3-2 | 우선순위 | CLI 옵션 > 환경변수 > config 파일 > 기본값 |
| D3-3 | main() 전달 | `_run_chat()`에 api_key 파라미터 추가 |
| D3-4 | VLLMProvider 전달 | `api_key=config.llm.api_key` |
| D3-5 | serve 전달 | agentic 모드에서도 api_key 전달 |

### 4.5 엣지 케이스

| # | 상황 | 대응 |
|---|------|------|
| EC-D3-A | --api-key 없이 DGX URL 사용 | config/환경변수에서 읽음, 없으면 "not-needed" → 403 (예상된 동작) |

---

## 5. D4/D5/D6/D7: VS Code Extension 수정

### 5.1 D7: package.json — apiKey 설정 추가

`contributes.configuration.properties`에 추가:

```json
"myaicoder.apiKey": {
  "type": "string",
  "default": "",
  "scope": "machine",
  "description": "API key for Gateway authentication (leave empty for local mode)"
}
```

### 5.1.1 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D7-1 | 설정 키 | `myaicoder.apiKey` |
| D7-2 | 기본값 | `""` (빈 문자열 = 로컬 모드) |
| D7-3 | 타입 | `string` |
| D7-4 | scope | `"machine"` — 워크스페이스 설정(.vscode/settings.json) 저장 차단, 글로벌 설정만 허용 (Git 커밋 보안 사고 방지) |

### 5.2 D4: config.ts — getApiKey() 추가

```typescript
getApiKey(): string {
  return this.get<string>('apiKey') || '';
}
```

### 5.2.1 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D4-1 | 메서드 | `getApiKey(): string` |
| D4-2 | 반환값 | 설정값 또는 빈 문자열 |

### 5.3 D5: process.ts — --api-key 인자 추가

`buildServeArgs`에 `apiKey` 옵션 추가:

```typescript
export function buildServeArgs(options: {
  allowBash?: boolean;
  maxConcurrent?: number;
  enableAgentic?: boolean;
  llmUrl?: string;
  modelName?: string;
  workingDir?: string;
  apiKey?: string;  // NEW
}): string[] {
  const args = ['serve'];
  ...
  if (options.apiKey) {
    args.push('--api-key', options.apiKey);
  }
  ...
  return args;
}
```

### 5.3.1 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D5-1 | 옵션 이름 | `apiKey?: string` |
| D5-2 | CLI 인자 | `--api-key <value>` |
| D5-3 | 조건부 전달 | 빈 문자열이면 전달 안 함 (로컬 모드) |

### 5.4 D6: client.ts — apiKey 전달

`connect()` 메서드의 `buildServeArgs` 호출에 apiKey 추가:

```typescript
async connect(): Promise<void> {
  const execPath = await this.config.resolveExecutablePath();
  const llmUrl = this.config.getLlmUrl();
  const apiKey = this.config.getApiKey();  // NEW
  const cwd = this.config.getWorkspaceFolder();
  const args = buildServeArgs({
    allowBash: this.config.get<boolean>('allowBash'),
    maxConcurrent: this.config.get<number>('maxConcurrent'),
    enableAgentic: this.config.get<boolean>('enableAgentic'),
    llmUrl: llmUrl ? `${llmUrl.replace(/\/+$/, '')}/v1` : undefined,
    modelName: this.config.getModelName(),
    workingDir: cwd ?? undefined,
    apiKey: apiKey || undefined,  // NEW
  });
```

### 5.4.1 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D6-1 | config 호출 | `this.config.getApiKey()` |
| D6-2 | 빈 문자열 처리 | `apiKey \|\| undefined` — 빈 문자열이면 undefined로 전달 → buildServeArgs에서 생략 |

---

## 6. D8: config/config.json.example

### 6.1 파일 내용

**경로**: `config/config.json.example`

```json
{
  "llm": {
    "provider": "vllm",
    "base_url": "http://localhost:8080/v1",
    "model": "qwen3.5-9b",
    "api_key": "not-needed",
    "max_tokens": 8192
  },
  "tools": {
    "enabled": true
  },
  "context": {
    "max_tokens": 32768
  }
}
```

### 6.1.1 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D8-1 | api_key 필드 | `"not-needed"` 기본값으로 예시 제공 |
| D8-2 | 주석 | JSON은 주석 미지원 → README에서 설명 |

---

## 7. 구현 순서

| 순서 | 산출물 | 의존성 | 예상 규모 |
|------|--------|--------|----------|
| 1 | D1: config.py | 없음 | +3줄 |
| 2 | D2: vllm_provider.py | D1 | +5줄 |
| 3 | D3: cli.py | D1, D2 | +8줄 |
| 4 | D7: package.json | 없음 | +5줄 |
| 5 | D4: config.ts | 없음 | +3줄 |
| 6 | D5: process.ts | 없음 | +4줄 |
| 7 | D6: client.ts | D4, D5 | +2줄 |
| 8 | D8: config.json.example | 없음 | 신규 파일 |

**총**: 7개 수정 파일 + 1개 신규 파일, ~30줄 변경

---

## 8. 검증 체크리스트

| # | 검증 항목 | 성공 기준 |
|---|----------|----------|
| V1 | config.py api_key 필드 | `AppConfig.load()` → `config.llm.api_key` 접근 가능 |
| V2 | 환경변수 오버라이드 | `MYAICODER_API_KEY=xxx` 설정 시 config보다 우선 |
| V3 | VLLMProvider api_key 전달 | `AsyncOpenAI(api_key=...)` + `_raw_chat` 헤더 동일 값 |
| V4 | _raw_chat Authorization | `api_key != "not-needed"`일 때 `Bearer <key>` 헤더 전송 |
| V5 | _raw_chat 로컬 모드 | `api_key == "not-needed"`일 때 Authorization 헤더 미전송 |
| V6 | CLI --api-key | `myaicoder --api-key xxx chat` → VLLMProvider에 전달 |
| V7 | CLI serve --api-key | `myaicoder serve --api-key xxx --agentic` → 인증 동작 |
| V8 | Extension apiKey 설정 | `myaicoder.apiKey` 값 → `--api-key` CLI 인자로 전달 |
| V9 | Extension 로컬 모드 | apiKey 빈 문자열 → `--api-key` 미전달 → 기존 동작 |
| V10 | DGX 통합 테스트 | Extension → serve --api-key → Gateway → 200 OK |
| V11 | 기존 테스트 통과 | 241/241 PASS (api_key 미설정 시 "not-needed" 기본값) |
| V12 | config.json.example | api_key 필드 포함 |
| V13 | apiKey scope: machine | VS Code 워크스페이스 설정에 저장 불가, 글로벌만 허용 |
| V14 | 빈 문자열 방어 | `apiKey=""` 설정 시 Bearer 헤더 미전송, 정상 fallback |
