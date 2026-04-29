# Cypher Recipes & Graph Tech

그래프 데이터를 구현하고 최적화하기 위한 기술 지침이다.

## 1. Cypher 쿼리 최적화
- `MATCH` 절의 효율적 사용 (Label 지정 및 인덱스 활용).
- `MERGE`를 활용한 데이터 중복 방지 및 원자적 생성.
- 가변 길이 경로 검색(`-[*1..3]->`) 시 성능 주의사항.

## 2. 그래프 알고리즘 (Graph Algorithms)
- **PageRank**: 영향력 있는 노드 탐색.
- **Community Detection (Louvain)**: 유사한 노드들의 그룹(커뮤니티) 발견.
- **Shortest Path**: 두 노드 간의 가장 빠른 연결 고리 탐색.

## 3. 인덱스 및 제약조건
- 고유 제약조건(`IS UNIQUE`) 및 검색 인덱싱 전략.
