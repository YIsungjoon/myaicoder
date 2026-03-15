# Getting Started

myAiCoder는 로컬 LLM 기반 AI 코딩 어시스턴트입니다. VS Code에서 채팅하며 코드를 작성할 수 있습니다.

## 모드 선택

| 모드 | 대상 | 셋업 시간 | 필요한 것 |
|------|------|:---------:|----------|
| **서버 모드** (권장) | 일반 개발자 | 3분 | Python, VS Code |
| **로컬 모드** | GPU 보유자/관리자 | 10분 | Python, VS Code, NVIDIA GPU, llama.cpp |

---

## 서버 모드 Quick Start (3분)

DGX 서버에 이미 LLM + Gateway가 돌고 있을 때 사용합니다.

### 1. 저장소 클론 & CLI 설치

```bash
git clone <repo-url> myaicoder
cd myaicoder
pip install -e services/myaicoder/
```

### 2. VS Code Extension 설치

팀에서 공유받은 `.vsix` 파일을 설치합니다:

```bash
code --install-extension myaicoder-1.0.1.vsix
```

또는 VS Code > Extensions > `...` > Install from VSIX...

### 3. 서버 URL 설정

VS Code 설정 (`Ctrl+,`) > `myaicoder.llmUrl` 검색 > 서버 주소 입력:

```
http://dgx-server:8080
```

### 4. 채팅 시작

VS Code 왼쪽 Activity Bar에서 myAiCoder 아이콘 클릭 > 채팅 시작!

---

## 로컬 모드 Quick Start (10분)

본인 PC에서 직접 LLM을 돌릴 때 사용합니다.

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python 패키지 매니저)
- NVIDIA GPU (CUDA 12+)
- [llama.cpp](https://github.com/ggerganov/llama.cpp) (빌드 완료, `llama-server` PATH 등록)
- VS Code 1.85+

### 1. 저장소 클론 & 자동 셋업

```bash
git clone <repo-url> myaicoder
cd myaicoder
scripts/setup-dev.sh
```

이 스크립트가 자동으로:
- config 파일 생성 (기존 파일은 보호)
- Python 의존성 설치
- myaicoder CLI 설치
- GGUF 모델 다운로드 (~6GB, 없는 경우에만)

### 2. Gateway 설정

```bash
# config/gateway.yaml에서 API key 해시 설정
python -c "import hashlib; print(hashlib.sha256(b'my-secret-key').hexdigest())"
# 출력된 해시를 config/gateway.yaml의 api_key_hash에 복사
```

### 3. 서비스 시작

```bash
scripts/start-all.sh
```

LLM 서버 + Gateway가 순차적으로 기동됩니다.

### 4. Extension 설치 & 채팅

```bash
cd apps/vscode-extension && npm install && npm run package
code --install-extension myaicoder-1.0.1.vsix
```

VS Code Activity Bar > myAiCoder > 채팅 시작!

---

## DGX 서버 관리자 가이드

DGX 서버에 LLM + Gateway를 올려서 팀원들이 원격으로 사용하게 하려면:

### 1. 서버 셋업

```bash
git clone <repo-url> myaicoder
cd myaicoder
scripts/setup-dev.sh
```

### 2. Config 편집

```bash
# config/gateway.yaml — 팀원별 API key 추가
# config/models.yaml — 모델 경로, GPU 설정
```

### 3. 서비스 기동

```bash
scripts/start-all.sh
# 또는 systemd/tmux로 백그라운드 실행
```

### 4. 방화벽 설정

Gateway 포트 `8080`을 사내 네트워크에 개방합니다.

### 5. 팀원에게 안내

```
1. myaicoder CLI 설치: pip install -e services/myaicoder/
2. .vsix 파일 설치 (카카오톡/인트라넷에서 다운로드)
3. VS Code 설정: myaicoder.llmUrl → http://<서버IP>:8080
```

---

## Architecture

```
[서버 모드]
개발자 PC                          DGX 서버
┌──────────────┐                 ┌──────────────────┐
│ VS Code      │                 │ Gateway (:8080)   │
│  └ Extension │ ── HTTP ──────> │  └ Auth, Logging  │
│  └ myaicoder │                 │  └ Rate Limiting  │
│    serve     │                 │  └ Proxy ─────────│──> LLM Server (:8001)
│   (로컬 도구) │                 │                    │    └ Qwen3.5-9B
└──────────────┘                 └──────────────────┘

[로컬 모드]
개발자 PC
┌─────────────────────────────────────────┐
│ VS Code → Extension → myaicoder serve  │
│              │                          │
│              └─> Gateway (:8080)        │
│                    └─> LLM Server (:8001)│
└─────────────────────────────────────────┘
```

---

## Extension Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `myaicoder.llmUrl` | `http://localhost:8080` | Gateway URL (서버 모드에서 변경) |
| `myaicoder.modelName` | `qwen3.5-9b` | 상태바 표시 모델명 |
| `myaicoder.allowBash` | `false` | Bash 도구 허용 여부 |
| `myaicoder.maxConcurrent` | `1` | 최대 동시 MCP 요청 |
| `myaicoder.enableAgentic` | `false` | 에이전트 모드 |

---

## Troubleshooting

| 문제 | 해결 |
|------|------|
| `llama-server not found` | `.env`에 `LLAMA_SERVER_PATH=/path/to/llama-server` 설정 |
| Gateway 인증 실패 (403) | `config/gateway.yaml`의 `api_key_hash` 확인 |
| Extension 연결 안 됨 | `myaicoder` CLI가 PATH에 있는지 확인 (`which myaicoder`) |
| 서버 모드 연결 안 됨 | DGX 서버 방화벽 8080 포트 확인, `curl http://dgx:8080/health` |
| 모델 로딩 느림 | 첫 요청 시 콜드 스타트 (~10초), 이후 정상 |
