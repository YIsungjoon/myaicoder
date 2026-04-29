# Graph Modeling & Ontology

데이터 간의 복잡한 관계를 지식 그래프로 구조화하기 위한 설계 원칙이다.

## 1. 노드 및 관계 정의 (Nodes & Relationships)
- **Nodes**: 실체(Entity)를 나타냄. (예: `User`, `Project`, `Material`, `Law`)
- **Relationships**: 실체 간의 연결을 나타냄. (예: `WORKS_ON`, `CONSISTS_OF`, `REFERENCES`)
- **Properties**: 노드와 관계에 부가 정보를 저장. (예: `since`, `version`, `weight`)

## 2. 온톨로지 설계 (Ontology)
- 상위 개념과 하위 개념의 계층 구조 정의 (`is_a` 관계).
- 복잡한 도메인 지식을 LLM이 추론하기 좋은 형태로 추상화.

## 3. 설계 패턴
- **Star Schema in Graph**: 중심 노드와 주변 속성 노드 연결.
- **Linked Data**: 외부 데이터셋(DBpedia, Wikidata)과의 연결 고려.
