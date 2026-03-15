# Plan: DGX Migration — 전체 환경 구축

- **Feature**: dgx-migration
- **Level**: Enterprise
- **Created**: 2026-03-15
- **Status**: Draft

---

## 1. 배경 및 목표

### 1.1 현재 상태 (As-Is)
- **실행 환경**: 개발 데스크톱 (24GB VRAM)
- **모델 서빙**: llama.cpp 직접 빌드 (`~/llm-server-env/llama.cpp/`)
- **서비스**: myaicoder CLI + Gateway (수동 실행, `scripts/start-all.sh`)
- **모델**: Qwen 3.5 9B/27B, Qwen 3 Coder 30B (GGUF, 한 번에 1개만 로드)
- **인프라**: docker-compose (Postgres, Redis, Prometheus, Grafana만)
- **접근**: localhost only
- **문제점**:
  - 24GB VRAM으로 27B+ 모델 로드 시 품질 저하 (Q4 양자화 필수)
  - 동시 모델 서빙 불가
  - 수동 프로세스 관리 (재시작 시 전체 수동 실행)
  - 팀 공유 불가

### 1.2 목표 상태 (To-Be)
- **실행 환경**: DGX Spark (ARM CPU, GB10 Blackwell, 128GB 통합메모리)
- **모델 서빙**: llama.cpp (ARM 네이티브 빌드), 동시 다중 모델 가능
- **서비스**: Docker Compose로 전체 스택 컨테이너화
- **모델**: 기존 GGUF + 더 큰 모델 (70B급) 추가 가능
- **인프라**: 단일 `docker compose up`으로 전체 시작
- **접근**: 내부망 + SSH 터널

### 1.3 핵심 가치
| 가치 | 설명 |
|------|------|
| **원클릭 시작** | `docker compose up -d` 한 줄로 전체 환경 시작 |
| **다중 모델** | 128GB 통합메모리로 2-3개 모델 동시 서빙 |
| **팀 공유** | 내부망 IP로 팀원 접근 가능 |
| **자동 복구** | `restart: unless-stopped`으로 장애 시 자동 재시작 |

---

## 2. 범위 (Scope)

### 2.1 In-Scope

| # | 작업 | 설명 |
|---|------|------|
| S1 | **Dockerfile 작성** | myaicoder, gateway 서비스 컨테이너 이미지 빌드 |
| S2 | **llama.cpp ARM 빌드** | DGX Spark ARM + CUDA용 llama-server 컨테이너 |
| S3 | **docker-compose 통합** | 전체 스택 (LLM + Gateway + Infra) 단일 compose |
| S4 | **prod 환경 설정** | config/gateway.prod.yaml, config/models.prod.yaml |
| S5 | **배포 스크립트** | DGX 초기 셋업 + 모델 다운로드 + 서비스 시작 |
| S6 | **네트워크 구성** | 내부망 접근, SSH 터널 가이드 |
| S7 | **모니터링** | Prometheus + Grafana 연동 (기존 docker-compose 확장) |

### 2.2 Out-of-Scope
- Kubernetes 배포 (향후 필요 시 확장)
- TLS/HTTPS 인증서 (내부망이므로 HTTP)
- CI/CD 파이프라인 (수동 배포 → 향후 자동화)
- 모델 파인튜닝/학습

---

## 3. 기술 분석

### 3.1 DGX Spark 특성
| 항목 | 사양 | 영향 |
|------|------|------|
| CPU | ARM (Grace) | Docker 이미지 `linux/arm64` 필수, x86 이미지 호환 불가 |
| GPU | GB10 Blackwell | CUDA 12.8+, llama.cpp CUDA 빌드 필요 |
| 메모리 | 128GB 통합 (CPU+GPU 공유) | 모델 여러 개 동시 로드 가능, GPU VRAM 제한 없음 |
| OS | Ubuntu (ARM64) | 표준 Docker/docker-compose 사용 가능 |

### 3.2 ARM 호환성 체크리스트
| 컴포넌트 | ARM64 지원 | 비고 |
|----------|-----------|------|
| Python 3.11+ | ✅ | 공식 ARM64 이미지 |
| FastAPI/uvicorn | ✅ | Pure Python |
| llama.cpp | ✅ | ARM NEON + CUDA 빌드 필요 |
| PostgreSQL 16 | ✅ | `postgres:16-alpine` ARM64 지원 |
| Redis 7 | ✅ | `redis:7-alpine` ARM64 지원 |
| Prometheus | ✅ | ARM64 이미지 제공 |
| Grafana | ✅ | ARM64 이미지 제공 |

### 3.3 모델 전략 (128GB 통합메모리)
| 모델 | 파일 크기 | 메모리 예상 | 동시 서빙 |
|------|----------|-----------|----------|
| Qwen3.5-9B (Q4_K_M) | ~6GB | ~8GB | ✅ |
| Qwen3.5-27B (Q4_K_M) | ~16GB | ~20GB | ✅ |
| Qwen3-Coder-30B (Q4_K_M) | ~18GB | ~22GB | ✅ |
| **3개 동시** | ~40GB | ~50GB | ✅ (128GB 중 39% 사용) |
| Qwen3.5-72B (Q4_K_M, 향후) | ~42GB | ~50GB | 2개까지 가능 |

### 3.4 llama.cpp 멀티 인스턴스 전략
- **방안 A**: llama-server 인스턴스 3개 (모델별 포트 분리) ← **채택**
  - 장점: 모델별 독립 재시작, 리소스 격리, 간단
  - 단점: 포트 3개 관리
- **방안 B**: llama-server `--model-alias` 멀티모델 (단일 프로세스)
  - 장점: 포트 1개
  - 단점: 한 모델 장애 시 전체 영향, 실험적 기능

---

## 4. 아키텍처

### 4.1 배포 토폴로지
```
DGX Spark (내부망 192.168.x.x)
┌─────────────────────────────────────────────────────┐
│  Docker Compose                                     │
│  ┌───────────────────────────────────────────┐      │
│  │ llama-9b    :8001  ← Qwen3.5-9B          │      │
│  │ llama-27b   :8002  ← Qwen3.5-27B         │      │
│  │ llama-coder :8003  ← Qwen3-Coder-30B     │      │
│  └───────────────────────────────────────────┘      │
│           ↕ (내부 네트워크)                            │
│  ┌───────────────────────────────────────────┐      │
│  │ gateway     :8080  ← API Gateway          │      │
│  └───────────────────────────────────────────┘      │
│           ↕                                         │
│  ┌───────────────────────────────────────────┐      │
│  │ postgres    :5432  │ redis   :6379        │      │
│  │ prometheus  :9090  │ grafana :3000        │      │
│  └───────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────┘
         ↕ (내부망 / SSH 터널)
  ┌──────────────┐
  │ 개발자 PC     │
  │ VS Code Ext  │
  │ CLI Client   │
  └──────────────┘
```

### 4.2 Docker 이미지 구성
| 이미지 | Base | 빌드 방식 |
|--------|------|----------|
| `myaicoder/llama-server` | `nvidia/cuda:12.8.0-devel-ubuntu24.04` (ARM64) | llama.cpp 소스 빌드 |
| `myaicoder/gateway` | `python:3.11-slim` (ARM64) | pip/uv install |
| `myaicoder/cli` | 호스트 직접 설치 또는 gateway 컨테이너 내 | uv install |

### 4.3 볼륨 마운트
| 볼륨 | 호스트 경로 | 컨테이너 경로 | 용도 |
|------|-----------|-------------|------|
| models | `~/models/` | `/models` | GGUF 모델 파일 (읽기전용) |
| config | `./config/` | `/app/config` | 설정 파일 |
| postgres_data | Docker volume | `/var/lib/postgresql/data` | DB 영속화 |
| grafana_data | Docker volume | `/var/lib/grafana` | 대시보드 영속화 |

---

## 5. 구현 계획

### 5.0 사전 체크 (DGX 호스트)
| # | 항목 | 확인 명령 | 필수 |
|---|------|----------|------|
| P0-1 | NVIDIA Driver | `nvidia-smi` | ✅ |
| P0-2 | CUDA 버전 | `nvidia-smi` 상단 CUDA Version | ✅ |
| P0-3 | **NVIDIA Container Toolkit** | `nvidia-ctk --version` | ✅ |
| P0-4 | Docker GPU 접근 | `docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu24.04 nvidia-smi` | ✅ |
| P0-5 | ARM64 아키텍처 | `uname -m` → `aarch64` | ✅ |

> **중요**: Docker 컨테이너에서 GPU를 사용하려면 호스트에 `nvidia-container-toolkit`이 반드시 설치되어 있어야 하며, compose 서비스에 `deploy.resources.reservations.devices` 설정이 필요합니다.

### 5.1 단계별 작업

#### Phase 1: 컨테이너화 (Dockerfiles)
| # | 작업 | 산출물 |
|---|------|--------|
| P1-1 | llama-server Dockerfile (ARM64 + CUDA) | `docker/llama-server.Dockerfile` |
| P1-2 | Gateway Dockerfile | `docker/gateway.Dockerfile` |
| P1-3 | 로컬 빌드 테스트 | 이미지 빌드 성공 확인 |

#### Phase 2: Docker Compose 통합
| # | 작업 | 산출물 |
|---|------|--------|
| P2-1 | docker-compose.prod.yml 작성 | 전체 스택 정의 |
| P2-2 | prod 환경 설정 파일 | `config/gateway.prod.yaml`, `config/models.prod.yaml` |
| P2-3 | .env.prod 템플릿 | 환경변수 정리 |

#### Phase 3: DGX 셋업 스크립트
| # | 작업 | 산출물 |
|---|------|--------|
| P3-1 | DGX 초기 셋업 스크립트 | `scripts/setup-dgx.sh` |
| P3-2 | 모델 다운로드 스크립트 | `scripts/download-models.sh` |
| P3-3 | 서비스 관리 명령 | start/stop/status 래퍼 |

#### Phase 4: 네트워크 & 모니터링
| # | 작업 | 산출물 |
|---|------|--------|
| P4-1 | SSH 터널 가이드 | 접속 문서 |
| P4-2 | Prometheus 타겟 업데이트 | `config/prometheus.prod.yml` |
| P4-3 | Grafana 대시보드 | GPU 메모리, 요청 처리량, 응답 시간 |

#### Phase 5: 테스트 & 검증
| # | 작업 | 산출물 |
|---|------|--------|
| P5-1 | DGX 이미지 빌드 검증 | ARM64 빌드 성공 |
| P5-2 | 통합 테스트 (DGX) | 기존 integration_test.sh 적용 |
| P5-3 | 다중 모델 동시 서빙 테스트 | 3개 모델 동시 로드 확인 |

### 5.2 구현 순서 (의존성)
```
P1-1 (llama Dockerfile)
  ↓
P1-2 (gateway Dockerfile) ── P2-2 (prod config)
  ↓                              ↓
P1-3 (로컬 테스트)           P2-3 (.env.prod)
  ↓                              ↓
P2-1 (docker-compose.prod.yml) ←─┘
  ↓
P3-1 (setup-dgx.sh) ── P3-2 (download-models.sh)
  ↓
P3-3 (서비스 관리)
  ↓
P4-1~P4-3 (네트워크 & 모니터링)
  ↓
P5-1~P5-3 (테스트)
```

---

## 6. 리스크 및 대응

| # | 리스크 | 영향 | 대응 |
|---|--------|------|------|
| R1 | llama.cpp ARM+CUDA 빌드 실패 | 모델 서빙 불가 | NVIDIA NGC llama.cpp 이미지 확인, 소스 빌드 fallback |
| R2 | 128GB 통합메모리에서 GPU 할당 불명확 | 모델 로드 실패 | `--n-gpu-layers -1` 테스트, `nvidia-smi` 모니터링 |
| R3 | ARM64 Docker 이미지 호환성 | 특정 이미지 미지원 | multi-arch 이미지 확인, 필요 시 빌드 |
| R4 | DGX Spark CUDA 드라이버 버전 | llama.cpp 빌드 시 CUDA 버전 불일치 | `nvidia-smi` 확인 후 맞는 CUDA 이미지 사용 |
| R5 | 내부망 방화벽으로 포트 차단 | 접근 불가 | SSH 터널 (-L), 필요 시 방화벽 규칙 추가 |
| R6 | NVIDIA Container Toolkit 미설치 | Docker에서 GPU 접근 불가 | P0-3 사전 체크, `apt install nvidia-container-toolkit` |

---

## 7. 성공 기준

| # | 기준 | 측정 방법 |
|---|------|----------|
| C1 | `docker compose up -d` 한 줄로 전체 시작 | 명령 실행 후 모든 컨테이너 healthy |
| C2 | 3개 모델 동시 서빙 | 각 모델 /health 엔드포인트 200 OK |
| C3 | Gateway 통한 모델 라우팅 | curl로 모델별 chat completion 응답 확인 |
| C4 | 개발자 PC에서 접근 | VS Code Extension에서 DGX Gateway 연결 성공 |
| C5 | 모니터링 동작 | Grafana 대시보드에서 메트릭 확인 |
| C6 | 자동 재시작 | 컨테이너 kill 후 자동 복구 확인 |

---

## 8. 산출물 목록

| # | 파일 | 설명 |
|---|------|------|
| D1 | `docker/llama-server.Dockerfile` | llama.cpp ARM64+CUDA 빌드 |
| D2 | `docker/gateway.Dockerfile` | Gateway 서비스 이미지 |
| D3 | `docker-compose.prod.yml` | 프로덕션 전체 스택 |
| D4 | `config/gateway.prod.yaml` | 프로덕션 Gateway 설정 |
| D5 | `config/models.prod.yaml` | 프로덕션 모델 설정 (다중 인스턴스) |
| D6 | `.env.prod.example` | 환경변수 템플릿 |
| D7 | `scripts/setup-dgx.sh` | DGX 초기 셋업 |
| D8 | `scripts/download-models.sh` | 모델 다운로드 |
| D9 | `config/prometheus.prod.yml` | 프로덕션 모니터링 |
