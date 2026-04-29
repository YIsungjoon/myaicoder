import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional, Literal

class LawSearchTool:
    """국가법령정보센터 API를 사용하여 법령을 검색하고 조문을 조회하는 도구."""
    
    SEARCH_URL = "http://www.law.go.kr/DRF/lawSearch.do"
    ARTICLE_URL = "http://www.law.go.kr/DRF/lawService.do"

    def __init__(self, oc: Optional[str] = None):
        import os
        # 환경 변수에서 OC 코드를 읽어오되, 없으면 기본값 'test' 사용
        self.oc = oc or os.getenv("LAW_API_OC", "test")
        try:
            self.timeout = int(os.getenv("LAW_API_TIMEOUT", "30"))
        except:
            self.timeout = 30

    def _request_xml(self, url: str, params: dict) -> ET.Element:
        """API 호출 후 XML Element 반환."""
        query_params = {**params, "OC": self.oc, "type": "XML"}
        query_string = urllib.parse.urlencode(query_params)
        full_url = f"{url}?{query_string}"
        
        try:
            with urllib.request.urlopen(full_url, timeout=self.timeout) as response:
                content = response.read().decode('utf-8')
                return ET.fromstring(content)
        except Exception as e:
            # 에러 발생 시 빈 루트 엘리먼트라도 반환하여 이후 로직이 깨지지 않게 함
            return ET.Element("error", {"message": str(e)})

    def search_laws(self, query: str, target: Literal["eflaw", "admrul", "ordin"] = "eflaw") -> List[Dict[str, str]]:
        """법령 목록을 검색합니다."""
        params = {"target": target, "query": query}
        root = self._request_xml(self.SEARCH_URL, params)
        
        results = []
        # 대상에 따른 태그 이름 설정
        tag_name = "law" if target in ["eflaw", "ordin"] else "admrul"
        
        for item in root.findall(f".//{tag_name}"):
            # 각 필드를 안전하게 가져오기 위한 헬퍼
            def get_text(tag: str) -> str:
                node = item.find(tag)
                return (node.text or "").strip() if node is not None else ""

            if target == "eflaw":
                results.append({
                    "id": get_text("법령ID"),
                    "name": get_text("법령명한글"),
                    "type": "법령",
                    "link": f"https://www.law.go.kr{get_text('법령상세링크')}"
                })
            elif target == "admrul":
                results.append({
                    "id": get_text("행정규칙일련번호"),
                    "name": get_text("행정규칙명"),
                    "type": "행정규칙",
                    "link": f"https://www.law.go.kr{get_text('행정규칙상세링크')}"
                })
        return results

    def get_article_detail(self, law_id: str, article_no: str) -> Dict[str, Any]:
        """특정 법령의 조문 상세 내용을 조회합니다."""
        # target=lawjosub 은 현행법령 전용
        params = {"target": "lawjosub", "ID": law_id, "JO": article_no}
        root = self._request_xml(self.ARTICLE_URL, params)
        
        jo_item = root.find(".//조문단위")
        if jo_item is None:
            return {"status": "error", "message": f"제{article_no}조를 찾을 수 없습니다."}
            
        def get_node_text(path: str, default: str = "") -> str:
            node = root.find(path) if path.startswith(".") else jo_item.find(path)
            return (node.text or default).strip() if node is not None else default

        return {
            "status": "success",
            "law_name": get_node_text(".//법령명한글"),
            "article_no": get_node_text("조문번호"),
            "article_title": get_node_text("조문제목", "제목 없음"),
            "content": get_node_text("조문내용", "내용 없음"),
            "paragraphs": [p.text.strip() for p in jo_item.findall(".//항내용") if p.text]
        }
