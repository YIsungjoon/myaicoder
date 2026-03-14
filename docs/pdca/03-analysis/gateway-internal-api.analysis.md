# gateway-internal-api Analysis Report

> **Analysis Type**: Gap Analysis (Design vs Implementation)
>
> **Project**: myAiCoder Gateway
> **Analyst**: bkit-gap-detector
> **Date**: 2026-03-14
> **Design Doc**: [gateway-internal-api.design.md](../02-design/features/gateway-internal-api.design.md)

---

## 1. Analysis Overview

### 1.1 Analysis Purpose

`gateway-internal-api` 피처의 Design 문서(섹션 1-6)와 실제 구현 코드를 1:1 비교하여
PDCA Check 단계의 Match Rate를 산출한다.

### 1.2 Analysis Scope

- **Design Document**: `docs/pdca/02-design/features/gateway-internal-api.design.md`
- **Implementation Path**: `services/gateway/app/` (router.py, routes/internal.py, config.py, main.py)
- **Test Path**: `services/gateway/tests/test_internal.py`
- **Config Example**: `services/gateway/gateway.yaml.example`
- **Analysis Date**: 2026-03-14

---

## 2. Gap Analysis (Design vs Implementation)

### 2.1 ModelRouter.reload() (Design 섹션 2.1)

| 항목 | Design | Implementation | Status |
|------|--------|----------------|--------|
| 메서드 시그니처 | `reload(self, model_name: str, upstream: str) -> None` | `reload(self, model_name: str, upstream: str) -> None` | ✅ Match |
| `_default_upstream` 갱신 | `self._default_upstream = upstream` | `self._default_upstream = upstream` | ✅ Match |
| 모든 routes 덮어쓰기 | `for name in self._routes: self._routes[name] = upstream` | 동일 | ✅ Match |
| 동기 메서드 (await 불필요) | 명시 | `def reload` (동기) | ✅ Match |
| logger.info 호출 | Design에 없음 | `logger.info("routes_reloaded", ...)` 추가 | ⚠️ Added |

**소결**: Design과 완전히 일치. logger 호출은 Design의 routes/internal.py에 명시되어 있으므로
router.py에도 추가된 것은 합리적인 보강 (중복 로그지만 무해).

### 2.2 POST /internal/routes/reload (Design 섹션 2.2)

| 항목 | Design | Implementation | Status |
|------|--------|----------------|--------|
| 라우터 prefix | `/internal` | `/internal` | ✅ Match |
| 라우터 tags | `["internal"]` | `["internal"]` | ✅ Match |
| 엔드포인트 경로 | `POST /routes/reload` | `POST /routes/reload` | ✅ Match |
| ReloadRequest 모델 | `current_model: str, port: int` | `current_model: str, port: int` | ✅ Match |
| X-Internal-Token Header | `Header()` | `Header()` | ✅ Match |
| 토큰 검증 로직 | `not expected or x_internal_token != expected` | 동일 | ✅ Match |
| 403 에러 메시지 | `"Invalid internal token"` | `"Invalid internal token"` | ✅ Match |
| upstream 생성 | `f"http://localhost:{body.port}/v1"` | 동일 | ✅ Match |
| logger.info 호출 | `"routes_reloaded"` + kwargs | 동일 | ✅ Match |
| 응답 형식 | `{"status": "ok", "current_model": ..., "upstream": ...}` | 동일 | ✅ Match |
| 모듈 docstring | 없음 | `"""Internal management API — ..."""` 추가 | ⚠️ Added |
| import 순서 | `HTTPException, Header, Request` | `Header, HTTPException, Request` (알파벳순) | ⚠️ Minor |

**소결**: 기능적으로 100% 일치. import 순서 차이는 알파벳 정렬 관행에 의한 것으로 동작 영향 없음.

### 2.3 Config 확장 (Design 섹션 2.3)

| 항목 | Design | Implementation | Status |
|------|--------|----------------|--------|
| `AuthConfig.internal_token` 필드 | `internal_token: str = ""` | `internal_token: str = ""` | ✅ Match |
| 빈 문자열 = 비활성화 | 명시 | 코드에서 `not expected` 체크로 구현 | ✅ Match |

**소결**: 완전 일치.

### 2.4 main.py 수정 (Design 섹션 2.4)

| 항목 | Design | Implementation | Status |
|------|--------|----------------|--------|
| import 구문 | `from .routes.internal import router as internal_router` | 동일 | ✅ Match |
| 라우터 등록 순서 | health → internal → v1 | health → internal → v1 | ✅ Match |
| 인증 분리 (internal != v1) | 명시 | internal은 자체 토큰, v1은 Bearer 인증 | ✅ Match |

**소결**: 완전 일치.

### 2.5 gateway.yaml.example (Design 변경 범위 테이블)

| 항목 | Design | Implementation | Status |
|------|--------|----------------|--------|
| `internal_token` 설정 예시 존재 | 명시 | `internal_token: ""` + 주석 포함 | ✅ Match |
| 토큰 생성 가이드 | 없음 | `# Generate: python -c "import secrets; ..."` 추가 | ⚠️ Added |

**소결**: Design 요구사항 충족 + 사용성 개선 주석 추가.

---

## 3. Error Handling (Design 섹션 6)

| 상황 | Design 처리 | Implementation 처리 | Status |
|------|-----------|-------------------|--------|
| X-Internal-Token 누락 | HTTP 422 (FastAPI Header 자동) | `Header()` → 자동 422 | ✅ Match |
| X-Internal-Token 불일치 | HTTP 403 `"Invalid internal token"` | `HTTPException(403, "Invalid internal token")` | ✅ Match |
| internal_token 미설정 (빈 문자열) | HTTP 403 (안전 기본값) | `not expected` → 403 | ✅ Match |
| body 필드 누락 | HTTP 422 (Pydantic 검증) | `ReloadRequest(BaseModel)` → 자동 422 | ✅ Match |
| Gateway 미실행 시 CLI 호출 | CLI 측 best-effort | CLI 측 구현 (이 피처 범위 외) | ✅ N/A |

**소결**: 에러 처리 5개 항목 모두 Design과 완전 일치.

---

## 4. Test Coverage (Design 섹션 4)

| Design 테스트 케이스 | 구현 테스트 함수 | 검증 내용 | Status |
|---------------------|----------------|----------|--------|
| `test_reload_success` | `test_reload_success` | 올바른 토큰 + body → 200 + 응답 검증 | ✅ Match |
| `test_reload_invalid_token` | `test_reload_invalid_token` | 틀린 토큰 → 403 | ✅ Match |
| `test_reload_missing_token` | `test_reload_missing_token` | 헤더 누락 → 422 | ✅ Match |
| `test_reload_empty_config_token` | `test_reload_empty_config_token` | internal_token 빈 문자열 → 403 | ✅ Match |
| `test_reload_updates_routing` | `test_reload_updates_routing` | reload 후 resolve() 새 upstream 반환 | ✅ Match |
| `test_router_reload_method` | `TestModelRouterReload.test_reload_overwrites_all_routes` | ModelRouter 단위 테스트 | ✅ Match |

**소결**: Design의 6개 테스트 케이스 모두 1:1 구현. 테스트 내용도 Design 명세와 정확히 일치.

---

## 5. Implementation Order (Design 섹션 5)

| Design 순서 | 작업 | 파일 | 구현 여부 |
|:----------:|------|------|:--------:|
| 1 | `AuthConfig`에 `internal_token` 추가 | `config.py` | ✅ |
| 2 | `ModelRouter.reload()` 메서드 추가 | `router.py` | ✅ |
| 3 | `routes/internal.py` 생성 | 신규 | ✅ |
| 4 | `main.py`에 internal 라우터 등록 | `main.py` | ✅ |
| 5 | 테스트 작성 | `tests/test_internal.py` | ✅ |
| 6 | `gateway.yaml.example` 업데이트 | example | ✅ |

**소결**: 6개 단계 모두 완료. 구현 순서는 git diff로 정확히 확인할 수 없으나, 모든 파일이 존재하고
상호 의존성이 올바르게 구성되어 있으므로 순서 준수로 판단.

---

## 6. Architecture / Convention Compliance

### 6.1 Architecture

| 항목 | 기대 | 실제 | Status |
|------|-----|------|--------|
| routes/ 경로에 엔드포인트 배치 | `routes/internal.py` | `app/routes/internal.py` | ✅ |
| config에 설정 집중 | `config.py` | `app/config.py` | ✅ |
| app state를 통한 의존성 주입 | `request.app.state.*` | 동일 | ✅ |
| `/internal`과 `/v1` 인증 분리 | Design 결정 사항 | 각각 독립 인증 | ✅ |

### 6.2 Convention

| 항목 | 기대 | 실제 | Status |
|------|-----|------|--------|
| 함수명 snake_case | `reload_routes` | `reload_routes` | ✅ |
| 클래스명 PascalCase | `ReloadRequest`, `ModelRouter` | 동일 | ✅ |
| async 엔드포인트 | 모든 route handler async | `async def reload_routes` | ✅ |
| type hints | 모든 파라미터 | 모두 적용 | ✅ |
| X-Internal-Token 헤더 사용 | `services/CLAUDE.md` 규칙 | 동일 | ✅ |

---

## 7. Match Rate Summary

### 7.1 항목별 점수

| Category | Match Items | Total Items | Score | Status |
|----------|:----------:|:-----------:|:-----:|:------:|
| ModelRouter.reload() | 4/4 | 4 | 100% | ✅ |
| POST /internal/routes/reload | 10/10 | 10 | 100% | ✅ |
| Config (internal_token) | 2/2 | 2 | 100% | ✅ |
| main.py 라우터 등록 | 3/3 | 3 | 100% | ✅ |
| Error Handling | 4/4 | 4 | 100% | ✅ |
| Test Coverage | 6/6 | 6 | 100% | ✅ |
| Implementation Order | 6/6 | 6 | 100% | ✅ |
| Architecture/Convention | 9/9 | 9 | 100% | ✅ |

### 7.2 Overall

```
+---------------------------------------------+
|  Overall Match Rate: 100%                   |
+---------------------------------------------+
|  Match:           44 items (100%)           |
|  Added (harmless):  3 items                 |
|  Missing:           0 items                 |
|  Changed:           0 items                 |
+---------------------------------------------+
```

### 7.3 Added Items (Design에 없으나 구현에 추가)

| 항목 | 위치 | 설명 | 영향 |
|------|------|------|------|
| router.py logger.info | `router.py:45` | reload() 내 로그 추가 | 무해 (디버깅 보강) |
| 모듈 docstring | `internal.py:1` | 모듈 설명 추가 | 무해 (가독성 향상) |
| 토큰 생성 가이드 주석 | `gateway.yaml.example:12` | secrets 생성 명령 주석 | 무해 (사용성 개선) |

이 3개 항목은 모두 Design 명세를 초과하는 보강이며, 기능적 변경이 아니므로 Match Rate에 영향 없음.

---

## 8. Overall Score

```
+---------------------------------------------+
|  Overall Score: 100/100                     |
+---------------------------------------------+
|  Design Match:        100%                  |
|  Error Handling:      100%                  |
|  Test Coverage:       100% (6/6 cases)      |
|  Architecture:        100%                  |
|  Convention:          100%                  |
+---------------------------------------------+
```

---

## 9. Conclusion

Design 문서와 구현 코드가 **완전히 일치**한다. 44개 비교 항목 전체가 Match이며,
추가된 3개 항목(로그, docstring, 주석)은 모두 기능에 영향이 없는 품질 보강이다.

Match Rate >= 90% 이므로 Check 단계를 통과하며, Act(iterate) 없이 Report 단계로 진행 가능하다.

---

## 10. Next Steps

- [x] Gap Analysis 완료
- [ ] Completion Report 작성 (`/pdca report gateway-internal-api`)

---

## Related Documents

- Plan: [gateway-internal-api.plan.md](../01-plan/features/gateway-internal-api.plan.md)
- Design: [gateway-internal-api.design.md](../02-design/features/gateway-internal-api.design.md)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-03-14 | Initial analysis | bkit-gap-detector |
