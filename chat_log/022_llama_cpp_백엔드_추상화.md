# 022. llama.cpp 백엔드 추상화 — ProcessManager 이중 백엔드 지원

**기록 시점**: 2026-03-14
**컨텍스트**: T3 Model Management E2E 준비

---

## 1. 변경 배경

추론 엔진이 vLLM → llama.cpp로 전환되면서, `VLLMProcessManager`의 커맨드 빌드 로직이
llama.cpp의 `llama-server`와 호환되지 않았다.

| 항목 | vLLM | llama.cpp |
|------|------|-----------|
| 명령어 | `vllm serve <model>` | `llama-server --model <model>` |
| GPU 설정 | `--gpu-memory-utilization 0.5` | `--n-gpu-layers -1` |
| 컨텍스트 | `--max-model-len 32768` | `--ctx-size 32768` |
| Health | `GET /health` | `GET /health` (동일) |

## 2. 변경 내용

### 2.1 config.py

- `LlamaCppArgs` 데이터클래스 신규 (n_gpu_layers, ctx_size, extra_args)
- `ModelProfile`에 `llama_cpp_args` 필드 추가
- `ModelsConfig`에 `backend` ("llama-cpp" | "vllm") 및 `backend_command` (실행 파일 경로) 추가
- YAML 파서에 `llama_cpp_args`, `backend`, `backend_command` 파싱 추가

### 2.2 process.py

- `VLLMProcessManager.__init__()`: `vllm_command` → `backend` + `command` 인수로 전환
- `_build_command()`: 백엔드별 분기 → `_build_vllm_command()` / `_build_llama_cpp_command()`
- `start()`: `llama_cpp_args` 파라미터 추가
- 바이너리 사전 검증 에러 메시지: 백엔드별 안내 (vLLM: pip install, llama.cpp: 빌드 가이드)

### 2.3 manager.py

- `switch_model()`: `llama_cpp_args=profile.llama_cpp_args` 전달 (start + rollback 모두)
- `launch()`: 동일하게 `llama_cpp_args` 전달

### 2.4 config/models.yaml

```yaml
backend: "llama-cpp"
backend_command: "/home/buttumaklevit/llm-server-env/llama.cpp/build/bin/llama-server"
```

### 2.5 tests/test_process.py

- `TestBuildCommandVLLM`: vLLM 커맨드 빌드 테스트 (기존 유지)
- `TestBuildCommandLlamaCpp`: llama-cpp 커맨드 빌드 테스트 (신규)
- `TestBinaryCheck`: `vllm_command` → `command` 인수 수정

## 3. 테스트 결과

| 서비스 | 결과 |
|--------|------|
| MyAiCoder | 101 passed, 4 skipped (기존 99 → 101) |
| Gateway | 43 passed |
| Ruff | All checks passed |

## 4. 하위 호환성

- `backend` 기본값은 `"llama-cpp"` (현재 실환경)
- `backend: "vllm"` 설정 시 기존 vLLM 방식으로 동작
- Health check (`GET /health`)는 양쪽 모두 동일하므로 변경 없음
