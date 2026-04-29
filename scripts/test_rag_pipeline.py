import os
import sys
import requests

# 프로젝트 경로 설정
sys.path.append(os.path.join(os.getcwd(), 'services/myaicoder/src'))
from myaicoder.agents.db_architect.architect import DBArchitect
from myaicoder.agents.data_strategist.strategist import DataStrategist
from myaicoder.agents.vector_technician.vector_expert import VectorExpert

def call_llm(prompt, system_prompt, persona_name):
    print(f"\n[{persona_name} Thinking...]")
    url = "http://localhost:8080/v1/chat/completions"
    payload = {
        "model": "qwen",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }
    try:
        response = requests.post(url, json=payload, timeout=90)
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Error: {str(e)}"

def run_rag_pipeline_test():
    # 1. 전문가 팀 소집
    architect = DBArchitect()
    strategist = DataStrategist()
    vector_expert = VectorExpert()
    
    test_file_path = "contech-chatbot/contech-chatbot/data/raw/contech_dx_md/01_system_overview.md"
    
    with open(test_file_path, "r", encoding="utf-8") as f:
        raw_content = f.read()
    
    print(f"📄 Target File: {test_file_path} (Size: {len(raw_content)} chars)")

    # --- Step 1: 아키텍트의 RAG 설계 ---
    print("\n--- Phase 1: RAG Architecture Design (Architect) ---")
    arch_prompt = f"사용자가 건설 기술 문서를 기반으로 한 RAG 시스템을 구축하려고 해. 데이터 소스는 마크다운 파일이야. 전체적인 데이터 흐름(전처리, 벡터 DB, 관계형 DB 활용)을 설계해줘."
    arch_plan = call_llm(arch_prompt, "You are a RAG System Architect.", "Architect")
    print(f"📐 Architect's Plan:\n{arch_plan}")

    # --- Step 2: 데이터 전략가의 청킹 전략 ---
    print("\n--- Phase 2: Data Preprocessing & Chunking (Strategist) ---")
    strat_context = strategist.read_knowledge("chunking_strategies.md")
    strat_prompt = f"다음은 원본 문서 내용의 일부야:\n\n{raw_content[:2000]}\n\n이 문서를 LLM 검색에 최적화하기 위해 어떤 청킹 전략을 쓰는 게 좋을까? {strat_context} 중에서 선택하고 구체적인 실행 계획을 말해줘."
    chunking_plan = call_llm(strat_prompt, "You are a Data Preprocessing Expert.", "Strategist")
    print(f"🧹 Strategist's Plan:\n{chunking_plan}")

    # --- Step 3: 벡터 기술자의 인덱싱 전략 ---
    print("\n--- Phase 3: Vector Indexing Strategy (Vector Expert) ---")
    vector_context = vector_expert.read_knowledge("vector_indexes.md")
    vec_prompt = f"전략가가 세운 청킹 계획은 다음과 같아:\n{chunking_plan}\n\n이 데이터를 저장할 때 어떤 벡터 인덱스와 유사도 측정 방식을 쓸지 {vector_context}를 참고해서 결정해줘."
    indexing_plan = call_llm(vec_prompt, "You are a Vector Database Specialist.", "Vector Expert")
    print(f"💾 Vector Expert's Plan:\n{indexing_plan}")

    # --- Step 4: 각자의 지식 업데이트 ---
    print("\n--- Phase 4: Learning & Documentation ---")
    # 아키텍트는 결정사항 기록
    architect.document_decision(f"RAG Pipeline for ConTech DX Docs: {indexing_plan[:100]}...")
    print("🧠 All experts updated their specialized knowledge bases.")

if __name__ == "__main__":
    run_rag_pipeline_test()
