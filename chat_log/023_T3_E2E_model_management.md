# 023. T3 Model Management E2E 테스트 완료

**기록 시점**: 2026-03-14

---

## 1. E2E 테스트 결과

| ID | 테스트 | 결과 | 비고 |
|----|--------|:----:|------|
| T3-1 | `myaicoder model list` | PASS | 3개 모델 (9B/27B/30B), 크기 정확 |
| T3-2 | `myaicoder model launch` | PASS | llama-server 자동 시작, health check 통과 |
| T3-3 | `myaicoder model switch` (9B→27B) | PASS | stop→start 순차 전환, 27B 로드 성공 |
| T3-4 | 즉시 요청 (race condition) | PASS | switch 직후 sleep 없이 즉시 응답 |
| T3-5 | `myaicoder model status` | PASS | 환경/모델 정보 출력 |
| - | Switch back (27B→9B) | PASS | VRAM 복귀 정상 |

## 2. 발견 및 수정한 이슈

### 2.1 config/ 경로 탐색 실패

**문제**: `Path.cwd()`가 `services/myaicoder/`를 반환하므로 프로젝트 루트의 `config/models.yaml`을 찾지 못함.

**해결**: `_find_project_root()` 메서드 추가 — `.git` 디렉토리를 기준으로 프로젝트 루트 탐색.

### 2.2 CLI에서 backend_command 미전달

**문제**: `VLLMProcessManager()`가 기본값으로 생성되어 config의 `backend`/`backend_command` 무시.

**해결**: `_build_model_manager()` 헬퍼 함수 추가 — config에서 backend 정보를 읽어 ProcessManager에 전달.

### 2.3 model list의 loaded 상태 미표시

**현상**: CLI가 일회성 프로세스이므로 launch 후 별도 CLI 실행 시 ProcessManager가 이전 프로세스 정보를 모름.

**판단**: 설계상 예상된 동작. 실제 프로세스는 정상 동작하며, health check로 상태 확인 가능.

## 3. 코드 변경 요약

| 파일 | 변경 |
|------|------|
| `models/config.py` | `_find_project_root()` 추가, config 검색 경로에 git root 추가 |
| `cli.py` | `_build_model_manager()` 헬퍼 추가, model 커맨드 4개 리팩토링 |
| `tests/test_config.py` | 기본값 테스트 수정 (project root config 감지 반영) |
