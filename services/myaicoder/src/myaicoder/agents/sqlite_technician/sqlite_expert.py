import os
from typing import Dict, Any
from ...tools.db_connector.adapter import SQLiteAdapter

class SQLiteExpert:
    def __init__(self, db_path: str):
        self.adapter = SQLiteAdapter(db_path)
        self.knowledge_dir = os.path.join(os.path.dirname(__file__), ".knowledge")

    def read_knowledge(self, filename: str) -> str:
        """지식 파일 내용을 읽어옵니다."""
        path = os.path.join(self.knowledge_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def update_knowledge(self, filename: str, content: str, mode: str = "append"):
        """지식 파일을 업데이트합니다."""
        path = os.path.join(self.knowledge_dir, filename)
        write_mode = "a" if mode == "append" else "w"
        with open(path, write_mode, encoding="utf-8") as f:
            if mode == "append" and os.path.exists(path) and os.path.getsize(path) > 0:
                f.write("\n\n")
            f.write(content)

    def get_reflection_context(self, last_query: str, last_result: Dict[str, Any]) -> str:
        """LLM이 성찰할 수 있도록 현재 지식과 최근 작업 결과를 요약합니다."""
        context = "### Current Knowledge\n"
        context += f"#### Schema:\n{self.read_knowledge('schema.md')[:1000]}...\n" # 너무 길면 생략
        context += f"#### Patterns:\n{self.read_knowledge('patterns.md')}\n"
        
        context += "\n### Last Task Execution\n"
        context += f"- **Query**: {last_query}\n"
        context += f"- **Status**: {last_result['status']}\n"
        if last_result['status'] == 'success':
            context += f"- **Row Count**: {last_result['row_count']}\n"
            # 데이터 샘플 일부 포함 (통찰을 위해)
            if last_result['data']:
                context += f"- **Sample Data**: {last_result['data'][:2]}\n"
        else:
            context += f"- **Error Message**: {last_result.get('message')}\n"
            
        return context

    def apply_reflection_update(self, llm_output: str):
        """LLM의 출력에서 'update:filename' 블록을 찾아 지식 파일을 업데이트합니다."""
        import re
        # ```update:filename ... ``` 형식을 파싱
        matches = re.findall(r"```update:(\w+\.md)\n(.*?)\n```", llm_output, re.DOTALL)
        for filename, content in matches:
            self.update_knowledge(filename, content, mode="append")
            print(f"Knowledge updated: {filename}")

    def run_task(self, query: str) -> Dict[str, Any]:
        """SQL 쿼리를 실행합니다."""
        return self.adapter.execute_query(query)

    def sync_schema(self):
        """실제 DB 스키마를 읽어 schema.md 초기 초안을 작성합니다."""
        schema_data = self.adapter.get_schema()
        if schema_data["status"] == "success":
            content = "# Database Schema Knowledge (Auto-synced)\n\n"
            for table, cols in schema_data["schema"].items():
                content += f"## {table}\n"
                content += "| Column | Type | PK | NotNull |\n"
                content += "| :--- | :--- | :--- | :--- |\n"
                for col in cols:
                    content += f"| {col['name']} | {col['type']} | {'V' if col['pk'] else ''} | {'V' if col['notnull'] else ''} |\n"
                content += "\n"
            self.update_knowledge("schema.md", content, mode="overwrite")
            return "Schema synced successfully."
        return f"Error syncing schema: {schema_data.get('message')}"
