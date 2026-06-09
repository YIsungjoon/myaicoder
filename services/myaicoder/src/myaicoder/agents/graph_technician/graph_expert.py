import os
from typing import Dict, Any

class GraphExpert:
    def __init__(self, graph_db_type: str = "neo4j"):
        self.knowledge_dir = os.path.join(os.path.dirname(__file__), ".knowledge")
        self.db_type = graph_db_type

    def read_knowledge(self, filename: str) -> str:
        path = os.path.join(self.knowledge_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def run_cypher(self, query: str) -> Dict[str, Any]:
        """Cypher 쿼리를 실행합니다."""
        pass
