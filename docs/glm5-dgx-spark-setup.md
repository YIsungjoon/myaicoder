# GLM-5 on DGX Spark 분산 추론 가이드

> 작성일: 2026-03-30 (최종 업데이트: 2026-03-30)
> 모델: GLM-5 UD-IQ1_M GGUF (209GB) — [unsloth/GLM-5-GGUF](https://huggingface.co/unsloth/GLM-5-GGUF)
> 인프라: DGX Spark x2 — **llama.cpp RPC 분산 추론 (성공)**
> 상태: ✅ **754B 모델 듀얼 노드 서빙 완료 — 9.2 tok/s**

---

## 1. GLM-5 모델 개요

| 항목 | 값 |
|------|-----|
| 개발사 | Zhipu AI (Z.ai) |
| 공개일 | 2026-02-11 |
| 아키텍처 | Mixture-of-Experts (MoE) + DeepSeek Sparse Attention |
| 총 파라미터 | 754B (활성 40B) |
| 사전학습 데이터 | 28.5T 토큰 |
| 컨텍스트 길이 | 128K (기본), 최대 ~202K |
| 라이선스 | MIT |

### 벤치마크

| 벤치마크 | 점수 |
|----------|------|
| Humanity's Last Exam (HLE w/ Tools) | 50.4 |
| AIME 2026 I | 92.7 |
| SWE-bench Verified | 77.8 |
| GPQA-Diamond | 86.0 |
| BrowseComp w/ Context | 75.9 |

---

## 2. 인프라 현황

### DGX Spark 사양

| 항목 | DGX1 (메인) | DGX2 (워커) |
|------|------------|------------|
| 호스트명 | spark-f0f7 | spark-fe65 |
| Tailscale IP | 100.76.168.99 | 100.78.49.9 |
| OS | Ubuntu (aarch64) | Ubuntu (aarch64) |
| CPU | ARM Grace (20코어) | ARM Grace (20코어) |
| GPU | NVIDIA GB10 (sm_121) | NVIDIA GB10 (sm_121) |
| 통합 메모리 (UMA) | 128GB (~115GB GPU 가용) | 128GB (~115GB GPU 가용) |
| 디스크 | 3.7TB (2.7TB 여유) | 3.7TB (2.2TB 여유) |
| CUDA | 13.0 | 13.0 |
| Python | 3.12.3 | 3.12.3 |
| Docker | 설치됨 | 설치됨 |
| 네트워크 지연 | DGX1 ↔ DGX2: ~2-3ms (Tailscale) | |

### 합산 가용 자원

- 총 메모리: **256GB** (128GB x 2)
- GPU 가용 (UMA): **~230GB** (115GB x 2)
- 총 디스크: **4.9TB 여유**

---

## 3. 분산 추론: llama.cpp RPC (최종 성공)

### 시행착오 기록

| 시도 | 설정 | 결과 |
|------|------|------|
| 1차 | `-ngl 999 --tensor-split 0.5,0.5` | ❌ CUDA 메모리 에러 (mmap 충돌) |
| 2차 | `-ngl 0 --tensor-split 0.5,0.5` | ❌ RPC 분산 안 됨 (CPU only에서는 RPC 비활성) |
| 3차 | `-ngl 999 --tensor-split 0.4,0.6` | ❌ 텐서 전송 실패 (mmap 충돌) |
| **4차** | **`-ngl 999 --tensor-split 0.5,0.5 --no-mmap`** | **✅ 성공!** |

### 핵심 발견: `--no-mmap` 필수

DGX Spark의 통합 메모리(UMA) 환경에서 mmap이 CUDA 메모리 할당과 충돌함.
`--no-mmap`으로 직접 메모리 할당하면 RPC 분산이 정상 작동.

> NVIDIA 포럼에서는 "RPC doesn't make much sense on Spark"라는 의견이 있었으나,
> `--no-mmap` 플래그 사용 시 **정상 동작 확인됨** (2026-03-30).

### 성공 결과

| 항목 | 값 |
|------|-----|
| 모델 | GLM-5 754B (UD-IQ1_M, 209GB GGUF) |
| DGX1 (CUDA0) | 106.5 GB |
| DGX2 (RPC0) | 103.0 GB |
| CPU 버퍼 | 0.5 GB |
| 디코드 속도 | **9.2 tok/s** |
| 프롬프트 처리 | **13.4 tok/s** |
| 컨텍스트 크기 | 2048 |

### 분산 추론 방식 비교 (최종)

| 방식 | 모델 형식 | DGX Spark 적합도 | 비고 |
|------|----------|:---:|------|
| **llama.cpp RPC + --no-mmap** | **GGUF** | **✅ 성공** | **현재 사용 중** |
| vLLM + Ray | safetensors | ⚠️ 가능하나 복잡 | sm_121 패치 필요, 모델 크기 제약 |
| EXO | safetensors/GGUF | 미검증 | 설정 간편하나 GLM-5 호환성 불확실 |
| KTransformers | safetensors | 미검증 | ARM64 호환성 미확인 |

---

## 4. 실행 절차 (검증 완료)

### 아키텍처

```
┌──────────────────────────┐     TCP/50052 (Tailscale)    ┌──────────────────────────┐
│      DGX1 (메인)          │ ◄──────────────────────────► │      DGX2 (워커)          │
│                           │        ~2ms latency          │                           │
│  llama-server             │                              │  rpc-server               │
│  - CUDA0: 106.5 GB       │                              │  - RPC0: 103.0 GB         │
│  - API 서빙 (:8080)      │                              │  - 레이어 수신/처리        │
│  - CPU 버퍼: 0.5 GB      │                              │                           │
└──────────────────────────┘                              └──────────────────────────┘
```

### Step 1: DGX2 rpc-server 시작

```bash
ssh dgx2
nohup ~/llama.cpp/build/bin/rpc-server -H 0.0.0.0 -p 50052 > /tmp/rpc-server.log 2>&1 &
```

### Step 2: DGX1 llama-server 시작

```bash
ssh dgx1
~/llama.cpp/build/bin/llama-server \
  -m ~/models/glm-5/UD-IQ1_M/GLM-5-UD-IQ1_M-00001-of-00006.gguf \
  --rpc 100.78.49.9:50052 \
  -ngl 999 \
  --tensor-split 0.5,0.5 \
  -c 2048 \
  --no-mmap \
  --host 0.0.0.0 \
  --port 8080
```

> **`--no-mmap` 필수!** DGX Spark UMA 환경에서 mmap은 CUDA 메모리 할당과 충돌함.
> 이 플래그 없이는 CUDA 메모리 에러 또는 텐서 전송 실패 발생.

### Step 3: 테스트

```bash
curl http://100.76.168.99:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "glm-5",
    "messages": [{"role": "user", "content": "안녕하세요, 당신은 누구인가요?"}],
    "max_tokens": 200
  }'
```

### 검증된 성능 (2026-03-30)

| 항목 | 값 |
|------|-----|
| 디코드 속도 | 9.2 tok/s |
| 프롬프트 처리 | 13.4 tok/s |
| 모델 로딩 시간 | ~5-8분 (209GB, --no-mmap) |
| 컨텍스트 크기 | 2048 |
| API 호환 | OpenAI Chat Completions API |

---

## 5. 사전 준비 사항

### llama.cpp 빌드 (양쪽 노드)

```bash
cd ~/llama.cpp
git checkout master && git pull origin master
cmake -B build -DGGML_RPC=ON -DGGML_CUDA=ON
cmake --build build --config Release -j$(nproc)
```

### 모델 다운로드 (DGX1만)

```bash
source ~/hf-env/bin/activate
hf download unsloth/GLM-5-GGUF --include "UD-IQ1_M/*" --local-dir ~/models/glm-5/
```

> RPC 방식에서는 DGX1에만 모델 파일이 있으면 됨. DGX2는 rpc-server로 레이어만 수신.

---

## 6. 주의사항 및 트러블슈팅

### 필수 설정

| 설정 | 이유 |
|------|------|
| `--no-mmap` | DGX Spark UMA에서 mmap과 CUDA 메모리 충돌 방지. **없으면 100% 실패** |
| `-ngl 999` | 모든 레이어를 GPU에 오프로드 (RPC 분산 활성화) |
| `--tensor-split 0.5,0.5` | 양쪽 균등 분배 (메모리 대칭) |

### RPC 버전 경고

```
WARNING: RPC server version mismatch: 3.6.0
```
양쪽 llama.cpp 버전이 다르면 발생. 기능적 문제 없으나, 양쪽을 같은 커밋으로 빌드 권장.

### 메모리 부족 시

- DGX1/2에서 다른 프로세스(Docker 컨테이너 등)가 메모리를 점유 중이면 OOM 발생
- `docker stop` 불필요한 컨테이너 정리 후 재시도
- 캐시 비우기: `sync && echo 3 | sudo tee /proc/sys/vm/drop_caches`

### 시행착오 기록 (참고)

| 시도 | 설정 | 결과 | 원인 |
|------|------|------|------|
| 1차 | `-ngl 999` (mmap 기본) | CUDA 메모리 크래시 | mmap과 UMA 충돌 |
| 2차 | `-ngl 0` | RPC 미작동 | GPU 레이어 0이면 RPC 비활성 |
| 3차 | `-ngl 999 --tensor-split 0.4,0.6` (mmap 기본) | 텐서 전송 실패 | mmap과 UMA 충돌 |
| **4차** | **`--no-mmap` 추가** | **✅ 성공** | 직접 메모리 할당으로 충돌 해소 |

---

## 7. GGUF 양자화 모델 참고 목록

출처: https://huggingface.co/unsloth/GLM-5-GGUF/tree/main

### 2대 합산 ~230GiB 기준

| 양자화 | 크기 | 적재 가능 | 비고 |
|--------|------|:---:|------|
| UD-IQ2_XXS | 241 GB | ⚠️ | KV캐시 포함 시 부족 |
| **UD-IQ1_M** | **224 GB (209GB 실측)** | **✅** | **현재 사용 중** |
| UD-IQ1_S | 204 GB | ✅ | 품질 약간 낮음 |
| UD-TQ1_0 | 176 GB | ✅ | 단일파일, 실험적 |

---

## 8. 현재 상태

### 완료 사항 (2026-03-30)

- [x] DGX1/2 환경 분석 및 사양 문서화
- [x] llama.cpp RPC 빌드 (DGX1: GGML_RPC=ON, GGML_CUDA=ON)
- [x] GLM-5 UD-IQ1_M GGUF 다운로드 (DGX1, 209GB)
- [x] llama.cpp RPC 분산 실행 — **`--no-mmap`으로 성공**
- [x] API 추론 테스트 통과 (9.2 tok/s)
- [x] vLLM + Ray 테스트 (NCCL 연결 성공, sm_121 패치 필요 확인)

### 다음 단계

- [ ] 장시간 안정성 테스트 (1시간+ 연속 추론)
- [ ] Gateway 연동 (프록시 설정 변경: upstream → DGX1:8080)
- [ ] 컨텍스트 크기 최적화 (2048 → 4096+)
- [ ] 더 큰 양자화(UD-IQ2_XXS) 테스트 가능 여부 재검토

---

## 9. 대안 방식 참고

### vLLM + Ray

- spark-vllm-docker로 sm_121 패치된 이미지 빌드 완료 (양쪽 보유)
- NCCL 통신 성공 확인 (`world_size=2, rank 0/1`)
- safetensors 모델 필요 — INT4-mixed가 실제 ~400GB로 메모리 부족
- `--gpu-memory-utilization 0.85` 필수 (기본 0.9는 OOM)

### EXO

- 미검증. 설정 간편하나 GLM-5 호환성 불확실

---

## 10. 참고 링크

### 모델
- GLM-5 GGUF: https://huggingface.co/unsloth/GLM-5-GGUF
- GLM-5 공식: https://huggingface.co/zai-org/GLM-5
- 논문: https://huggingface.co/papers/2602.15763

### DGX Spark
- llama.cpp DGX Spark 가이드: https://github.com/ggml-org/llama.cpp/discussions/16514
- Arm llama.cpp GPU 빌드: https://learn.arm.com/learning-paths/laptops-and-desktops/dgx_spark_llamacpp/2_gb10_llamacpp_gpu/
- spark-vllm-docker: https://github.com/eugr/spark-vllm-docker
- NVIDIA Stacked Sparks: https://build.nvidia.com/spark/vllm/stacked-sparks
- EXO + DGX Spark: https://blog.exolabs.net/nvidia-dgx-spark/

### 프레임워크
- llama.cpp RPC: https://github.com/ggml-org/llama.cpp/blob/master/tools/rpc/README.md
- vLLM: https://docs.vllm.ai/
- EXO: https://github.com/exo-explore/exo
