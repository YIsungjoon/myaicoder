import os
import sys
import sqlite3
import requests
import json

# 프로젝트 경로 설정
sys.path.append(os.path.join(os.getcwd(), 'services/myaicoder/src'))
from myaicoder.tools.database.manager import SQLManager

def call_llm(prompt, system_prompt="You are a helpful assistant."):
    """로컬 LLM 서버(localhost:8080) 호출"""
    url = "http://localhost:8080/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": "qwen",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Error: {str(e)}"

def run_integration_test():
    db_path = "learning_test.db"
    
    # 1. 테스트 DB 세팅
    print("--- Step 1: Setting up Sample DB ---")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE orders (id INTEGER PRIMARY KEY, item TEXT, status TEXT, amount INTEGER);')
    cursor.execute("INSERT INTO orders (item, status, amount) VALUES ('Macbook', 'COMPLETED', 3000);")
    cursor.execute("INSERT INTO orders (item, status, amount) VALUES ('iPhone', 'PENDING', 1200);")
    conn.commit()
    conn.close()

    manager = SQLManager(db_path)
    manager.sync_schema() # 기초 스키마 동기화

    # 2. LLM에게 작업 요청
    print("\n--- Step 2: Asking LLM to analyze and query ---")
    schema_info = manager.read_knowledge("schema.md")
    task_prompt = f"현재 DB 스키마는 다음과 같아:\n{schema_info}\n\n'완료된 주문의 총 금액'을 구하는 SQL을 작성해줘. 결과만 SQL로 줘."
    sql = call_llm(task_prompt).strip().replace("```sql", "").replace("```", "")
    print(f"LLM generated SQL: {sql}")

    # 3. SQL 실행
    print("\n--- Step 3: Executing SQL ---")
    result = manager.run_task(sql)
    print(f"Execution Result: {result}")

    # 4. 성찰 (Self-Reflection) - 학습 단계
    print("\n--- Step 4: Reflection & Learning ---")
    reflection_context = manager.get_reflection_context(sql, result)
    with open('services/myaicoder/src/myaicoder/tools/database/prompts/reflection.md', 'r') as f:
        reflection_system_prompt = f.read()
    
    learning_output = call_llm(reflection_context, system_prompt=reflection_system_prompt)
    print(f"LLM Learning Output:\n{learning_output}")

    # 5. 지식 업데이트 적용
    print("\n--- Step 5: Applying Knowledge Update ---")
    manager.apply_reflection_update(learning_output)

    # 6. 최종 지식 파일 확인
    print("\n--- Step 6: Verifying Updated Knowledge ---")
    patterns = manager.read_knowledge("patterns.md")
    print(f"Updated patterns.md:\n{patterns}")

    # 정리
    if os.path.exists(db_path):
        os.remove(db_path)

if __name__ == "__main__":
    run_integration_test()
