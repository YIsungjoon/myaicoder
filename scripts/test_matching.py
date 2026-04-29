import os
import sys

# 프로젝트 경로 설정
sys.path.append(os.path.join(os.getcwd(), 'services/myaicoder/src'))
from myaicoder.agents.db_architect.architect import DBArchitect

def test_architect_recommendation():
    architect = DBArchitect()
    
    scenarios = [
        "내 컴퓨터에서만 쓸 개인용 가계부 앱을 만들고 싶어.",
        "수만 명의 사용자가 동시에 접속하는 글로벌 배달 앱 서버를 구축할 거야."
    ]
    
    for i, req in enumerate(scenarios, 1):
        print(f"\n[Scenario {i}] User: \"{req}\"")
        recommendation = architect.recommend_technician(req)
        print(f"🧐 Architect: \"상황을 분석한 결과, **{recommendation['engine']}**이 가장 적합합니다.\"")
        print(f"👨‍🏫 Reason: {recommendation['reason']}")
        print(f"📞 Matching Technician: {recommendation['expert_class']}")

if __name__ == "__main__":
    test_architect_recommendation()
