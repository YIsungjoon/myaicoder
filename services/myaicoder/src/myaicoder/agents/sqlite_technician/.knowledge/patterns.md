## NULL 허용 집계 결과 처리
- SQL: SELECT COALESCE(SUM(amount), 0) AS total_amount FROM orders WHERE status = '완료';
- 이유: `SUM()` 함수는 매칭되는 행이 없거나 모든 값이 NULL일 경우 NULL을 반환함. `COALESCE`를 사용하여 0으로 기본값을 설정하면 비즈니스 로직에서 더 안전하게 처리 가능함.

## 참조 테이블 조인 (INNER JOIN)
- SQL: SELECT p.name AS product_name, c.name AS category_name FROM products p JOIN categories c ON p.category_id = c.id;
- 이유: 매핑 테이블(참조 테이블)과 본 테이블을 연결하여 가독성 높은 결과셋 생성. Alias(p, c)를 사용하여 가독성 및 유지보수성 향상.
- 활용: 카테고리별 제품 목록 조회, 카테고리별 집계 쿼리 작성 시 기본 구조로 재사용 가능.

## 카테고리별 총 매출 집계 (3개 테이블 조인 + GROUP BY)
- SQL: SELECT c.name AS category_name, SUM(p.price * s.qty) AS total_revenue FROM categories c JOIN products p ON c.id = p.category_id JOIN sales s ON p.id = s.product_id GROUP BY c.name ORDER BY total_revenue DESC;
- 이유: 참조 테이블(`categories`)과 거래 테이블(`sales`)을 외래 키 체인으로 순차적으로 조인한 후, 단위 가격과 수량의 곱을 집계하여 비즈니스 핵심 지표(매출)를 도출함.
- 활용: 카테고리별/기간별/판매자별 집계 리포트 작성 시 기본 템플릿으로 재사용 가능. `ORDER BY` 내림차순 정렬을 통해 상위 매출 항목을 빠르게 파악할 수 있음.

## 조인 시 중복 행 제거 (DISTINCT 활용)
- SQL: SELECT DISTINCT p.name FROM products p JOIN sales s ON p.id = s.product_id WHERE date(s.sale_date) > '2026-04-02';
- 이유: `products`와 `sales`는 1:N 관계이므로 조인 시 동일 제품이 여러 행으로 중복 출력됨. `DISTINCT`를 적용하여 비즈니스 요구사항(해당 기간에 판매된 제품 목록)에 맞게 고유값만 추출함.
- 활용: 다대일 관계 조인 시 중복 제거가 필요한 목록 조회 쿼리에 적용 가능.

## TEXT 타입 날짜 컬럼 필터링
- SQL: WHERE date(s.sale_date) > '2026-04-02'
- 이유: SQLite는 TEXT 타입의 날짜 문자열에 `date()` 함수를 적용하면 표준 날짜 형식으로 변환하여 비교 가능. 형식이 표준화되어 있을 경우 정확한 기간 필터링이 가능함.

## 복합 인덱스 설계 (조회 패턴 최적화)
- SQL: CREATE INDEX idx_reviews_product_created ON reviews(product_id, created_at DESC);
- 이유: 특정 제품의 리뷰 목록을 최신순으로 조회하는 쿼리(`WHERE product_id = ? ORDER BY created_at DESC`)에 최적화됨. 컬럼 순서와 정렬 방향을 실제 쿼리 패턴과 일치시켜야 인덱스 시퀀싱(Index Scan)이 효율적으로 동작함.

## 소프트 삭제 패턴 (Soft Delete)
- SQL: SELECT * FROM reviews WHERE product_id = ? AND deleted_at IS NULL;
- 이유: `deleted_at` 컬럼을 활용하여 물리적 삭제 대신 논리적 삭제를 구현. 연관 데이터(좋아요, 이미지)와의 참조 무결성을 유지하면서도 데이터 복구가 가능함. 조회 시 반드시 `IS NULL` 조건을 명시해야 함.

## ON DELETE CASCADE 활용
- SQL: FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE
- 이유: `review_images`, `review_likes` 등 자식 테이블의 수동 정리 로직을 제거하고 DB 레벨에서 일괄 삭제 처리. 트랜잭션 내 일관성을 보장하며 애플리케이션 코드 복잡도를 낮춤.