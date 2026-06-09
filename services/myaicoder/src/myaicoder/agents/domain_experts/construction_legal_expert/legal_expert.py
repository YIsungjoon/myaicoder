import os

from ....tools.law_search.law_tool import LawSearchTool

class ConstructionLegalExpert:
    def __init__(self):
        self.knowledge_dir = os.path.join(os.path.dirname(__file__), ".knowledge")
        self.law_tool = LawSearchTool()

    def read_knowledge(self, filename: str) -> str:
        path = os.path.join(self.knowledge_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def research_law(self, query: str) -> str:
        """법령을 검색하고 조문을 분석하여 보고서를 작성합니다."""
        # 1. 법령 검색
        laws = self.law_tool.search_laws(query)
        if not laws:
            return f"'{query}'에 대한 법령을 찾을 수 없습니다."
            
        # 2. 첫 번째 법령의 1조(목적)를 예시로 가져옴
        law_id = laws[0]['id']
        law_name = laws[0]['name']
        detail = self.law_tool.get_article_detail(law_id, "1")
        
        report = f"### {law_name} 분석 보고서\n\n"
        report += f"**법령명**: {law_name} (ID: {law_id})\n"
        report += f"**제1조(목적)**: {detail.get('content', '내용 없음')}\n\n"
        report += "---\n*본 보고서는 실시간 법령 검색 결과를 바탕으로 작성되었습니다.*"
        
        return report
