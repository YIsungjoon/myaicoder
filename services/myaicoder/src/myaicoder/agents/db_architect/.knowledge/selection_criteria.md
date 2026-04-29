# Database Selection Criteria

프로젝트의 요구사항에 따라 최적의 DB 엔진과 기술자를 선택하는 가이드라인이다.

## 1. SQLite 선택 기준 (Small/Local)
- **사용 사례**: 로컬 설정 저장, 단일 사용자 앱, 프로토타이핑, 모바일 앱 내장 DB.
- **장점**: 설정이 필요 없음, 파일 하나로 관리됨, 매우 빠름.
- **제한**: 동시 쓰기가 많은 환경에 부적합, 복잡한 사용자 권한 관리 불가능.

## 2. PostgreSQL 선택 기준 (Enterprise/Scalable)
- **사용 사례**: 웹 서비스 백엔드, 대규모 데이터 분석, 동시 접속자가 많은 앱.
- **장점**: 동시성 제어(MVCC) 우수, JSONB 등 다양한 데이터 타입 지원, 확장성 뛰어남.
- **제한**: 별도의 서버 설치 및 관리가 필요함, 설정이 상대적으로 복잡함.

## 3. 기술자 매칭 가이드
- 환경이 'Local/Standalone'이면 -> **SQLiteExpert** 호출.
- 환경이 'Server/Multi-user'이면 -> **PostgresExpert** 호출.
