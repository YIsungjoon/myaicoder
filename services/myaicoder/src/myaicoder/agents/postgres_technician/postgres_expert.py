import os
import re
from typing import Dict, Any
from ...tools.db_connector.adapter import PostgresAdapter

class PostgresExpert:
    def __init__(self, connection_string: str):
        self.adapter = PostgresAdapter(connection_string)
        self.knowledge_dir = os.path.join(os.path.dirname(__file__), ".knowledge")

    def read_knowledge(self, filename: str) -> str:
        path = os.path.join(self.knowledge_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def update_knowledge(self, filename: str, content: str, mode: str = "append"):
        path = os.path.join(self.knowledge_dir, filename)
        write_mode = "a" if mode == "append" else "w"
        with open(path, write_mode, encoding="utf-8") as f:
            if mode == "append" and os.path.exists(path) and os.path.getsize(path) > 0:
                f.write("\n\n")
            f.write(content)

    def run_task(self, query: str) -> Dict[str, Any]:
        """PostgreSQL 쿼리를 실행합니다."""
        return self.adapter.execute_query(query)

    def get_reflection_context(self, last_query: str, last_result: Dict[str, Any]) -> str:
        context = "### Current PostgreSQL Knowledge\n"
        context += f"#### Schema:\n{self.read_knowledge('schema.md')[:1000]}...\n"
        context += f"#### Patterns:\n{self.read_knowledge('patterns.md')}\n"
        context += f"\n### Last PostgreSQL Task\n- Query: {last_query}\n- Status: {last_result['status']}\n"
        return context

    def apply_reflection_update(self, llm_output: str):
        matches = re.findall(r"```update:(\w+\.md)\n(.*?)\n```", llm_output, re.DOTALL)
        for filename, content in matches:
            self.update_knowledge(filename, content, mode="append")
            print(f"Postgres Knowledge updated: {filename}")
