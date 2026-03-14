# Design: gateway-internal-api

**Feature**: gateway-internal-api
**날짜**: 2026-03-14
**Phase**: Design
**Level**: Enterprise
**Plan Reference**: `docs/pdca/01-plan/features/gateway-internal-api.plan.md`
**Design Source**: `docs/pdca/02-design/features/model-management.design.md` 섹션 7.1

---

## 1. 설계 개요

dev 환경에서 CLI `model switch` 후 Gateway 라우팅을 동기화하는 내부 API를 구축한다.
범위가 작고 설계가 model-management에서 이미 확정되었으므로, 핵심만 명세한다.

### 변경 범위

| 위치 | 변경 내용 |
|------|----------|
| `gateway/app/router.py` | `ModelRouter.reload()` 메서드 추가 |
| `gateway/app/routes/internal.py` | 신규 — `POST /internal/routes/reload` |
| `gateway/app/config.py` | `AuthConfig`에 `internal_token` 필드 추가 |
| `gateway/app/main.py` | internal 라우터 등록 |
| `gateway/gateway.yaml.example` | `internal_token` 설정 예시 |
| `gateway/tests/test_internal.py` | 신규 테스트 |

## 2. 모듈 상세 설계

### 2.1 ModelRouter.reload() (`router.py` 수정)

```python
class ModelRouter:
    # ... 기존 코드 유지 ...

    def reload(self, model_name: str, upstream: str) -> None:
        """Reload routing for dev environment model switch.

        After switch, all model names route to the same upstream
        (single vLLM instance on single port in dev).
        """
        self._default_upstream = upstream
        for name in self._routes:
            self._routes[name] = upstream
```

- 동기 메서드 — await 불필요
- dev 환경에서는 모든 route가 같은 port를 가리킴
- prod에서는 이 API 자체를 호출할 일이 없음 (Always-on)

### 2.2 Internal 라우터 (`routes/internal.py` 신규)

```python
from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel

logger = structlog.get_logger("gateway.internal")

router = APIRouter(prefix="/internal", tags=["internal"])


class ReloadRequest(BaseModel):
    current_model: str
    port: int


@router.post("/routes/reload")
async def reload_routes(
    request: Request,
    body: ReloadRequest,
    x_internal_token: str = Header(),
) -> dict:
    """Reload model routing after dev environment switch.

    Called by CLI after successful model switch.
    Requires X-Internal-Token header for authentication.
    """
    expected = request.app.state.config.auth.internal_token
    if not expected or x_internal_token != expected:
        raise HTTPException(status_code=403, detail="Invalid internal token")

    upstream = f"http://localhost:{body.port}/v1"
    request.app.state.model_router.reload(body.current_model, upstream)

    logger.info(
        "routes_reloaded",
        current_model=body.current_model,
        upstream=upstream,
    )

    return {"status": "ok", "current_model": body.current_model, "upstream": upstream}
```

#### 설계 결정

| 결정 | 근거 |
|------|------|
| Pydantic `ReloadRequest` | 요청 body 검증 (current_model, port 필수) |
| `Header()` | FastAPI가 누락 시 자동 422 반환 |
| `/v1` 라우터와 분리 | 사용자 인증(Bearer)과 내부 인증(X-Internal-Token) 독립 |
| Rate limiting 미적용 | `/internal` 경로는 `/v1`이 아니므로 rate limit dependency 미적용 |

### 2.3 Config 확장 (`config.py`)

```python
class AuthConfig(BaseModel):
    users: list[UserConfig] = []
    internal_token: str = ""  # 추가 — 비어있으면 내부 API 비활성화
```

`internal_token`이 빈 문자열이면 모든 내부 API 요청을 거부한다 (안전 기본값).

### 2.4 main.py 수정

```python
from .routes.internal import router as internal_router

# 라우터 등록 (health, internal은 인증 없음 / v1은 인증 필요)
app.include_router(health_router)
app.include_router(internal_router)  # 추가
app.include_router(v1_router)
```

## 3. 시퀀스 다이어그램

### E2E: CLI switch → Gateway reload

```
User: myaicoder model switch qwen3-coder-30b
  │
  ├─ ModelManager.switch_model()
  │   ├─ VLLMProcessManager.stop(:8001)
  │   └─ VLLMProcessManager.start(qwen3-coder-30b, :8001)
  │
  ├─ ModelManager._notify_gateway()  [이미 구현됨]
  │   └─ POST http://localhost:8080/internal/routes/reload
  │        Body: {"current_model": "qwen3-coder-30b", "port": 8001}
  │        Header: X-Internal-Token: <secret>
  │
  └─ Gateway
      ├─ 인증: X-Internal-Token 검증 ✓
      ├─ ModelRouter.reload("qwen3-coder-30b", "http://localhost:8001/v1")
      │   └─ 모든 routes → http://localhost:8001/v1
      └─ Response: {"status": "ok", "current_model": "qwen3-coder-30b"}
```

## 4. 테스트 전략

| 테스트 | 대상 | 주요 케이스 |
|--------|------|-----------|
| `test_reload_success` | 정상 reload | 올바른 토큰 + body → 200 + 라우팅 변경 확인 |
| `test_reload_invalid_token` | 인증 실패 | 틀린 토큰 → 403 |
| `test_reload_missing_token` | 헤더 누락 | X-Internal-Token 없음 → 422 |
| `test_reload_empty_config_token` | 미설정 | config의 internal_token이 빈 문자열 → 403 |
| `test_reload_updates_routing` | 라우팅 검증 | reload 후 resolve()가 새 upstream 반환 |
| `test_router_reload_method` | ModelRouter 단위 | reload() 호출 후 모든 routes 갱신 |

## 5. 구현 순서

| 순서 | 작업 | 파일 |
|------|------|------|
| 1 | `AuthConfig`에 `internal_token` 추가 | `config.py` |
| 2 | `ModelRouter.reload()` 메서드 추가 | `router.py` |
| 3 | `routes/internal.py` 생성 | 신규 |
| 4 | `main.py`에 internal 라우터 등록 | `main.py` |
| 5 | 테스트 작성 | `tests/test_internal.py` |
| 6 | `gateway.yaml.example` 업데이트 | example |

## 6. 에러 처리

| 상황 | 처리 |
|------|------|
| X-Internal-Token 누락 | HTTP 422 (FastAPI Header 자동 검증) |
| X-Internal-Token 불일치 | HTTP 403 "Invalid internal token" |
| internal_token 미설정 (빈 문자열) | HTTP 403 (안전 기본값) |
| body 필드 누락 | HTTP 422 (Pydantic 검증) |
| Gateway 미실행 시 CLI 호출 | CLI 측 best-effort, 무시 (이미 구현) |
