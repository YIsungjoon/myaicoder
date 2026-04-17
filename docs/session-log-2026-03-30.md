# 세션 로그: 2026-03-30

## 개요

DGX Spark 2대에서 GLM-5 754B 모델 분산 추론 환경 구축 + myAiCoder 코드베이스 머지 작업.

---

## 1. DGX Spark 환경 확인

### 접속 테스트
- DGX1 (spark-f0f7, 100.76.168.99): SSH 접속 OK, NVIDIA GB10, 128GB UMA, CUDA 13.0
- DGX2 (spark-fe65, 100.78.49.9): SSH 접속 OK, NVIDIA GB10, 128GB UMA, CUDA 13.0
- 네트워크 지연: ~2-3ms (Tailscale)

### 기존 서비스 정리
- DGX1: llama-server (Qwen3.5-4B) 종료
- DGX2: Docker 컨테이너 llama-coder, llama-27b, llama-9b 종료 (systemd 아닌 Docker로 실행 중이었음)
- DGX2 유지 서비스: gateway, grafana, prometheus, postgres, redis

---

## 2. GLM-5 모델 선택 과정

### GGUF 양자화 목록 조사
- 출처: https://huggingface.co/unsloth/GLM-5-GGUF
- 27개 양자화 모델 전체 비교표 작성 → `docs/glm5-dgx-spark-setup.md`에 문서화

### 메모리 계산 (GiB 단위 주의)
- DGX Spark 1대 총 메모리: 128GB = **119GiB**
- 2대 합산 가용: ~**228GiB** (OS/런타임 제외)
- UD-IQ2_XXS (241GB ≈ 225GiB) + KV캐시 → 여유 0 → **불가**
- **UD-IQ1_M (224GB ≈ 209GB 실측)** 선택 → 다운로드 완료

### safetensors 모델 크기 오류 발견
- Intel/GLM-5-int4-mixed-AutoRound: HuggingFace API `usedStorage`=122GB
- 실제 safetensors 합산: **~400GB** ("mixed" 양자화 — Expert만 INT4, 나머지 BF16)
- 다운로드 중단 및 삭제

---

## 3. llama.cpp RPC 분산 추론

### 사전 준비
- DGX1 llama.cpp 리빌드: `GGML_RPC=ON, GGML_CUDA=ON` (기존 OFF)
- DGX2: 이미 RPC 빌드 완료
- 모델 다운로드: `hf download unsloth/GLM-5-GGUF --include "UD-IQ1_M/*"` (209GB, ~40분)

### 시행착오 (4회)

| 시도 | 설정 | 결과 | 원인 |
|------|------|------|------|
| 1차 | `-ngl 999 --tensor-split 0.5,0.5` | ❌ CUDA 메모리 크래시 | mmap과 UMA 충돌 |
| 2차 | `-ngl 0` | ❌ RPC 미작동 | GPU 레이어 0이면 RPC 비활성 |
| 3차 | `-ngl 999 --tensor-split 0.4,0.6` | ❌ 텐서 전송 실패 | mmap과 UMA 충돌 |
| **4차** | **`--no-mmap` 추가** | **✅ 성공** | 직접 메모리 할당으로 충돌 해소 |

### 핵심 발견
- **`--no-mmap` 필수**: DGX Spark UMA 환경에서 mmap이 CUDA 메모리 할당과 충돌
- NVIDIA 포럼에서는 "RPC doesn't make sense on Spark"라는 의견이 있었으나, `--no-mmap`으로 **정상 작동 확인**

### 최종 성공 결과
- DGX1 (CUDA0): 106.5 GB / DGX2 (RPC0): 103.0 GB
- 디코드: **9.2 tok/s** (ctx=2048), **6.2 tok/s** (ctx=8192)
- 프롬프트: 13.4 tok/s
- API: OpenAI Chat Completions 호환

### 실행 명령어 (검증 완료)

```bash
# DGX2: rpc-server
nohup ~/llama.cpp/build/bin/rpc-server -H 0.0.0.0 -p 50052 > /tmp/rpc-server.log 2>&1 &

# DGX1: llama-server
~/llama.cpp/build/bin/llama-server \
  -m ~/models/glm-5/UD-IQ1_M/GLM-5-UD-IQ1_M-00001-of-00006.gguf \
  --rpc 100.78.49.9:50052 \
  -ngl 999 --tensor-split 0.5,0.5 \
  -c 8192 --no-mmap \
  --host 0.0.0.0 --port 8080
```

### 엔드포인트
- Base URL: `http://100.76.168.99:8080`
- Chat: `POST /v1/chat/completions`
- 컨텍스트: 8,192 토큰

---

## 4. vLLM + Ray 테스트 (참고)

### spark-vllm-docker
- DGX1에서 빌드 완료 (`vllm-node:latest`, sm_121 패치 포함)
- DGX2로 이미지 복사 완료 (docker save/scp/load)

### 클러스터 테스트 결과
- Ray 클러스터 연결: ✅ (2 노드, 2 GPU, 167GiB)
- NCCL 통신: ✅ (world_size=2, rank 0/1)
- 서빙: ⚠️ `--gpu-memory-utilization 0.9` 기본값으로 OOM → 0.85로 해결 가능
- sm_121: `vllm-node` 이미지로 해결 (기존 `cu130-nightly`는 sm_120까지만 지원)

### safetensors 모델 문제
- GLM-5-FP8: 754GB → 2대 합산 256GB에 불가
- GLM-5-NVFP4: 406GB → 불가
- GLM-5-int4-mixed: 실제 400GB → 불가
- **결론: vLLM용 GLM-5는 현재 DGX Spark 2대로 불가. GGUF가 유일한 선택지**

---

## 5. myAiCoder 코드베이스 머지

### 분기 상태
- 로컬 (2개 커밋): Security Hardening, Gateway 동시성 버그 수정
- 리모트 (7개 커밋): Gateway/Tools 패키지 재구성, Middleware Stack 아키텍처

### 머지 결과
- 충돌 1건: `services/gateway/app/proxy/forward.py` (import 경로) → 리모트 기준 해결
- 머지 커밋: `7e14cfc`
- 백업 브랜치: `backup/local-security-fixes`

### gap-detector 검증
- 종합 점수: **99% PASS**
- Gateway import: 100% / Tools import: 100% / 설계-구현 일치: 97%
- 의도적 개선 3건: FilesystemMiddleware 예외처리, SubAgent.keywords, PlanningMiddleware 함수 추출
- 설계 문서 3건 업데이트 완료

---

## 6. Blender MCP 연동 조사

### blender-mcp 구조
- MCP 서버가 Blender Addon과 소켓 통신 (도구 제공)
- LLM API 직접 호출 없음 → AI 클라이언트가 도구를 호출하는 구조

### llama.cpp 연동 방안
1. **Open WebUI + MCP** (단기 검증): Docker 한 줄로 설치, 웹 UI 제공
2. **커스텀 MCP 클라이언트** (장기 본 구현): myAiCoder에 MCP 클라이언트 내장
- 핵심 과제: GLM-5 1-bit 양자화의 tool calling 품질 검증 필요

---

## 7. 생성/수정된 문서

| 문서 | 내용 |
|------|------|
| `docs/glm5-dgx-spark-setup.md` | GLM-5 분산 추론 가이드 (전면 작성 + 3회 업데이트) |
| `docs/pdca/02-design/features/api-gateway-refactoring.design.md` | routes/metrics.py 분리 반영 |
| `docs/pdca/02-design/features/deepagent-alignment.design.md` | SubAgent.keywords, 예외처리, 함수 추출 3건 반영 |
| `docs/session-log-2026-03-30.md` | 본 세션 로그 |

---

## 8. 현재 상태 (세션 종료 시점)

### 실행 중인 서비스
| 서비스 | 위치 | 상태 |
|--------|------|------|
| GLM-5 llama-server (8080) | DGX1 | ✅ 운영 중 |
| rpc-server (50052) | DGX2 | ✅ 운영 중 |
| gateway (8080) | DGX2 Docker | ✅ 운영 중 |
| grafana (3000) | DGX2 Docker | ✅ 운영 중 |
| prometheus (9090) | DGX2 Docker | ✅ 운영 중 |
| postgres | DGX2 Docker | ✅ 운영 중 |
| redis | DGX2 Docker | ✅ 운영 중 |

### 디스크 사용
| 위치 | 내용 | 크기 |
|------|------|------|
| DGX1 ~/models/glm-5/UD-IQ1_M/ | GLM-5 GGUF | 209GB |
| DGX1 ~/models/glm-5/UD-IQ1_M/ (GGUF) | 사용 중 | - |
| DGX1 ~/spark-vllm-docker/ | vLLM Docker 빌드 환경 | ~1GB |
| DGX1 /tmp/vllm-node.tar | vllm-node 이미지 tar | 17GB (삭제 가능) |

### 다음 작업 (추천)
1. 장시간 안정성 테스트 (GLM-5 연속 추론)
2. Gateway upstream을 GLM-5 엔드포인트로 변경
3. Blender MCP 연동 (Open WebUI 검증 → 커스텀 클라이언트)
4. 불필요 파일 정리 (`/tmp/vllm-node.tar`, HF 캐시 등)
