# Plan: developer-onboarding

## Feature 정보

| 항목 | 내용 |
|------|------|
| Feature | developer-onboarding |
| Track | A (UX 완성 및 제품화) |
| 우선순위 | **높음** — 사내 배포 시 가장 먼저 필요 |
| 의존 | marketplace-deployment (Extension .vsix), observability (모니터링 스택) |

## 1. 목적

새로운 사내 개발자가 **10분 이내에** myAiCoder를 셋업하고 VS Code에서 사용할 수 있게 한다.

### 배경

- 코드와 기능은 모두 완성 (15개 PDCA feature, 241개 테스트)
- 하지만 온보딩 문서가 없어 신규 개발자가 **혼자서 셋업 불가능**
- config 파일에 절대경로 하드코딩 (`/home/buttumaklevit/...`)
- 서비스 3개를 각각 수동 기동해야 함
- 모델명 기본값 불일치 (CLI: `Qwen3.5-27B` vs config: `qwen3.5-9b`)

## 2. 현재 상태 분석

### 2.1 신규 개발자가 겪는 문제

| 단계 | 문제 | 심각도 |
|------|------|:------:|
| 1. 클론 후 뭐하지? | getting-started 가이드 없음 | 치명 |
| 2. config 파일 없음 | gitignore 처리됨, example 파일은 서비스 디렉토리에만 존재 | 높음 |
| 3. llama.cpp 경로 | `backend_command`에 절대경로 하드코딩 | 높음 |
| 4. 모델 다운로드 | 어디서, 어떤 모델을 받는지 안내 없음 | 높음 |
| 5. 서비스 기동 순서 | LLM → Gateway → Extension 순서를 알아야 함 | 중간 |
| 6. CLI 기본 모델명 | `Qwen3.5-27B-Q4_0.gguf` (코드) vs `qwen3.5-9b` (config) | 중간 |

### 2.2 이미 있는 것

| 항목 | 위치 |
|------|------|
| Extension README | apps/vscode-extension/README.md (Quick Start 5단계) |
| Gateway example config | services/gateway/gateway.yaml.example |
| Models example config | services/myaicoder/models.yaml.example |
| CLI entry point | `myaicoder = "myaicoder.cli:main"` (pyproject.toml) |
| Extension CLI 자동탐지 | config.ts (PATH → venv → 수동) |

## 3. 요구사항

### 3.1 필수 요구사항 (P0)

| ID | 요구사항 | 검증 기준 |
|----|----------|----------|
| R1 | `docs/getting-started.md` 작성 | 5분 퀵스타트 + 전체 셋업 가이드 |
| R2 | `config/*.example` 파일 중앙화 | config/gateway.yaml.example, config/models.yaml.example |
| R3 | models.yaml `backend_command` 포터블화 | 환경변수 또는 which 탐지로 절대경로 제거 |
| R4 | CLI 기본 모델명 수정 | `Qwen3.5-27B-Q4_0.gguf` → `qwen3.5-9b` (config와 일치) |
| R5 | `scripts/setup-dev.sh` 셋업 스크립트 | config 복사, 의존성 설치, 검증 자동화 |
| R6 | `.env.example` 파일 | 필요한 환경변수 목록 + 기본값 |
| R7 | 기존 테스트 241개 통과 | 0 regression |

### 3.2 권장 요구사항 (P1)

| ID | 요구사항 | 검증 기준 |
|----|----------|----------|
| R8 | 프로젝트 루트 README.md | 프로젝트 개요 + getting-started 링크 |
| R9 | `scripts/start-all.sh` 서비스 기동 스크립트 | LLM + Gateway 한 번에 기동 |

### 3.3 이연 항목 (P2)

| ID | 요구사항 | 이유 |
|----|----------|------|
| R10 | Docker 기반 원클릭 셋업 | GPU 패스스루 설정 복잡, 현재 불필요 |
| R11 | 트러블슈팅 가이드 | 운영 경험 축적 후 |

## 4. 구현 범위

### 4.1 문서

```
docs/getting-started.md      ← 신규: 5분 퀵스타트 + 전체 가이드
README.md (프로젝트 루트)      ← 신규: 프로젝트 개요
```

### 4.2 Config 포터블화

```
config/gateway.yaml.example   ← 신규: 중앙화된 example (시크릿 플레이스홀더)
config/models.yaml.example    ← 신규: backend_command → 환경변수 참조
.env.example                  ← 신규: LLAMA_SERVER_PATH, MODELS_DIR 등
```

### 4.3 코드 수정

```
services/myaicoder/src/myaicoder/core/config.py
  → LLMConfig.model 기본값: "Qwen3.5-27B-Q4_0.gguf" → "qwen3.5-9b"

services/myaicoder/src/myaicoder/models/config.py (해당 시)
  → backend_command 3-tier fallback 체인:
    1. models.yaml에 명시된 값 (최우선, 오버라이드)
    2. 환경변수 LLAMA_SERVER_PATH
    3. which llama-server 자동 탐지 (시스템 PATH)
```

### 4.4 스크립트

```
scripts/setup-dev.sh          ← 신규: config 복사, pip install, uv sync, 모델 다운로드, 검증
scripts/start-all.sh          ← 신규: LLM 서버 + Gateway 기동 (선택적)
```

#### setup-dev.sh 핵심 원칙

1. **멱등성**: 여러 번 실행해도 안전. 기존 config 덮어쓰지 않음 (`cp -n` 또는 `if [ ! -f ]`)
2. **모델 자동 다운로드**: `huggingface-cli download`로 GGUF 모델이 없을 경우에만 다운로드
3. **에러 시 즉시 중단**: `set -euo pipefail`

## 5. 구현 순서

| 단계 | 작업 | 산출물 |
|------|------|--------|
| S1 | config/*.example 파일 생성 | config/gateway.yaml.example, config/models.yaml.example |
| S2 | .env.example 생성 | .env.example |
| S3 | CLI 기본 모델명 수정 | core/config.py |
| S4 | models.yaml backend_command 포터블화 | models/config.py 수정 |
| S5 | scripts/setup-dev.sh 작성 | scripts/setup-dev.sh |
| S6 | scripts/start-all.sh 작성 | scripts/start-all.sh |
| S7 | docs/getting-started.md 작성 | docs/getting-started.md |
| S8 | 프로젝트 루트 README.md 작성 | README.md |
| S9 | 기존 테스트 통과 확인 | 241 passed |

## 6. 리스크

| 리스크 | 영향 | 대응 |
|--------|------|------|
| models.yaml 포터블화 시 기존 환경 깨짐 | 현재 사용자 config 무효 | 환경변수 미설정 시 기존 절대경로 폴백 |
| setup-dev.sh 권한 이슈 | macOS/Linux 차이 | bash 호환 + 에러 메시지 명확화 |
| GGUF 모델 용량 | 다운로드 시간 | 가이드에 모델 크기/권장사양 명시 |

## 7. 성공 기준

| 기준 | 측정 방법 |
|------|----------|
| 신규 개발자 10분 내 첫 대화 성공 | getting-started 가이드 따라하기 |
| config 절대경로 0건 | grep으로 `/home/` 패턴 미검출 (example 파일 내) |
| setup-dev.sh 정상 실행 | 스크립트 실행 후 Gateway 헬스체크 성공 |
| 기존 테스트 241개 통과 | pytest + vitest 전체 실행 |
| CLI 기본 모델명 config와 일치 | `myaicoder config show`에서 확인 |
