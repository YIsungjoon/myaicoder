# Design: developer-onboarding

## 참조 문서
- Plan: `docs/pdca/01-plan/features/developer-onboarding.plan.md`

---

## 1. 설계 개요

신규 개발자가 10분 내에 myAiCoder를 셋업할 수 있도록 문서 + 스크립트 + config 포터블화.
**코드 변경 최소화** — process.py 환경변수 폴백 1건 + config.py 기본값 수정 1건만.

### 변경 파일 목록

| # | 파일 | 작업 | 설계 항목 |
|---|------|------|----------|
| D1 | `config/gateway.yaml.example` | 신규 | 중앙 config example (시크릿 플레이스홀더) |
| D2 | `config/models.yaml.example` | 신규 | 중앙 config example (경로 플레이스홀더) |
| D3 | `.env.example` | 신규 | 환경변수 목록 |
| D4 | `services/myaicoder/src/myaicoder/models/process.py` | 수정 | backend_command 3-tier fallback |
| D5 | `services/myaicoder/src/myaicoder/core/config.py` | 수정 | CLI 기본 모델명 일치 |
| D6 | `scripts/setup-dev.sh` | 신규 | 멱등 셋업 스크립트 |
| D7 | `scripts/start-all.sh` | 신규 | 서비스 기동 스크립트 |
| D8 | `docs/getting-started.md` | 신규 | 5분 퀵스타트 가이드 |
| D9 | `README.md` (프로젝트 루트) | 신규 | 프로젝트 개요 |

---

## 2. D1: config/gateway.yaml.example

기존 `services/gateway/gateway.yaml.example`을 중앙 config/로 이동·확장.

```yaml
# myAiCoder Gateway Configuration
# Copy to config/gateway.yaml and fill in your values

server:
  host: "0.0.0.0"
  port: 8080

auth:
  users:
    - user_id: "dev_user"
      name: "Developer"
      api_key_hash: "<your-bcrypt-hash-here>"
      role: "admin"
  internal_token: "<generate-with-python -c 'import secrets; print(secrets.token_urlsafe(32))'>"

models:
  default_model: "qwen3.5-9b"
  routes:
    "qwen3.5-9b": "http://localhost:8001/v1"

rate_limit:
  enabled: true
  roles:
    admin: { requests_per_minute: 120, requests_per_hour: 3600 }
    user: { requests_per_minute: 30, requests_per_hour: 500 }

logging:
  level: "INFO"
  format: "json"
```

### 검증 기준
- 플레이스홀더(`<your-...>`)가 포함되어 그대로 사용 불가 (의도적)
- 복사 후 값 채우면 Gateway 정상 기동

---

## 3. D2: config/models.yaml.example

```yaml
# myAiCoder Models Configuration
# Copy to config/models.yaml and adjust paths for your environment

environment: dev
models_dir: "~/models"
default_model: "qwen3.5-9b"
port: 8001
backend: "llama-cpp"

# backend_command: 생략 시 자동 탐지 (아래 우선순위)
#   1. 이 필드에 명시된 경로
#   2. 환경변수 LLAMA_SERVER_PATH
#   3. 시스템 PATH의 llama-server

instances:
  - name: "qwen3.5-9b"
    file: "Qwen3.5-9B-Q4_K_M.gguf"
    description: "Qwen 3.5 9B — fast response"
    vllm_args:
      gpu_memory_utilization: 0.5
      max_model_len: 32768
    defaults:
      temperature: 0.0
      max_tokens: 8192
```

### 설계 결정
- `backend_command` 필드를 **주석 처리**하여 자동 탐지가 기본 동작
- 오버라이드가 필요한 경우에만 주석 해제

---

## 4. D3: .env.example

```bash
# myAiCoder Environment Variables
# Copy to .env and adjust values

# LLM Server (llama.cpp)
LLAMA_SERVER_PATH=        # llama-server 바이너리 경로 (비워두면 PATH에서 자동 탐지)
MODELS_DIR=~/models       # GGUF 모델 파일 디렉토리

# Gateway
GATEWAY_CONFIG=config/gateway.yaml

# Monitoring (optional)
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
GRAFANA_PASSWORD=admin
```

---

## 5. D4: process.py — backend_command 3-tier fallback

### 현재 코드 (2-tier)

```python
def __init__(self, backend: str = "llama-cpp", command: str = ""):
    if command:
        self._cmd = command           # 1. yaml 명시값
    elif backend == "llama-cpp":
        self._cmd = "llama-server"    # 2. 기본 바이너리명 (PATH 탐지)
    else:
        self._cmd = "vllm"
```

### 변경 후 (3-tier)

```python
import os

def __init__(self, backend: str = "llama-cpp", command: str = ""):
    if command:
        self._cmd = command                                    # 1. yaml 명시값 (최우선)
    elif os.environ.get("LLAMA_SERVER_PATH"):
        self._cmd = os.environ["LLAMA_SERVER_PATH"]            # 2. 환경변수
    elif backend == "llama-cpp":
        self._cmd = "llama-server"                             # 3. PATH 자동 탐지
    else:
        self._cmd = os.environ.get("VLLM_PATH", "vllm")
```

### 변경 범위
- `__init__` 메서드만 수정 (4줄 추가)
- 기존 동작 100% 호환 (yaml에 값이 있으면 그대로 최우선)
- `shutil.which()` 검증은 기존 로직 그대로 유지

### 검증 기준
- yaml 명시 → 해당 경로 사용
- yaml 비어있음 + `LLAMA_SERVER_PATH` 설정 → 환경변수 사용
- 둘 다 없음 → `llama-server` (PATH 탐지)
- 기존 테스트 32개 통과

---

## 6. D5: core/config.py — 기본 모델명 수정

### 변경

```python
# Before
@dataclass
class LLMConfig:
    model: str = "Qwen3.5-27B-Q4_0.gguf"

# After
@dataclass
class LLMConfig:
    model: str = "qwen3.5-9b"
```

### 이유
- `config/models.yaml`의 `default_model: "qwen3.5-9b"`와 일치시킴
- Gateway routes에서도 `"qwen3.5-9b"` 키로 라우팅
- 기존 `.gguf` 확장자 포함 이름은 로컬 파일명, 라우팅용 이름이 아님

### 검증 기준
- `myaicoder config show`에서 `model: qwen3.5-9b` 표시
- 기존 테스트 통과

---

## 7. D6: scripts/setup-dev.sh

### 핵심 원칙
1. **멱등성**: 기존 파일 덮어쓰지 않음 (`cp -n`)
2. **모델 자동 다운로드**: `huggingface-cli`로 없는 모델만 다운로드
3. **에러 시 즉시 중단**: `set -euo pipefail`

### 스크립트 구조

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODELS_DIR="${MODELS_DIR:-$HOME/models}"

echo "=== myAiCoder Dev Setup ==="

# 1. Config 복사 (멱등: 기존 파일 보호)
echo "[1/5] Config files..."
cp -n "$REPO_ROOT/config/gateway.yaml.example" "$REPO_ROOT/config/gateway.yaml" 2>/dev/null && \
  echo "  Created config/gateway.yaml (edit API keys!)" || \
  echo "  config/gateway.yaml already exists, skipped"
cp -n "$REPO_ROOT/config/models.yaml.example" "$REPO_ROOT/config/models.yaml" 2>/dev/null && \
  echo "  Created config/models.yaml" || \
  echo "  config/models.yaml already exists, skipped"
cp -n "$REPO_ROOT/.env.example" "$REPO_ROOT/.env" 2>/dev/null && \
  echo "  Created .env" || \
  echo "  .env already exists, skipped"

# 2. Python 의존성
echo "[2/5] Python dependencies..."
(cd "$REPO_ROOT/services/myaicoder" && uv sync --extra dev)
(cd "$REPO_ROOT/services/gateway" && uv sync --extra dev)

# 3. CLI 설치
echo "[3/5] Installing myaicoder CLI..."
(cd "$REPO_ROOT/services/myaicoder" && uv pip install -e .)

# 4. 모델 다운로드 (없는 경우에만)
echo "[4/5] Checking model files..."
mkdir -p "$MODELS_DIR"
MODEL_FILE="$MODELS_DIR/Qwen3.5-9B-Q4_K_M.gguf"
if [ -f "$MODEL_FILE" ]; then
  echo "  Model already exists: $MODEL_FILE"
else
  echo "  Downloading Qwen3.5-9B-Q4_K_M.gguf (~6GB)..."
  if command -v huggingface-cli &>/dev/null; then
    huggingface-cli download Qwen/Qwen3.5-9B-GGUF Qwen3.5-9B-Q4_K_M.gguf \
      --local-dir "$MODELS_DIR" --local-dir-use-symlinks False
  else
    echo "  huggingface-cli not found. Install: pip install huggingface-hub"
    echo "  Or download manually from https://huggingface.co/Qwen/Qwen3.5-9B-GGUF"
  fi
fi

# 5. 검증
echo "[5/5] Verifying setup..."
echo -n "  myaicoder CLI: "
if command -v myaicoder &>/dev/null; then echo "OK"; else echo "NOT FOUND (check PATH)"; fi
echo -n "  Gateway config: "
if [ -f "$REPO_ROOT/config/gateway.yaml" ]; then echo "OK"; else echo "MISSING"; fi
echo -n "  Models config: "
if [ -f "$REPO_ROOT/config/models.yaml" ]; then echo "OK"; else echo "MISSING"; fi
echo -n "  Model file: "
if [ -f "$MODEL_FILE" ]; then echo "OK ($(du -h "$MODEL_FILE" | cut -f1))"; else echo "MISSING"; fi
echo -n "  llama-server: "
if command -v llama-server &>/dev/null; then echo "OK"; else echo "NOT FOUND (build or set LLAMA_SERVER_PATH)"; fi

echo ""
echo "=== Setup complete! ==="
echo "Next: edit config/gateway.yaml (set API key hash), then run: scripts/start-all.sh"
```

### 검증 기준
- 첫 실행: config 복사 + 의존성 설치 + 모델 다운로드 시도
- 재실행: config 스킵 + 의존성 업데이트 + 모델 스킵
- 검증 섹션에서 각 항목 OK/MISSING 표시

---

## 8. D7: scripts/start-all.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Load .env if exists
[ -f "$REPO_ROOT/.env" ] && set -a && source "$REPO_ROOT/.env" && set +a

MODELS_DIR="${MODELS_DIR:-$HOME/models}"
LLAMA_PORT="${LLAMA_PORT:-8001}"
GATEWAY_PORT="${GATEWAY_PORT:-8080}"

echo "=== Starting myAiCoder Services ==="

# 1. LLM Server
LLAMA_CMD="${LLAMA_SERVER_PATH:-llama-server}"
MODEL_FILE="$MODELS_DIR/Qwen3.5-9B-Q4_K_M.gguf"
if [ ! -f "$MODEL_FILE" ]; then
  echo "ERROR: Model not found: $MODEL_FILE"
  echo "Run scripts/setup-dev.sh first"
  exit 1
fi

echo "[1/2] Starting LLM server on port $LLAMA_PORT..."
$LLAMA_CMD \
  --model "$MODEL_FILE" \
  --host 0.0.0.0 --port "$LLAMA_PORT" \
  --n-gpu-layers -1 --ctx-size 32768 &
LLM_PID=$!

# Wait for LLM server to be ready
echo "  Waiting for LLM server..."
for i in $(seq 1 30); do
  if curl -sf "http://localhost:$LLAMA_PORT/health" >/dev/null 2>&1; then
    echo "  LLM server ready!"
    break
  fi
  sleep 1
done

# 2. Gateway
echo "[2/2] Starting Gateway on port $GATEWAY_PORT..."
cd "$REPO_ROOT/services/gateway"
GATEWAY_CONFIG="$REPO_ROOT/config/gateway.yaml" \
  uv run uvicorn app.main:create_app --factory \
  --host 0.0.0.0 --port "$GATEWAY_PORT" &
GW_PID=$!

echo ""
echo "=== Services Running ==="
echo "  LLM Server: http://localhost:$LLAMA_PORT (PID: $LLM_PID)"
echo "  Gateway:    http://localhost:$GATEWAY_PORT (PID: $GW_PID)"
echo ""
echo "Press Ctrl+C to stop all services"

# Graceful shutdown
trap "echo 'Stopping...'; kill $GW_PID $LLM_PID 2>/dev/null; wait" INT TERM
wait
```

### 검증 기준
- LLM + Gateway 순차 기동
- Ctrl+C로 두 서비스 동시 정리
- 모델 파일 없으면 에러 + 가이드 메시지

---

## 9. D8: docs/getting-started.md

### 두 가지 모드

```
[로컬 모드] 개발자 PC에서 모든 서비스 실행
VS Code → myaicoder serve (로컬 도구) → localhost:8080 Gateway → localhost:8001 LLM

[서버 모드] DGX 서버에 LLM+Gateway, 개발자 PC는 Extension만
VS Code → myaicoder serve (로컬 도구) → dgx-server:8080 Gateway → DGX LLM
```

### 구조

```markdown
# Getting Started

## 모드 선택
- **서버 모드 (권장)**: DGX 서버에 LLM이 이미 돌고 있을 때 → 3분 셋업
- **로컬 모드**: 본인 PC에서 직접 LLM을 돌릴 때 → 10분 셋업

## 서버 모드 Quick Start (3분) — DGX 서버 사용
1. git clone & cd myaicoder
2. pip install -e services/myaicoder/  (CLI 설치)
3. VS Code에서 .vsix 설치
4. VS Code 설정: myaicoder.llmUrl → "http://dgx-server:8080"
5. Activity Bar에서 myAiCoder → 채팅 시작

## 로컬 모드 Quick Start (10분) — 본인 PC에서 LLM 실행
1. git clone & cd myaicoder
2. scripts/setup-dev.sh  (config + 의존성 + 모델 다운로드)
3. config/gateway.yaml 편집 (API key 설정)
4. scripts/start-all.sh  (LLM + Gateway 기동)
5. VS Code에서 .vsix 설치 → 채팅 시작

## DGX 서버 관리자 가이드
### LLM 서버 기동
### Gateway 기동
### 방화벽/포트 설정 (8080 개방)
### API key 발급

## Architecture Overview
(간략 다이어그램: 로컬 모드 vs 서버 모드)

## Troubleshooting
- llama-server not found → LLAMA_SERVER_PATH 설정
- Gateway 인증 실패 → gateway.yaml API key 확인
- Extension 연결 안 됨 → myaicoder CLI PATH 확인
- 서버 모드 연결 안 됨 → DGX 방화벽 8080 포트 확인
```

### 핵심 설계: 서버 모드는 Extension 설정 1개만 변경

```json
// VS Code settings.json
{
  "myaicoder.llmUrl": "http://dgx-server:8080"
}
```

도구(파일 읽기/쓰기/검색)는 항상 로컬 `myaicoder serve`에서 실행되므로,
LLM URL만 바꾸면 서버 모드로 전환됨.

### 검증 기준
- 서버 모드: 3단계로 첫 대화 성공
- 로컬 모드: 5단계로 첫 대화 성공
- Troubleshooting 4개 항목 포함

---

## 10. D9: README.md (프로젝트 루트)

### 구조

```markdown
# myAiCoder

> AI coding assistant powered by local LLM — your data stays on your machine

## What is myAiCoder?
로컬 LLM + MCP 프로토콜 기반 AI 코딩 어시스턴트. VS Code에서 사용.

## Quick Start
→ docs/getting-started.md 링크

## Architecture
Extension ↔ MCP Client ↔ myaicoder serve ↔ Gateway ↔ LLM Server

## Project Structure
(모노레포 디렉토리 설명)

## Development
→ getting-started.md 링크

## License
MIT
```

---

## 11. 구현 순서

```
S1. config/gateway.yaml.example 생성               [D1]
S2. config/models.yaml.example 생성                 [D2]
S3. .env.example 생성                               [D3]
S4. process.py 수정 (3-tier fallback)               [D4]
S5. core/config.py 기본 모델명 수정                   [D5]
S6. scripts/setup-dev.sh 작성                        [D6]
S7. scripts/start-all.sh 작성                        [D7]
S8. docs/getting-started.md 작성                     [D8]
S9. README.md (프로젝트 루트) 작성                     [D9]
S10. 기존 테스트 통과 확인                             [241 passed]
```

## 12. 검증 매트릭스

| 설계 항목 | 검증 방법 | 성공 기준 |
|----------|----------|----------|
| D1 gateway example | 플레이스홀더 존재 확인 | `<your-` 패턴 포함 |
| D2 models example | `backend_command` 주석 처리 확인 | `# backend_command` |
| D3 .env.example | 파일 존재 + 변수 목록 | LLAMA_SERVER_PATH 포함 |
| D4 3-tier fallback | 환경변수 설정 후 process 테스트 | LLAMA_SERVER_PATH 우선 |
| D5 기본 모델명 | `python -c "from myaicoder.core.config import LLMConfig; print(LLMConfig().model)"` | `qwen3.5-9b` |
| D6 setup-dev.sh | 첫 실행 → 재실행 (멱등성) | config 덮어쓰기 없음 |
| D7 start-all.sh | 모델 없을 때 에러 메시지 | 명확한 가이드 출력 |
| D8 getting-started | Quick Start 5단계 존재 | 제목 확인 |
| D9 README | 프로젝트 루트에 존재 | 링크 유효 |
| 전체 | Gateway + myaicoder + Extension 테스트 | 241 passed |
