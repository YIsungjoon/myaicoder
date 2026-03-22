# myaicoder 구조 분석 및 개선 계획

> 분석일: 2026-03-22
> 목적: 바이브 코딩으로 인한 구조적 인지부채 해소

---

## 현재 상태 요약

| 서비스 | 심각도 | 문제 |
|--------|--------|------|
| **Gateway app** | 🔴 심각 | 루트에 13개 파일 밀집, 결합도 매우 높음 |
| **MyaiCoder tools** | 🟡 주의 | 12개 도구 파일이 논리적 그룹 없이 나열 |
| **MyaiCoder core** | 🟢 양호 | engine.py 결합도 높지만 정상 범위 |
| **MyaiCoder mcp** | 🟢 양호 | 빈 transport/ 디렉토리만 정리 필요 |
| **VS Code Extension** | ✅ 우수 | 기능별로 잘 분류됨 |

---

## 문제 1: Gateway — 13개 파일이 루트에 밀집 (심각)

### 현재 구조

```
gateway/app/
├── auth.py              ← 인증
├── concurrency.py       ← 동시성 제어
├── config.py            ← 설정
├── db.py                ← DB (210줄)
├── deps.py              ← 의존성 주입 (5개 import, HIGH COUPLING)
├── logging.py           ← 로깅
├── main.py              ← 진입점 (10개 import, HIGHEST COUPLING)
├── metrics.py           ← Prometheus 메트릭
├── models.py            ← 데이터 모델
├── proxy.py             ← HTTP 프록시 (288줄, 가장 큼)
├── rate_limiter.py      ← 레이트 제한
├── router.py            ← 모델 라우팅
└── routes/
    ├── health.py
    ├── internal.py
    ├── metrics.py
    └── v1.py
```

**문제점:**
- 인증, 설정, DB, 프록시, 미들웨어가 **같은 수준에 혼재**
- `main.py`가 10개 모듈을 import → 모든 것에 의존
- `deps.py`가 5개 모듈을 import → 의존성 허브
- "인증 관련 파일이 어디있지?" → 13개를 다 봐야 함

### 개선 구조

```
gateway/app/
├── main.py                    ← 진입점 (create_app만)
├── config/                    ← 설정 관련
│   ├── __init__.py
│   ├── settings.py            ← GatewayConfig
│   └── models.py              ← 데이터 모델
├── auth/                      ← 인증 관련
│   ├── __init__.py
│   └── store.py               ← AuthStore
├── middleware/                 ← 미들웨어 관련
│   ├── __init__.py
│   ├── concurrency.py         ← ConcurrencyLimiter
│   ├── rate_limiter.py        ← SlidingWindowLimiter
│   └── deps.py                ← FastAPI 의존성
├── proxy/                     ← 프록시 관련
│   ├── __init__.py
│   ├── forward.py             ← 프록시 로직
│   └── router.py              ← 모델 라우팅
├── infra/                     ← 인프라 관련
│   ├── __init__.py
│   ├── db.py                  ← DB 연결/스키마
│   ├── logging.py             ← 구조화 로깅
│   └── metrics.py             ← Prometheus 메트릭
└── routes/                    ← API 엔드포인트 (유지)
    ├── health.py
    ├── internal.py
    ├── metrics.py
    └── v1.py
```

**개선 효과:**
- "인증 관련?" → `auth/` 디렉토리만 보면 됨
- "미들웨어?" → `middleware/` 디렉토리만 보면 됨
- `main.py`의 import가 패키지 단위로 정리됨

---

## 문제 2: MyaiCoder tools — 논리적 그룹화 부재 (주의)

### 현재 구조

```
tools/
├── base.py              ← 기본 클래스
├── registry.py          ← 도구 레지스트리
├── bash.py              ← 셸 명령 실행
├── build_runner.py      ← 빌드 실행
├── edit.py              ← 파일 편집
├── glob_tool.py         ← 파일 패턴 검색
├── grep_tool.py         ← 내용 검색 (246줄, 가장 큼)
├── list_dir.py          ← 디렉토리 목록
├── read.py              ← 파일 읽기
├── web_fetch.py         ← 웹 페이지 가져오기
└── write.py             ← 파일 쓰기
```

**문제점:**
- "파일 관련 도구는?" → 12개를 다 열어봐야 함
- edit, read, write, list_dir이 논리적으로 같은 그룹인데 분산
- 도구가 늘어나면 더 심해짐

### 개선 구조

```
tools/
├── base.py              ← 유지 (기본 클래스)
├── registry.py          ← 유지 (도구 레지스트리)
├── filesystem/          ← 파일 시스템 도구
│   ├── __init__.py
│   ├── read.py
│   ├── write.py
│   ├── edit.py
│   └── list_dir.py
├── search/              ← 검색 도구
│   ├── __init__.py
│   ├── bash.py
│   ├── glob_tool.py
│   └── grep_tool.py
└── external/            ← 외부 통신 도구
    ├── __init__.py
    ├── build_runner.py
    └── web_fetch.py
```

**개선 효과:**
- "파일 관련 도구?" → `filesystem/` 하나만 보면 됨
- 새 도구 추가 시 어디에 넣을지 명확
- 도구 유형별 공통 로직 추출 가능

---

## 문제 3: 기타 정리 필요 사항

### 빈 디렉토리 정리

```
mcp/transport/         ← __init__.py만 있고 비어있음
                        → 사용 예정이면 TODO 주석, 아니면 제거
```

### utils 디렉토리

```
utils/                 ← 파일 1개만 존재
                        → 내용 확인 후 적절한 위치로 이동 검토
```

---

## 리팩토링 우선순위

### Phase 1: Gateway 구조 개선 (가장 시급)
1. 기능별 서브패키지 생성 (auth, middleware, proxy, infra, config)
2. 파일 이동 및 import 경로 수정
3. 테스트 실행으로 동작 확인

### Phase 2: Tools 구조 개선
1. 기능별 서브패키지 생성 (filesystem, search, external)
2. 파일 이동 및 registry.py import 경로 수정
3. 테스트 실행으로 동작 확인

### Phase 3: 정리
1. 빈 디렉토리 정리
2. utils 정리
3. 전체 import 정리

---

## 리팩토링 시 주의사항

1. **한 번에 하나의 패키지만** 이동 → 테스트 → 다음 이동
2. **import 경로** 수정 시 grep으로 모든 참조 확인
3. **테스트가 깨지면** 즉시 멈추고 원인 파악
4. **git commit을 자주** — 각 이동 단계마다 커밋
5. **기능 변경 없이** 구조만 변경 (리팩토링 원칙)
