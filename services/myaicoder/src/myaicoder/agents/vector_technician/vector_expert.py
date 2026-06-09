import os
from typing import List

class VectorExpert:
    def __init__(self, vector_db_type: str = "chroma"):
        self.knowledge_dir = os.path.join(os.path.dirname(__file__), ".knowledge")
        self.db_type = vector_db_type

    def read_knowledge(self, filename: str) -> str:
        path = os.path.join(self.knowledge_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def upsert_vectors(self, chunks: List[str], embeddings: List[List[float]]):
        """벡터 데이터를 DB에 저장합니다."""
        pass

    def search_similar(self, query_vector: List[float], top_k: int = 5):
        """유사한 데이터를 검색합니다."""
        pass
