# 변경 로그 (Changelog)

> PDCA 완료 보고서 및 주요 배포 이력

---

## [2026-03-17] - Gateway Code Review & Bug Fix

### 추가 (Added)
- Gateway 서비스 7개 Critical 버그 수정 완료
- 동시성 제어 시스템 안정화
- 에러 로깅 인프라 강화
- 보안 로깅 개선 (URL 크리덴셜 제외)

### 변경 (Changed)
- `routes/v1.py`: ConnectError 예외 처리 로직 정리
- `proxy.py`: 변수 초기화 패턴 개선 (불안정한 체크 → None 검증)
- `proxy.py`: 핫 경로 import 최적화 (루프 외부 이동)
- `db.py`: 데이터베이스 URL 파싱 방식 보안 강화 (urlparse 적용)

### 수정됨 (Fixed)
- **C-05**: ConnectError 시 동시성 슬롯 이중 해제 (routes/v1.py:85-90)
- **C-02 (W10)**: catch_all 핸들러 동시성 슬롯 누수 (routes/v1.py)
- **C-01**: proxy.py에서 예외 무시 문제 (명시적 로깅 추가)
- **C-02**: proxy.py 불안정한 변수 존재 체크 (초기화 + None 검증)
- **Issue #5**: proxy.py 핫 루프에서 반복 import
- **C-03**: db.py fire-and-forget 태스크 에러 추적 불가 (콜백 추가)
- **C-04**: db.py DB URL 로깅 시 크리덴셜 노출 (urlparse 적용)

### 테스트 (Test Results)
- 43/43 테스트 통과 ✅ (100%)
- 설계 일치도: 98%
- Critical 버그 수정률: 100% (7/7)

### 상태
- Gateway Service: 🟢 프로덕션 배포 준비 완료
- Core Service: 🟡 다음 사이클 (9개 보안 이슈)
- VS Code Extension: 🟡 다음 사이클 (4개 보안 이슈)

---

## 우선순위 로드맵

### 긴급 (Critical) — 2026-03-20 시작
1. **Core Service 보안** (9건)
   - Command injection (C-01, C-02)
   - Path traversal (C-03, C-04, C-05)
   - SSRF (C-07)
   - 기타 (C-08, C-09)

2. **VS Code Extension XSS** (4건)
   - XSS 수정 (C-01, C-02)
   - API 키 노출 (C-03)
   - 타입 안전성 (C-04)

### 중간 (Medium) — 2026-03-25 시작
3. **Gateway 성능 최적화** (6건)
   - Prometheus 라벨 정규화 (W7)
   - upstream 읽기 타임아웃 (W13)
   - Rate limit 원자적 증가 (W12)
   - 기타 성능 개선

### 낮음 (Low) — 2026-04-01 이후
4. **코드 정리 및 최적화**
   - SKIP_DIRS 상수 통합
   - HTTP 클라이언트 재사용
   - 재연결 백오프 메커니즘

---

## 배포 예정

```
Master Branch (프로덕션):
└── v1.1.0 (2026-04-01)
    ├── Gateway 7개 버그 수정
    ├── Core 9개 보안 수정 (예정)
    └── VS Code 4개 보안 수정 (예정)
```

---

## 관련 문서

- [Gateway Code Review Report](features/gateway-code-review.report.md)
- [Code Review Analysis](../03-analysis/code-review-2026-03-17.analysis.md)
