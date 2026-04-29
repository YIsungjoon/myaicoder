import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import re
from typing import List, Dict, Any, Optional

class KcscSearchTool:
    """법제처 API를 통해 KDS/KCS 건설기준을 검색하고 상세 내용을 조회하는 도구."""
    
    SEARCH_URL = "http://www.law.go.kr/DRF/lawSearch.do"
    ARTICLE_URL = "http://www.law.go.kr/DRF/lawService.do"

    def __init__(self, oc: Optional[str] = None):
        import os
        self.oc = oc or os.getenv("LAW_API_OC", "test")
        self.timeout = 30

    def _request_xml(self, url: str, params: dict) -> ET.Element:
        query_params = {**params, "OC": self.oc, "type": "XML"}
        query_string = urllib.parse.urlencode(query_params)
        full_url = f"{url}?{query_string}"
        
        try:
            with urllib.request.urlopen(full_url, timeout=self.timeout) as response:
                content = response.read().decode('utf-8')
                return ET.fromstring(content)
        except Exception as e:
            return ET.Element("error", {"message": str(e)})

    def search_standards(self, query: str) -> List[Dict[str, str]]:
        """기술기준(KDS/KCS) 목록을 검색합니다."""
        params = {"target": "admrul", "query": query, "display": 20}
        root = self._request_xml(self.SEARCH_URL, params)
        
        results = []
        for item in root.findall(".//admrul"):
            def get_text(tag: str) -> str:
                node = item.find(tag)
                return (node.text or "").strip() if node is not None else ""

            title = get_text("행정규칙명")
            # 기술기준 관련 키워드 필터링
            if any(kw in title for kw in ["기준", "시방서", "지침"]):
                results.append({
                    "id": get_text("행정규칙일련번호"),
                    "name": title,
                    "type": "기술기준",
                    "issued_by": get_text("소관부처명"),
                    "effective_date": get_text("시행일자")
                })
        return results

    def get_standard_detail(self, standard_id: str) -> Dict[str, Any]:
        """특정 기술기준의 상세 본문을 조회합니다."""
        params = {"target": "admrul", "ID": standard_id}
        root = self._request_xml(self.ARTICLE_URL, params)
        
        basic = root.find(".//행정규칙기본정보") or root.find(".//기본정보")
        
        def get_node_text(node, tag: str, default: str = "") -> str:
            if node is None: return default
            found = node.find(tag)
            return (found.text or default).strip() if found is not None else default

        content_node = root.find(".//조문내용") or root.find(".//본문")
        content = (content_node.text or "").strip() if content_node is not None else "내용 없음"
        
        return {
            "status": "success" if content != "내용 없음" else "error",
            "title": get_node_text(basic, "행정규칙명", "제목 없음"),
            "issued_by": get_node_text(basic, "소관부처명", "소관부처 없음"),
            "content": content[:5000],
            "full_url": f"https://www.law.go.kr/행정규칙/{standard_id}"
        }

    def search_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """KDS 41 10 10 같은 코드로 직접 검색하여 첫 번째 결과를 반환합니다."""
        clean_code = code.replace(" ", "")
        search_results = self.search_standards(clean_code)
        
        if not search_results:
            search_results = self.search_standards(code)
            
        if search_results:
            detail = self.get_standard_detail(search_results[0]['id'])
            if detail.get("status") == "success":
                return detail
        return None
