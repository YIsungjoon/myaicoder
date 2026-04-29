# Design Document: SQL Specialist Agent (Self-Learning)

**상태**: 설계 중 (Draft)
**기능명**: `sql-specialist-agent`
**핵심 패턴**: Modular LLM Wiki (Decentralized Learning)

## 1. 아키텍처 개요

SQL 전문 에이전트는 단순히 쿼리를 실행하는 도구가 아니라, 데이터베이스 스키마와 최적의 쿼리 패턴을 스스로 학습하고 관리하는 독립적인 지능형 모듈로 설계합니다.

### 1.1 분산형 학습 구조 (Decentralized Learning)
각 도구는 자신의 실행 경로 내에 `.knowledge/` 디렉토리를 보유하며, 이 공간을 통해 개별적으로 성장합니다.

```text
services/myaicoder/src/myaicoder/tools/database/
├── __init__.py
├── adapter.py          # DB 엔진별 어댑터 (SQLite, Postgres 등)
├── manager.py          # SQL 에이전트 오케스트레이터
├── .knowledge/         # 도구 전용 지식 저장소 (LLM Wiki)
│   ├── schema.md       # 스스로 파악한 DB 구조 및 주석
│   ├── patterns.md     # 성공한 SQL 쿼리 레시피
│   └── anti_patterns.md # 실패했던 사례 및 주의사항
└── prompts/            # SQL 특화 시스템 프롬프트
```

## 2. 핵심 메커니즘: Self-Learning Loop

### 2.1 Ingest (지식 흡수)
작업 성공 시, 에이전트는 결과물에서 '학습 가치가 있는 정보'를 추출합니다.
- 예: "이 쿼리는 `orders`와 `users` 테이블을 조인할 때 `user_id`를 인덱스로 사용함" -> `patterns.md` 업데이트.

### 2.2 Query (지식 활용)
새로운 SQL 요청이 오면, 에이전트는 먼저 자신의 `.knowledge/`를 읽어 컨텍스트를 보강합니다.
- `schema.md`를 통해 컬럼의 비즈니스적 의미를 파악.
- `patterns.md`를 참고하여 유사한 쿼리 초안 작성.

### 2.3 Lint (지식 정제)
주기적으로 실제 DB 상태와 `schema.md`를 비교하여 동기화합니다. (Validation Tool 사용)

## 3. 데이터 모델 (Knowledge Schema)

### 3.1 `schema.md`
단순 DDL이 아닌, LLM이 이해하기 쉽게 가공된 문서.
- `## [Table Name]`
- `Description`: LLM이 성찰을 통해 작성한 테이블 용도.
- `Columns`: 타입, 제약조건, 그리고 **실제 데이터 샘플 기반의 특징**.

### 3.2 `patterns.md`
- `## [Task Description]`
- `SQL`: 최적화된 SQL 코드.
- `Reasoning`: 왜 이 방식이 효율적인지에 대한 설명.

## 4. 구현 단계 (Do Phase)

1. **Phase 1**: DB 연결 어댑터 및 기본 쿼리 도구 구현.
2. **Phase 2**: `.knowledge/` 읽기/쓰기 기능을 담당하는 `KnowledgeManager` 개발.
3. **Phase 3**: 작업 완료 후 스스로 지식을 기록하는 '성찰(Reflection)' 프롬프트 통합.
4. **Phase 4**: 학습된 지식을 다음 작업의 컨텍스트로 주입하는 로직 완성.

## 5. 보안 및 안전장치
- **Read-Only Mode**: 기본적으로 SELECT 쿼리만 허용 (설정에 따라 변경).
- **Execution Approval**: 파괴적인 명령(DROP, DELETE 등)은 반드시 사용자 승인 필요.
- **Data Masking**: 개인정보(PII) 패턴 감지 시 지식 저장소 기록 제외.

---
**Executive Summary: SQL Specialist Agent Design**

| 구분 | 내용 |
| :--- | :--- |
| **핵심 설계** | 도구별 독립 지식 저장소(`.knowledge/`)를 활용한 분산형 학습 아키텍처 |
| **기능 효과** | 사용할수록 프로젝트 특화 DB 지식이 쌓여 쿼리 정확도와 속도 향상 |
| **학습 방식** | Karpathy의 LLM Wiki 모델을 도구 단위로 축소 및 적용 |
| **차별점** | 중앙 집중식이 아닌 모듈형 성장으로 시스템 복잡도 관리 및 성능 최적화 |
