import os
import sys
import sqlite3
import requests
import json

# 프로젝트 경로 설정
sys.path.append(os.path.join(os.getcwd(), 'services/myaicoder/src'))
from myaicoder.tools.database.manager import SQLManager

def call_llm(prompt, system_prompt="You are a SQL expert."):
    url = "http://localhost:8080/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": "qwen",
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
        "temperature": 0
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        return response.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Error: {str(e)}"

def run_training_cycle(manager, task_description):
    print(f"\n[Task] {task_description}")
    
    # 1. 지식 기반 쿼리 생성
    knowledge_context = f"Schema:\n{manager.read_knowledge('schema.md')}\nPatterns:\n{manager.read_knowledge('patterns.md')}"
    prompt = f"현재 지식:\n{knowledge_context}\n\n과제: {task_description}\nSQL만 출력해줘."
    sql = call_llm(prompt).strip().replace("```sql", "").replace("```", "")
    print(f"> Generated SQL: {sql}")

    # 2. 실행
    result = manager.run_task(sql)
    print(f"> Execution: {result['status']}")

    # 3. 성찰 및 학습
    reflection_context = manager.get_reflection_context(sql, result)
    with open('services/myaicoder/src/myaicoder/tools/database/prompts/reflection.md', 'r') as f:
        reflection_system_prompt = f.read()
    
    learning_output = call_llm(reflection_context, system_prompt=reflection_system_prompt)
    manager.apply_reflection_update(learning_output)
    print("> Learning complete.")

def start_bootcamp():
    db_path = "bootcamp.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 복잡한 스키마 생성
    cursor.execute("CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT);")
    cursor.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, category_id INTEGER, price INTEGER);")
    cursor.execute("CREATE TABLE sales (id INTEGER PRIMARY KEY, product_id INTEGER, qty INTEGER, sale_date TEXT);")
    
    # 샘플 데이터 주입
    cursor.execute("INSERT INTO categories (name) VALUES ('Electronics'), ('Books');")
    cursor.execute("INSERT INTO products (name, category_id, price) VALUES ('Laptop', 1, 1000), ('Keyboard', 1, 50), ('Novel', 2, 20);")
    cursor.execute("INSERT INTO sales (product_id, qty, sale_date) VALUES (1, 2, '2026-04-01'), (2, 5, '2026-04-02'), (3, 10, '2026-04-03');")
    
    conn.commit()
    conn.close()

    manager = SQLManager(db_path)
    manager.sync_schema()

    # 트레이닝 시나리오 실행
    scenarios = [
        "각 상품의 이름과 해당 상품이 속한 카테고리 이름을 함께 보여줘. (Join 경험)",
        "카테고리별로 총 매출액(price * qty)을 계산해서 매출이 높은 순으로 정렬해줘. (Aggregation & Math 경험)",
        "존재하지 않는 'customer_name' 컬럼을 조회하려고 시도해보고, 에러가 나면 어떻게 대처해야 할지 학습해. (Error Handling 경험)",
        "2026년 4월 2일 이후에 팔린 상품들의 목록을 뽑아줘. (Date handling 경험)"
    ]

    for scenario in scenarios:
        run_training_cycle(manager, scenario)

    print("\n--- Bootcamp Finished! ---")
    print("Final Knowledge in schema.md:")
    print(manager.read_knowledge("schema.md"))

    if os.path.exists(db_path):
        os.remove(db_path)

if __name__ == "__main__":
    start_bootcamp()
