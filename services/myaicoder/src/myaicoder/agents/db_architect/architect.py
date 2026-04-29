import os
import requests
import json
from typing import Dict, Any, List

class DBArchitect:
    def __init__(self, llm_url: str = "http://localhost:8080/v1/chat/completions"):
        self.knowledge_dir = os.path.join(os.path.dirname(__file__), ".knowledge")
        self.llm_url = llm_url

    def read_knowledge(self, filename: str) -> str:
        path = os.path.join(self.knowledge_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

    def _call_llm(self, prompt: str, system_prompt: str) -> str:
        """로컬 LLM 서버 호출 (지능 활용)"""
        payload = {
            "model": "qwen",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0,
            "response_format": { "type": "json_object" } # JSON 출력을 유도
        }
        try:
            response = requests.post(self.llm_url, json=payload, timeout=30)
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            return f"Error: {str(e)}"

    def recommend_technician(self, requirement: str) -> Dict[str, str]:
        """LLM 지능을 사용하여 최적의 DB 엔진과 기술자를 추천합니다."""
        criteria = self.read_knowledge("selection_criteria.md")
        
        system_prompt = f"""너는 노련한 DB 아키텍트이다. 다음 지식 베이스를 바탕으로 사용자의 요구사항에 가장 적합한 DB 엔진을 선택하라.
        
        지식 베이스:
        {criteria}
        
        반드시 다음 JSON 형식으로만 답변하라:
        {{
            "engine": "SQLite 또는 PostgreSQL",
            "expert_class": "SQLiteExpert 또는 PostgresExpert",
            "reason": "선택한 이유에 대한 상세한 설명"
        }}"""
        
        llm_response = self._call_llm(f"요구사항: {requirement}", system_prompt)
        
        try:
            # JSON만 추출 (혹시 모를 마크다운 태그 제거)
            clean_json = llm_response.strip().replace("```json", "").replace("```", "")
            return json.loads(clean_json)
        except:
            # 파싱 실패 시 기본값 (안전장치)
            return {
                "engine": "Unknown",
                "expert_class": "Unknown",
                "reason": f"LLM 응답 분석 실패: {llm_response}"
            }

    def plan_schema(self, requirement: str) -> Dict[str, Any]:
        """사용자의 요구사항을 분석하여 DB 설계도를 작성합니다."""
        pass

    def document_decision(self, decision: str):
        """설계 결정 사항을 architecture.md에 기록하여 기억합니다."""
        path = os.path.join(self.knowledge_dir, "architecture.md")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n\n## Design Decision\n{decision}")
