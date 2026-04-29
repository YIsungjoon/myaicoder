# Database Schema Knowledge (Auto-synced)

## categories
| Column | Type | PK | NotNull |
| :--- | :--- | :--- | :--- |
| id | INTEGER | V |  |
| name | TEXT |  |  |

## products
| Column | Type | PK | NotNull |
| :--- | :--- | :--- | :--- |
| id | INTEGER | V |  |
| name | TEXT |  |  |
| category_id | INTEGER |  |  |
| price | INTEGER |  |  |

## sales
| Column | Type | PK | NotNull |
| :--- | :--- | :--- | :--- |
| id | INTEGER | V |  |
| product_id | INTEGER |  |  |
| qty | INTEGER |  |  |
| sale_date | TEXT |  |  |



## products & categories 관계
- `products.category_id`는 `categories.id`를 참조하는 외래 키(FK) 역할을 함.
- 비즈니스 의미: 제품 분류 및 카테고리별 매출/재고 리포트 작성 시 핵심 연결고리.
- `sales.sale_date`는 TEXT 타입으로 저장됨. 날짜 범위 조회나 정렬 시 문자열 비교 규칙을 따르므로, 정확한 날짜 연산이 필요하면 `date()` 함수 적용 또는 타입 변경을 고려해야 함.

## products & sales 테이블 (추가 통찰)
- 현재 스키마에는 `customer_name` 또는 `customer_id` 컬럼이 존재하지 않음.
- `products` 테이블은 제품 정보만 관리하며, `sales` 테이블도 거래 내역(`product_id`, `qty`, `sale_date`)만 기록함.
- 비즈니스 의미: 현재 구조는 제품 중심의 판매 기록만 추적 가능함. 고객별 구매 이력, CRM 연동, 고객 기반 분석이 필요할 경우 `customers` 테이블 신규 추가 또는 `sales` 테이블에 `customer_id` 컬럼 추가가 필요함.

## sales (추가 통찰)
- `sale_date` 컬럼은 TEXT 타입이지만, SQLite의 `date()` 함수가 'YYYY-MM-DD' 형식의 문자열을 자연스럽게 인식하여 필터링에 성공함.
- 비즈니스 의미: 날짜 기반 조회 시 문자열 정렬/비교 규칙(YYYY-MM-DD)을 준수해야 정확한 범위 조회가 가능함. 현재 구조는 제품 중심의 판매 기록만 추적하며, 고객 정보(`customer_id` 등)가 없어 고객별 리포트 작성 시 추가 테이블 설계가 필요함.

## reviews
- `id` INTEGER PK, `user_id`, `product_id` 외래키 참조.
- `rating` INTEGER CHECK(1~5)로 평점 범위 제약 적용.
- `is_public` INTEGER DEFAULT 1: 리뷰 공개/비공개 플래그.
- `deleted_at` DATETIME NULL: 소프트 삭제(Soft Delete) 패턴 적용. 논리적 삭제로 데이터 보존 및 참조 무결성 유지 목적.
- `created_at`, `updated_at` DATETIME: 생성/수정 시점 자동 기록.

## review_images
- `review_id` FK ON DELETE CASCADE: 리뷰 삭제 시 이미지 자동 정리.
- `sort_order` INTEGER DEFAULT 0: 다중 이미지 정렬용 순서 컬럼.

## review_likes
- 리뷰와 사용자 간 다대다 관계 해결을 위한 연결 테이블(Junction Table).
- `UNIQUE(review_id, user_id)` 제약으로 동일 사용자의 중복 좋아요 방지.
- `review_id`, `user_id` 모두 FK ON DELETE CASCADE 적용.

## 스키마 의존성 통찰
- `reviews.user_id`가 `users(id)`를 참조하지만, 현재 스키마에 `users` 테이블 정의가 없음. 실제 실행 시 `users` 테이블이 먼저 생성되어야 FK 제약이 유효함.
- `products` 테이블과 `reviews` 테이블 간 1:N 관계가 추가됨에 따라, 제품별 평점 집계(`AVG(rating)`) 또는 리뷰 수 카운트 쿼리가 빈번해질 것으로 예상됨.