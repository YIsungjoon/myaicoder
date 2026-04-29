# Vector Indexing & Metrics

고차원 벡터 데이터를 효율적으로 저장하고 검색하기 위한 기술 지침이다.

## 1. 유사도 측정 (Similarity Metrics)
- **Cosine Similarity**: 방향 위주의 유사도 (텍스트 검색에 가장 일반적).
- **Euclidean Distance (L2)**: 벡터 간의 절대적 거리 (이미지, 오디오 검색에 유리).
- **Dot Product**: 벡터의 크기와 방향을 모두 고려.

## 2. 인덱싱 알고리즘 (Indexing)
- **HNSW (Hierarchical Navigable Small World)**: 가장 빠르고 정확한 그래프 기반 인덱싱.
- **IVF (Inverted File Index)**: 데이터를 클러스터링하여 검색 범위 축소.
- **Flat**: 전수 조사 (데이터가 적을 때만 사용).
