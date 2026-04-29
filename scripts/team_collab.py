import os
import sys
import requests

# 프로젝트 경로 설정
sys.path.append(os.path.join(os.getcwd(), 'services/myaicoder/src'))
from myaicoder.agents.db_architect.architect import DBArchitect
from myaicoder.agents.db_technician.technician import SQLManager

def call_llm(prompt, system_prompt, persona_name):
    """특정 페르소나로 LLM 호출"""
    print(f"\n[{persona_name} Thinking...]")
    url = "http://localhost:8080/v1/chat/completions"
    payload = {
        "model": "qwen",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }
    try:
        response = requests.post(url, json=payload, timeout=60)
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Error: {str(e)}"

def run_team_collaboration():
    # 1. 팀 소집
    architect = DBArchitect()
    technician = SQLManager("collab_test.db")
    
    # 2. 사용자 요청
    user_request = "쇼핑몰 앱을 만드는데, '상품 리뷰' 기능을 추가하고 싶어. 테이블 구조를 잡고 생성해줘."
    print(f"👤 User Request: {user_request}")

    # --- Step 1: 아키텍트의 설계 ---
    print("\n--- Phase 1: Strategic Planning (Architect) ---")
    arch_context = f"Current Architecture:\n{architect.read_knowledge('architecture.md')}\nPrinciples:\n{architect.read_knowledge('modeling_principles.md')}"
    arch_prompt = f"{arch_context}\n\nUser Request: {user_request}\n이 기능을 위한 테이블 구조(BluePrint)를 설계해줘. 컬럼명과 타입을 명확히 정의하고, 기술자에게 줄 전달사항을 마크다운으로 작성해줘."
    
    arch_blueprint = call_llm(arch_prompt, "You are a Senior DB Architect.", "Architect")
    print(f"📐 Architect's BluePrint:\n{arch_blueprint}")

    # --- Step 2: 기술자의 구현 ---
    print("\n--- Phase 2: Technical Implementation (Technician) ---")
    tech_prompt = f"아키텍트의 설계도:\n{arch_blueprint}\n\n위 설계도를 바탕으로 SQLite용 CREATE TABLE SQL을 작성하고 실행해줘."
    
    # 기술자는 자신의 SQL 지식을 참고하여 쿼리 생성
    sql_code = call_llm(tech_prompt, "You are a SQL Expert Technician.", "Technician")
    # SQL만 추출 (간단한 파싱)
    sql = sql_code.split("```sql")[1].split("```")[0].strip() if "```sql" in sql_code else sql_code
    print(f"🛠️ Technician's SQL:\n{sql}")
    
    execution_result = technician.run_task(sql)
    print(f"✅ Execution Result: {execution_result['status']}")

    # --- Step 3: 각자의 학습 (성찰) ---
    print("\n--- Phase 3: Post-Task Reflection & Learning ---")
    
    # 기술자의 학습
    with open('services/myaicoder/src/myaicoder/agents/db_technician/prompts/reflection.md', 'r') as f:
        tech_ref_prompt = f.read()
    tech_learning = call_llm(technician.get_reflection_context(sql, execution_result), tech_ref_prompt, "Technician")
    technician.apply_reflection_update(tech_learning)
    
    # 아키텍트의 학습 및 기록
    architect.document_decision(f"리뷰 기능 추가: {user_request}\n결과: {execution_result['status']}")
    print("🧠 Architect documented the decision.")

    if os.path.exists("collab_test.db"):
        os.remove("collab_test.db")

if __name__ == "__main__":
    run_team_collaboration()
