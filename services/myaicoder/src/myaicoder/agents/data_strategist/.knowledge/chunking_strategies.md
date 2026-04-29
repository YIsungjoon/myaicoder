# Chunking & Preprocessing Strategies

데이터를 LLM이 검색하기 좋게 조각내고 정제하는 전략 가이드이다.

## 1. 청킹 전략 (Chunking Strategies)
- **Fixed-size Chunking**: 가장 단순하며 속도가 빠름. (예: 500 tokens, 10% overlap)
- **Markdown-aware Chunking**: 헤더(#, ##)를 기준으로 문맥을 보존하며 자름.
- **Recursive Character Chunking**: 문장, 문단 단위로 재귀적으로 자르며 의미적 단절 최소화.
- **Semantic Chunking**: 문장 간의 의미적 유사도를 분석하여 주제가 바뀔 때 자름 (고급).

## 2. 전처리 규칙 (Preprocessing Rules)
- **Noise Removal**: HTML 태그, 불필요한 특수문자, 중복 공백 제거.
- **Entity Normalization**: 날짜, 금액, 고유 명사 등의 형식을 통일하여 검색 정확도 향상.
- **Language Detection**: 다국어 데이터의 경우 언어별로 분리하여 처리.
