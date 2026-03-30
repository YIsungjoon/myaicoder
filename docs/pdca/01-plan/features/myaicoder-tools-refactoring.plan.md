# Plan: myAiCoder Core Tools 구조 개선 (Refactoring)

> **상태**: P (Plan)
> **작성일**: 2026-03-24
> **목표**: `tools/` 루트의 12개 파일을 기능별 서브패키지로 그룹화하여 가독성을 높이고 유지보수성을 확보한다.

---

## 1. 배경 및 필요성
- **구조적 부채**: 파일 시스템 관련 도구(read, write), 검색 관련 도구(grep, glob), 외부 실행 도구(bash, web) 등이 하나의 디렉토리에 섞여 있음.
- **인지 부채**: 특정 기능의 도구를 찾기 위해 전체 목록을 확인해야 함.
- **확장성**: `deepagents`의 `write_todos`와 같은 지능형 도구를 추가할 때 논리적 위치가 불분명함.

---

## 2. 핵심 설계 원칙
1. **관심사 분리 (SoC)**: 도구의 성격(파일, 검색, 외부)에 따라 디렉토리를 분리한다.
2. **Registry 패턴 유지**: 도구의 물리적 위치가 바뀌어도 `registry.py`를 통한 일관된 인터페이스를 제공한다.
3. **의존성 최소화**: 각 도구 패키지 간의 상호 의존성을 배제하여 독립적인 테스트가 가능하게 한다.
4. **DRY (Don't Repeat Yourself)**: `base.py`의 공통 로직을 강화하여 각 도구의 구현을 단순화한다.

---

## 3. 목표 구조 (Target Architecture)

```
myaicoder/tools/
├── __init__.py
├── base.py              ← 도구 기본 클래스 (유지)
├── registry.py          ← 도구 통합 등록 및 조회 (핵심)
├── filesystem/          ← 파일 시스템 관련
│   ├── __init__.py
│   ├── read.py
│   ├── write.py
│   ├── edit.py
│   └── list_dir.py
├── search/              ← 검색 및 분석 관련
│   ├── __init__.py
│   ├── bash.py
│   ├── glob_tool.py
│   └── grep_tool.py
└── external/            ← 외부 시스템 연동
    ├── __init__.py
    ├── build_runner.py
    └── web_fetch.py
```

---

## 4. 실행 단계 (Implementation Steps)

### Phase 1: 패키지 기반 구축 (P -> D)
1. `filesystem/`, `search/`, `external/` 디렉토리 생성 및 `__init__.py` 초기화.
2. `base.py`를 검토하여 서브패키지 도구들이 공유할 공통 유틸리티가 있는지 확인.

### Phase 2: 파일 이동 및 Registry 수정
1. 12개 도구 파일을 대상 패키지로 이동.
2. `registry.py`의 `import` 경로를 전면 수정하여 기존 기능이 중단되지 않도록 함.

### Phase 3: 테스트 및 검증 (Check)
1. `uv run pytest services/myaicoder/tests/test_tools/` 실행 (100% 패스 목표).
2. MCP 서버 연동 시 도구 이름 및 스키마가 변함없는지 확인.

---

## 5. 위험 요소 및 대응
- **Import Error**: 대량의 파일 이동으로 인한 경로 오류. `grep`을 통해 모든 참조를 사전 확인.
- **MCP Schema 변동**: 도구 클래스명이 바뀌어 MCP 스키마가 깨질 위험. 클래스명은 기존과 동일하게 유지.

---

## 6. 성공 지표
- `tools/` 루트 파일 수: 12개 -> 3개 (`base.py`, `registry.py`, `__init__.py`)
- 모든 도구 테스트 및 통합 테스트 통과
