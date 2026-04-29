## SUM() 결과의 NULL 미처리
- 문제: 조건에 맞는 데이터가 없을 때 `SUM()`이 NULL을 반환하여, 이후 계산이나 UI 표시에서 예기치 않은 동작을 유발할 수 있음.
- 해결: 항상 `COALESCE(SUM(column), 0)` 또는 `IFNULL()`을 사용하여 NULL을 0(또는 적절한 기본값)으로 치환할 것.

## INNER JOIN 시 미분류 데이터 누락
- 문제: `products` 테이블에 `category_id`가 NULL인 경우, `INNER JOIN` 시 해당 행이 결과셋에서 완전히 제외됨.
- 해결: 모든 제품을 목록에 표시해야 한다면 `LEFT JOIN products p LEFT JOIN categories c ON p.category_id = c.id` 사용.
- 추가 주의: `sales.sale_date`가 TEXT 타입이므로 `WHERE sale_date > '2023-01-01'` 비교 시 문자열 사전순 정렬을 따름. 날짜 기반 필터링 시 `WHERE date(sale_date) > '2023-01-01'` 또는 컬럼 타입을 `DATE`/`DATETIME`으로 변경 권장.

## GROUP BY 시 이름 컬럼 대신 PK 사용 권장
- 문제: 실행된 쿼리에서 `GROUP BY c.name`을 사용함. 카테고리 이름이 중복되거나 향후 이름이 변경될 경우 집계 결과가 왜곡되거나 유지보수가 어려워질 수 있음.
- 해결: 항상 `GROUP BY c.id`로 그룹화하고, SELECT 절에서 `c.name`을 함께 출력하는 것이 안전함.
- 개선 예시: `GROUP BY c.id` 사용 시 이름 변경 시에도 집계 기준이 유지되며, 인덱스 활용도도 높아짐.

## 컬럼명 불일치 및 스키마 검증 누락
- **현상**: `SELECT customer_name FROM products;` 실행 시 `no such column: customer_name` 에러 발생.
- **원인**: 비즈니스 용어(`customer_name`)와 실제 데이터베이스 컬럼명을 매핑하지 않고 추측하여 쿼리를 작성함. 현재 `products` 테이블에는 고객 관련 컬럼이 없음.
- **대응 방안**: 
  1. 쿼리 작성 전 반드시 `PRAGMA table_info(table_name);` 또는 스키마 매핑 파일을 확인하여 컬럼 존재 여부를 검증해야 함.
  2. 비즈니스 요구사항에 해당하는 컬럼이 스키마에 없을 경우, 해당 데이터가 실제로 저장되는 테이블을 먼저 파악하거나 DBA/기획자와 협의하여 스키마 확장 여부를 결정해야 함.
  3. 외래 키 관계가 명확하지 않은 경우, `JOIN` 조건이나 컬럼명을 추측하기보다 `sqlite_master` 또는 데이터베이스 다이어그램을 먼저 참조할 것.

## TEXT 타입 날짜 컬럼에 함수 적용 시 인덱스 비활성화
- 문제: `WHERE date(sale_date) > '2026-04-02'`와 같이 컬럼에 함수를 적용하면 SQLite가 해당 컬럼의 인덱스를 사용하지 못해 전체 테이블 스캔(Full Table Scan)이 발생할 수 있음.
- 해결 방안: 
  1. 데이터 설계 단계에서 날짜 컬럼을 `DATE` 또는 `INTEGER`(Unix Timestamp) 타입으로 변경 권장.
  2. 성능이 중요한 경우 `WHERE sale_date > '2026-04-02'` (함수 미적용)로 비교하되, 데이터 형식이 표준 'YYYY-MM-DD' 문자열로 저장되어 있음을 보장해야 함.
  3. 대용량 데이터 시 `date()` 함수 대신 `strftime('%Y-%m-%d', sale_date)` 또는 타입 변경을 고려.

## 다중 문장 실행 제한 (Multi-statement Execution)
- 에러: `You can only execute one statement at a time.`
- 원인: 현재 에이전트 실행 환경이 한 번에 하나의 SQL 문장만 허용함. `CREATE TABLE`, `CREATE TRIGGER`, `CREATE INDEX` 등을 하나의 블록으로 묶어 전송하면 파싱 오류 발생.
- 해결책: 각 DDL/DML 문을 분리하여 개별 실행하거나, 환경이 허용하는 경우 세미콜론(`;`)으로 명확히 구분하여 전송해야 함. 스키마 변경 작업 시 `IF NOT EXISTS` 또는 `IF NOT EXISTS` 기반 인덱스 생성을 활용하여 재실행 시 충돌을 방지할 것.

## SQLite 트리거 할당 연산자 및 호환성 주의
- 주의: SQLite는 DDL 문법상 `ON UPDATE CURRENT_TIMESTAMP`를 지원하지 않아 트리거로 `updated_at` 자동 갱신을 구현해야 함. 트리거 내 할당 연산자로 `:=` 또는 `=` 모두 사용되나, SQLite 버전 및 실행 환경에 따라 문법 오류가 발생할 수 있음.
- 대안: 안정성을 위해 애플리케이션 레벨에서 `UPDATE` 시 `updated_at = datetime('now')`를 직접 바인딩하거나, ORM의 `beforeUpdate` 훅을 활용하는 것을 권장함.