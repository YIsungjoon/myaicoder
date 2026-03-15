# Design: DGX Migration — 전체 환경 구축

- **Feature**: dgx-migration
- **Level**: Enterprise
- **Created**: 2026-03-15
- **Plan Reference**: `docs/pdca/01-plan/features/dgx-migration.plan.md`

---

## 1. 설계 개요

DGX Spark (ARM Grace CPU, GB10 Blackwell GPU, 128GB 통합메모리)에 myAiCoder 전체 스택을 Docker Compose로 배포한다. llama.cpp 기반 3개 모델 동시 서빙, Gateway 프록시, 모니터링을 포함한다.

### 1.1 산출물 매핑

| # | 산출물 | Plan 참조 | 설계 섹션 |
|---|--------|----------|----------|
| D1 | `docker/llama-server.Dockerfile` | P1-1 | §2 |
| D2 | `docker/gateway.Dockerfile` | P1-2 | §3 |
| D3 | `docker-compose.prod.yml` | P2-1 | §4 |
| D4 | `config/gateway.prod.yaml` | P2-2 | §5.1 |
| D5 | `config/models.prod.yaml` | P2-2 | §5.2 |
| D6 | `.env.prod.example` | P2-3 | §5.3 |
| D7 | `scripts/setup-dgx.sh` | P3-1 | §6.1 |
| D8 | `scripts/download-models.sh` | P3-2 | §6.2 |
| D9 | `config/prometheus.prod.yml` | P4-2 | §7 |

---

## 2. D1: llama-server.Dockerfile

### 2.1 설계 의도
- DGX Spark ARM64 + CUDA 환경에서 llama.cpp를 소스 빌드
- Multi-stage 빌드로 최종 이미지 경량화 (빌드 도구 제외)
- GGUF 모델은 볼륨 마운트 (이미지에 포함하지 않음)

### 2.2 파일 내용

**경로**: `docker/llama-server.Dockerfile`

```dockerfile
# ── Stage 1: Build llama.cpp ──
FROM nvidia/cuda:12.8.0-devel-ubuntu24.04 AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake git build-essential ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG LLAMA_CPP_VERSION=master
RUN git clone --depth 1 --branch ${LLAMA_CPP_VERSION} \
    https://github.com/ggml-org/llama.cpp.git /build/llama.cpp

WORKDIR /build/llama.cpp
RUN cmake -B build \
    -DGGML_CUDA=ON \
    -DCMAKE_CUDA_ARCHITECTURES="100" \
    -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build --target llama-server -j$(nproc)

# ── Stage 2: Runtime ──
FROM nvidia/cuda:12.8.0-runtime-ubuntu24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/llama.cpp/build/bin/llama-server /usr/local/bin/llama-server

# Model mount point
VOLUME /models

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -sf http://localhost:8080/health || exit 1

ENTRYPOINT ["llama-server"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
```

### 2.3 설계 항목 체크리스트

| # | 항목 | 상세 |
|---|------|------|
| D1-1 | Base 이미지 | `nvidia/cuda:12.8.0-devel-ubuntu24.04` (빌드), `nvidia/cuda:12.8.0-runtime-ubuntu24.04` (실행) |
| D1-2 | Multi-stage | builder → runtime (빌드 도구 제외로 이미지 경량화) |
| D1-3 | CUDA Architecture | `CMAKE_CUDA_ARCHITECTURES="100"` (Blackwell GB10 = SM 100) |
| D1-4 | 빌드 타겟 | `llama-server`만 빌드 (불필요한 바이너리 제외) |
| D1-5 | 버전 핀닝 | `LLAMA_CPP_VERSION` ARG로 태그/커밋 지정 가능 (기본 master) |
| D1-6 | HEALTHCHECK | `/health` 엔드포인트 30초 간격 체크 |
| D1-7 | VOLUME | `/models` 마운트 포인트 선언 |
| D1-8 | ENTRYPOINT/CMD 분리 | 기본 `--host 0.0.0.0 --port 8080`, compose에서 CMD 오버라이드로 모델/포트 지정 |

### 2.4 엣지 케이스

| # | 상황 | 대응 |
|---|------|------|
| EC-D1-A | CUDA 12.8 이미지가 ARM64 미제공 | `12.6.0`으로 fallback, DGX 호스트 CUDA 버전 확인 후 결정 |
| EC-D1-B | Blackwell SM 100 미지원 (llama.cpp 버전 문제) | `CMAKE_CUDA_ARCHITECTURES="90;100"` 으로 확장, 또는 최신 llama.cpp 태그 사용 |
| EC-D1-C | 빌드 시간 과다 (>30분) | `--build-arg LLAMA_CPP_VERSION=b5000` 등 안정 태그 사용, 빌드 캐시 활용 |

---

## 3. D2: gateway.Dockerfile

### 3.1 설계 의도
- Gateway 서비스를 컨테이너화 (FastAPI + uvicorn)
- uv로 의존성 설치 (빠른 설치, lockfile 활용)
- 설정 파일은 볼륨 마운트

### 3.2 파일 내용

**경로**: `docker/gateway.Dockerfile`

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first (cache layer)
COPY services/gateway/pyproject.toml .
RUN uv pip install --system --no-cache -r pyproject.toml

# Copy application code
COPY services/gateway/app/ ./app/

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=5s --retries=3 \
    CMD curl -sf http://localhost:8080/health || exit 1

CMD ["uvicorn", "app.main:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8080"]
```

### 3.3 설계 항목 체크리스트

| # | 항목 | 상세 |
|---|------|------|
| D2-1 | Base 이미지 | `python:3.11-slim` (ARM64 multi-arch 지원) |
| D2-2 | 패키지 매니저 | uv (`ghcr.io/astral-sh/uv:latest`에서 바이너리 복사) |
| D2-3 | 레이어 캐시 | pyproject.toml 먼저 복사 → 의존성 설치 → 소스 복사 (변경 최소화) |
| D2-4 | GATEWAY_CONFIG | 환경변수로 설정 파일 경로 주입 (compose에서 설정) |
| D2-5 | HEALTHCHECK | `/health` 15초 간격 |
| D2-6 | 실행 명령 | `uvicorn app.main:create_app --factory` (기존과 동일) |

### 3.4 엣지 케이스

| # | 상황 | 대응 |
|---|------|------|
| EC-D2-A | uv ARM64 바이너리 미제공 | `pip install` fallback (Dockerfile 내 조건 분기) |
| EC-D2-B | pyproject.toml의 dev 의존성 포함 | `--no-cache -r pyproject.toml`은 기본 의존성만 설치 (dev 제외) |

---

## 4. D3: docker-compose.prod.yml

### 4.1 설계 의도
- 전체 스택을 단일 compose 파일로 관리
- GPU 리소스 할당 (NVIDIA Container Toolkit)
- 서비스 간 내부 네트워크 격리
- 헬스체크 기반 의존성 관리

### 4.2 파일 내용

**경로**: `docker-compose.prod.yml`

```yaml
version: "3.8"

services:
  # ── LLM Servers (3 instances) ──
  llama-9b:
    build:
      context: .
      dockerfile: docker/llama-server.Dockerfile
    container_name: llama-9b
    command:
      - "--host"
      - "0.0.0.0"
      - "--port"
      - "8080"
      - "--model"
      - "/models/${MODEL_9B:-Qwen3.5-9B-Q4_K_M.gguf}"
      - "--n-gpu-layers"
      - "-1"
      - "--ctx-size"
      - "${CTX_SIZE_9B:-32768}"
    volumes:
      - ${MODELS_DIR:-~/models}:/models:ro
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    restart: unless-stopped
    networks:
      - llm-net
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 120s

  llama-27b:
    build:
      context: .
      dockerfile: docker/llama-server.Dockerfile
    container_name: llama-27b
    command:
      - "--host"
      - "0.0.0.0"
      - "--port"
      - "8080"
      - "--model"
      - "/models/${MODEL_27B:-Qwen3.5-27B-Q4_K_M.gguf}"
      - "--n-gpu-layers"
      - "-1"
      - "--ctx-size"
      - "${CTX_SIZE_27B:-32768}"
    volumes:
      - ${MODELS_DIR:-~/models}:/models:ro
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    restart: unless-stopped
    networks:
      - llm-net
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 180s

  llama-coder:
    build:
      context: .
      dockerfile: docker/llama-server.Dockerfile
    container_name: llama-coder
    command:
      - "--host"
      - "0.0.0.0"
      - "--port"
      - "8080"
      - "--model"
      - "/models/${MODEL_CODER:-Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf}"
      - "--n-gpu-layers"
      - "-1"
      - "--ctx-size"
      - "${CTX_SIZE_CODER:-16384}"
    volumes:
      - ${MODELS_DIR:-~/models}:/models:ro
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    restart: unless-stopped
    networks:
      - llm-net
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8080/health"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 180s

  # ── API Gateway ──
  gateway:
    build:
      context: .
      dockerfile: docker/gateway.Dockerfile
    container_name: gateway
    environment:
      - GATEWAY_CONFIG=/app/config/gateway.prod.yaml
    volumes:
      - ./config:/app/config:ro
    ports:
      - "${GATEWAY_PORT:-8080}:8080"
    depends_on:
      llama-9b:
        condition: service_healthy
      llama-27b:
        condition: service_healthy
      llama-coder:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - llm-net
      - infra-net
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8080/health"]
      interval: 15s
      timeout: 5s
      retries: 3

  # ── Infrastructure ──
  postgres:
    image: postgres:16-alpine
    container_name: postgres
    environment:
      POSTGRES_USER: ${DB_USER:-myaicoder}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME:-myaicoder}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped
    networks:
      - infra-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-myaicoder}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: redis
    restart: unless-stopped
    networks:
      - infra-net
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  # ── Monitoring ──
  prometheus:
    image: prom/prometheus:v2.51.0
    container_name: prometheus
    ports:
      - "${PROMETHEUS_PORT:-9090}:9090"
    volumes:
      - ./config/prometheus.prod.yml:/etc/prometheus/prometheus.yml:ro
    restart: unless-stopped
    networks:
      - infra-net
    depends_on:
      gateway:
        condition: service_healthy

  grafana:
    image: grafana/grafana:10.4.0
    container_name: grafana
    ports:
      - "${GRAFANA_PORT:-3000}:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - ./config/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./config/grafana/dashboards:/var/lib/grafana/dashboards:ro
      - grafana_data:/var/lib/grafana
    restart: unless-stopped
    networks:
      - infra-net
    depends_on:
      - prometheus

networks:
  llm-net:
    driver: bridge
  infra-net:
    driver: bridge

volumes:
  postgres_data:
  grafana_data:
```

### 4.3 설계 항목 체크리스트

| # | 항목 | 상세 |
|---|------|------|
| D3-1 | GPU 리소스 예약 | `deploy.resources.reservations.devices` — NVIDIA Container Toolkit 필수 |
| D3-2 | 컨테이너 내부 포트 통일 | 모든 llama-server가 내부 8080 사용, 호스트 포트 매핑 불필요 (Gateway가 Docker 내부 DNS로 접근) |
| D3-3 | 네트워크 분리 | `llm-net` (LLM↔Gateway), `infra-net` (Gateway↔DB/모니터링) |
| D3-4 | 헬스체크 의존성 | Gateway는 3개 LLM 서버 모두 healthy 후 시작 |
| D3-5 | start_period | llama-9b: 120s, llama-27b/coder: 180s (모델 로딩 시간 고려) |
| D3-6 | 모델 볼륨 | `${MODELS_DIR}:/models:ro` — 읽기전용 마운트 |
| D3-7 | 자동 재시작 | `restart: unless-stopped` (시스템 재부팅 후에도 자동 시작) |
| D3-8 | 환경변수 | `.env.prod`에서 주입 (모델 파일명, 포트, DB 비밀번호 등) |
| D3-9 | 호스트 포트 노출 | Gateway(:8080), Prometheus(:9090), Grafana(:3000)만 호스트 노출 |
| D3-10 | DB 포트 비노출 | Postgres, Redis는 호스트에 노출하지 않음 (보안) |
| D3-11 | Postgres 헬스체크 | `pg_isready` 사용 |
| D3-12 | Redis 헬스체크 | `redis-cli ping` 사용 |

### 4.4 네트워크 토폴로지

```
llm-net                          infra-net
┌────────────────────┐   ┌────────────────────────┐
│ llama-9b   :8080   │   │ postgres  :5432        │
│ llama-27b  :8080   │   │ redis     :6379        │
│ llama-coder:8080   │   │ prometheus:9090 ←host  │
│    ↕                │   │ grafana   :3000 ←host  │
│ gateway    :8080 ←──┼───┼── :8080 ←host         │
└────────────────────┘   └────────────────────────┘
```

### 4.5 엣지 케이스

| # | 상황 | 대응 |
|---|------|------|
| EC-D3-A | 128GB 메모리에서 3개 모델 동시 로드 실패 | `CTX_SIZE_*` 줄이기, 또는 llama-coder 서비스를 `profiles: ["full"]`로 분리 |
| EC-D3-B | GPU count: all에서 경쟁 (3개 프로세스 동시 GPU 접근) | DGX Spark 통합메모리라 GPU 메모리 분리 불필요, `count: all` 유지 |
| EC-D3-C | 모델 로딩 중 Gateway 시작 시도 | `depends_on: condition: service_healthy` + `start_period`로 방어 |

---

## 5. D4/D5/D6: 환경 설정 파일

### 5.1 D4: config/gateway.prod.yaml

```yaml
server:
  host: "0.0.0.0"
  port: 8080

auth:
  internal_token: "${INTERNAL_TOKEN}"
  users:
    - api_key_hash: "${ADMIN_API_KEY_HASH}"
      user_id: "admin"
      name: "관리자"
      org: "MyAiCoder"
      role: "admin"

models:
  default: "qwen3.5-9b"
  routes:
    - name: "qwen3.5-9b"
      upstream: "http://llama-9b:8080/v1"
      description: "Qwen 3.5 9B (Fast)"
    - name: "qwen3.5-27b"
      upstream: "http://llama-27b:8080/v1"
      description: "Qwen 3.5 27B (Quality)"
    - name: "qwen3-coder-30b"
      upstream: "http://llama-coder:8080/v1"
      description: "Qwen 3 Coder 30B (Coding)"

rate_limit:
  enabled: true
  roles:
    admin:
      requests_per_minute: 120
      requests_per_hour: 3600
    user:
      requests_per_minute: 30
      requests_per_hour: 500

logging:
  level: "INFO"
  format: "json"
```

### 5.1.1 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D4-1 | upstream URL | Docker 내부 DNS: `http://llama-9b:8080/v1` (localhost 아님) |
| D4-2 | 3개 모델 라우팅 | 각 llama 컨테이너별 독립 upstream |
| D4-3 | 시크릿 | `${INTERNAL_TOKEN}`, `${ADMIN_API_KEY_HASH}` — .env.prod에서 주입 |
| D4-4 | rate_limit | dev와 동일 (필요 시 prod용 조정) |

### 5.2 D5: config/models.prod.yaml

```yaml
environment: prod
models_dir: "/models"
default_model: "qwen3.5-9b"
gateway_url: "http://gateway:8080"

instances:
  - name: "qwen3.5-9b"
    file: "Qwen3.5-9B-Q4_K_M.gguf"
    port: 8080
    container: "llama-9b"
    description: "Qwen 3.5 9B — fast response"
    defaults:
      temperature: 0.0
      max_tokens: 8192

  - name: "qwen3.5-27b"
    file: "Qwen3.5-27B-Q4_K_M.gguf"
    port: 8080
    container: "llama-27b"
    description: "Qwen 3.5 27B — high quality"
    defaults:
      temperature: 0.0
      max_tokens: 8192

  - name: "qwen3-coder-30b"
    file: "Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"
    port: 8080
    container: "llama-coder"
    description: "Qwen 3 Coder 30B — coding specialized"
    defaults:
      temperature: 0.0
      max_tokens: 8192
```

### 5.2.1 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D5-1 | environment | `prod` (dev와 구분) |
| D5-2 | container 필드 | 각 인스턴스에 Docker 컨테이너명 매핑 (관리용) |
| D5-3 | 포트 통일 | 모든 인스턴스 8080 (Docker 내부) |
| D5-4 | gateway_url | Docker 내부 DNS `http://gateway:8080` |

### 5.3 D6: .env.prod.example

```bash
# ── Model Configuration ──
MODELS_DIR=~/models
MODEL_9B=Qwen3.5-9B-Q4_K_M.gguf
MODEL_27B=Qwen3.5-27B-Q4_K_M.gguf
MODEL_CODER=Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf
CTX_SIZE_9B=32768
CTX_SIZE_27B=32768
CTX_SIZE_CODER=16384

# ── Gateway ──
GATEWAY_PORT=8080
INTERNAL_TOKEN=<generate-with-openssl-rand-base64-32>
ADMIN_API_KEY_HASH=sha256:<your-api-key-hash>

# ── Database ──
DB_USER=myaicoder
DB_PASSWORD=<generate-secure-password>
DB_NAME=myaicoder

# ── Monitoring ──
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
GRAFANA_PASSWORD=<generate-secure-password>
```

### 5.3.1 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D6-1 | 시크릿 플레이스홀더 | `<generate-with-...>` 형태로 생성 방법 안내 |
| D6-2 | 모델 파일명 오버라이드 | 기본값은 compose에서 설정, .env로 변경 가능 |
| D6-3 | CTX_SIZE 분리 | 모델별 컨텍스트 크기 독립 설정 |
| D6-4 | .gitignore | `.env.prod`는 반드시 `.gitignore`에 포함 (시크릿 보호) |

---

## 6. D7/D8: 배포 스크립트

### 6.1 D7: scripts/setup-dgx.sh

**목적**: DGX 호스트 사전 검증 + Docker 환경 준비

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=== myAiCoder DGX Setup ==="

# P0: 사전 체크
echo "[1/5] Checking system requirements..."

# P0-1: Architecture
ARCH=$(uname -m)
if [ "$ARCH" != "aarch64" ]; then
    echo "WARNING: Expected aarch64, got $ARCH"
fi

# P0-2: NVIDIA Driver
if ! command -v nvidia-smi &>/dev/null; then
    echo "ERROR: nvidia-smi not found. Install NVIDIA drivers."
    exit 1
fi
echo "  GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)"
echo "  CUDA: $(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)"

# P0-3: NVIDIA Container Toolkit
if ! command -v nvidia-ctk &>/dev/null; then
    echo "ERROR: nvidia-container-toolkit not installed."
    echo "  Install: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
    exit 1
fi
echo "  Container Toolkit: $(nvidia-ctk --version 2>/dev/null || echo 'installed')"

# P0-4: Docker
if ! command -v docker &>/dev/null; then
    echo "ERROR: Docker not installed."
    exit 1
fi
echo "  Docker: $(docker --version)"

# P0-5: Docker GPU test
echo ""
echo "[2/5] Testing Docker GPU access..."
if ! docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu24.04 nvidia-smi &>/dev/null; then
    echo "ERROR: Docker cannot access GPU."
    echo "  Check: nvidia-container-toolkit configuration"
    exit 1
fi
echo "  Docker GPU: OK"

# Setup .env.prod
echo ""
echo "[3/5] Creating .env.prod..."
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ ! -f "$REPO_ROOT/.env.prod" ]; then
    cp "$REPO_ROOT/.env.prod.example" "$REPO_ROOT/.env.prod"
    # Generate secrets
    INTERNAL_TOKEN=$(openssl rand -base64 32)
    sed -i "s|<generate-with-openssl-rand-base64-32>|${INTERNAL_TOKEN}|" "$REPO_ROOT/.env.prod"
    DB_PASS=$(openssl rand -base64 16)
    sed -i "s|<generate-secure-password>|${DB_PASS}|g" "$REPO_ROOT/.env.prod"
    echo "  Created .env.prod (review and update API key hash!)"
else
    echo "  .env.prod already exists, skipping"
fi

# Create models directory
echo ""
echo "[4/5] Checking models directory..."
MODELS_DIR="${MODELS_DIR:-$HOME/models}"
mkdir -p "$MODELS_DIR"
echo "  Models dir: $MODELS_DIR"

# Build images
echo ""
echo "[5/5] Building Docker images..."
cd "$REPO_ROOT"
docker compose -f docker-compose.prod.yml build

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Download models:  ./scripts/download-models.sh"
echo "  2. Review config:    nano .env.prod"
echo "  3. Start services:   docker compose -f docker-compose.prod.yml up -d"
```

### 6.1.1 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D7-1 | 사전 체크 5항목 | Architecture, NVIDIA Driver, Container Toolkit, Docker, GPU Access |
| D7-2 | 시크릿 자동 생성 | `openssl rand -base64 32` (INTERNAL_TOKEN), `openssl rand -base64 16` (DB_PASSWORD) |
| D7-3 | 멱등성 | `.env.prod` 존재 시 skip, `mkdir -p` |
| D7-4 | 이미지 빌드 | `docker compose -f docker-compose.prod.yml build` |
| D7-5 | 실패 시 즉시 종료 | `set -euo pipefail` |

### 6.2 D8: scripts/download-models.sh

**목적**: GGUF 모델 파일 다운로드 (Hugging Face)

```bash
#!/usr/bin/env bash
set -euo pipefail

MODELS_DIR="${MODELS_DIR:-$HOME/models}"
mkdir -p "$MODELS_DIR"

# Model definitions: name|filename|repo|size
MODELS=(
    "Qwen3.5-9B|Qwen3.5-9B-Q4_K_M.gguf|Qwen/Qwen3.5-9B-GGUF|~6GB"
    "Qwen3.5-27B|Qwen3.5-27B-Q4_K_M.gguf|Qwen/Qwen3.5-27B-GGUF|~16GB"
    "Qwen3-Coder-30B|Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf|Qwen/Qwen3-Coder-30B-A3B-Instruct-GGUF|~18GB"
)

echo "=== Model Download ==="
echo "Target directory: $MODELS_DIR"
echo ""

for entry in "${MODELS[@]}"; do
    IFS='|' read -r name filename repo size <<< "$entry"
    filepath="$MODELS_DIR/$filename"

    if [ -f "$filepath" ]; then
        echo "[SKIP] $name already exists ($filepath)"
        continue
    fi

    echo "[DOWNLOAD] $name ($size)"
    echo "  From: https://huggingface.co/$repo"

    if command -v huggingface-cli &>/dev/null; then
        huggingface-cli download "$repo" "$filename" \
            --local-dir "$MODELS_DIR" --local-dir-use-symlinks False
    else
        echo "  huggingface-cli not found, using curl..."
        curl -L -o "$filepath" \
            "https://huggingface.co/$repo/resolve/main/$filename"
    fi

    echo "  Done: $filepath"
    echo ""
done

# Ensure read permission for Docker volume mount
chmod 644 "$MODELS_DIR"/*.gguf 2>/dev/null || true

echo ""
echo "=== Download Complete ==="
ls -lh "$MODELS_DIR"/*.gguf 2>/dev/null || echo "No .gguf files found"
```

### 6.2.1 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D8-1 | 다운로드 도구 | `huggingface-cli` 우선, 없으면 `curl` fallback |
| D8-2 | 멱등성 | 파일 존재 시 SKIP |
| D8-3 | 모델 목록 | 배열로 관리 (추가/제거 용이) |
| D8-4 | HF repo 경로 | 실제 Hugging Face 리포지토리 경로 (검증 필요) |
| D8-5 | 볼륨 권한 보장 | `chmod 644 *.gguf` — Docker 컨테이너 내 프로세스(root/UID)가 읽기 가능하도록 |

### 6.2.2 엣지 케이스

| # | 상황 | 대응 |
|---|------|------|
| EC-D8-A | HF 리포지토리 경로 변경 | MODELS 배열의 repo 필드 수정 |
| EC-D8-B | 다운로드 중 중단 | curl은 부분 파일 남김 → 재실행 시 파일 존재로 SKIP → 수동 삭제 후 재시도 필요 |
| EC-D8-C | DGX 인터넷 접근 불가 | 로컬 PC에서 다운로드 후 scp로 전송 |
| EC-D8-D | 볼륨 마운트 Permission Denied | 호스트 사용자 UID와 컨테이너 프로세스 UID 불일치 시 발생 → `chmod 644`로 전역 읽기 권한 보장 |

---

## 7. D9: config/prometheus.prod.yml

### 7.1 파일 내용

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "gateway"
    static_configs:
      - targets: ["gateway:8080"]
    metrics_path: /metrics
    scrape_interval: 10s

  - job_name: "llama-9b"
    static_configs:
      - targets: ["llama-9b:8080"]
    metrics_path: /metrics
    scrape_interval: 30s

  - job_name: "llama-27b"
    static_configs:
      - targets: ["llama-27b:8080"]
    metrics_path: /metrics
    scrape_interval: 30s

  - job_name: "llama-coder"
    static_configs:
      - targets: ["llama-coder:8080"]
    metrics_path: /metrics
    scrape_interval: 30s
```

### 7.1.1 설계 항목

| # | 항목 | 상세 |
|---|------|------|
| D9-1 | Gateway 메트릭 | `gateway:8080/metrics` (Docker DNS) |
| D9-2 | LLM 메트릭 | llama.cpp `/metrics` 엔드포인트 (빌트인 Prometheus 지원) |
| D9-3 | host.docker.internal 제거 | 모두 Docker 내부 네트워크 사용 (dev와 차이점) |
| D9-4 | scrape_interval | Gateway 10s, LLM 30s (LLM은 변화 느림) |

---

## 8. 구현 순서 (Implementation Order)

| 순서 | 산출물 | 의존성 | 예상 규모 |
|------|--------|--------|----------|
| 1 | D1: llama-server.Dockerfile | 없음 | 신규 파일 |
| 2 | D2: gateway.Dockerfile | 없음 | 신규 파일 |
| 3 | D5: models.prod.yaml | 없음 | 신규 파일 |
| 4 | D4: gateway.prod.yaml | D5 참조 | 신규 파일 |
| 5 | D6: .env.prod.example | D3 참조 | 신규 파일 |
| 6 | D9: prometheus.prod.yml | 없음 | 신규 파일 |
| 7 | D3: docker-compose.prod.yml | D1, D2, D4, D5, D6, D9 | 신규 파일 (핵심) |
| 8 | D8: download-models.sh | 없음 | 신규 파일 |
| 9 | D7: setup-dgx.sh | D3, D6 | 신규 파일 |

**총 산출물**: 9개 신규 파일, 0개 수정 파일

---

## 9. 검증 체크리스트 (Gap Analysis 기준)

| # | 검증 항목 | 성공 기준 |
|---|----------|----------|
| V1 | D1 빌드 성공 | `docker build -f docker/llama-server.Dockerfile .` 에러 없음 |
| V2 | D2 빌드 성공 | `docker build -f docker/gateway.Dockerfile .` 에러 없음 |
| V3 | D3 전체 시작 | `docker compose -f docker-compose.prod.yml up -d` 모든 컨테이너 healthy |
| V4 | D4 Gateway 설정 | 3개 모델 라우팅 동작, upstream Docker DNS 해석 |
| V5 | D5 모델 설정 | prod 환경 값 반영 |
| V6 | D6 시크릿 | 플레이스홀더 없음, .gitignore 포함 |
| V7 | D7 사전 체크 | 5개 항목 모두 PASS, 이미지 빌드 성공 |
| V8 | D8 모델 다운로드 | 멱등성 (SKIP 동작), fallback (curl) 동작 |
| V9 | D9 메트릭 수집 | Prometheus에서 4개 타겟 UP |
| V10 | GPU 접근 | llama-server 컨테이너에서 `nvidia-smi` 실행 가능 |
| V11 | 다중 모델 동시 | 3개 모델 각각 /health 200 OK |
| V12 | Gateway 프록시 | curl로 모델별 chat completion 응답 |
| V13 | 자동 재시작 | `docker kill llama-9b` 후 자동 복구 |
| V14 | 네트워크 격리 | llama 컨테이너는 호스트 포트 미노출 |
