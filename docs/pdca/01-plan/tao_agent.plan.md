# TAO (Thought-Action-Observation) 에이전트 전환 계획

## 1. 개요 및 배경
- **문제점**: 로컬 LLM(예: LM Studio에 올라간 Qwen, Gemma 등)의 추론 능력 및 지시 준수 한계로 인해, 파일 분석 요청 시 자율적인 도구 호출(Tool Calling)을 건너뛰고 텍스트 답변으로 조기 종료하는 현상이 잦음.
- **해결책**: 에이전트의 작동 방식을 명시적인 **TAO (Thought-Action-Observation)** 프레임워크로 규정하여 에이전트의 추론 경로를 강제하고, 사용자가 에이전트의 사고 과정을 투명하게 모니터링할 수 있도록 설계함.

## 2. TAO 프레임워크 정의
- **Thought (사고)**: 현재 사용자의 목표 대비 진행 상황을 판단하고, 다음으로 수행해야 할 툴과 그 이유를 논리적으로 생각함.
- **Action (행동)**: Thought에 따라 실제 툴(Tool)을 호출함. (OpenAI `tool_calls` 규격)
- **Observation (관찰)**: 툴의 실행 결과(출력 또는 에러)를 관찰하고 지식을 업데이트함 (대화 이력에 `role: tool`로 주입).

## 3. 구현 범위 및 목표 (Strategy)
### 3.1. 시스템 프롬프트 개편
- `context.py` 내 `AGENTIC_BASE_PROMPT`를 수정하여 에이전트가 답변을 생성할 때 반드시 `Thought:` 블록을 작성하고 도구를 호출하도록 구조화된 예시와 지침을 주입.

### 3.2. 실행 엔진 (Engine) 고도화
- `engine.py` 내 `MiddlewareEngine.chat()`의 실행 루프 수정.
- 매 단계마다 LLM의 출력물 중 `Thought` 블록을 파싱하여, 실시간 진행 로그(`on_progress`)에 Thought 내용을 명확하게 표출.

### 3.3. UI 피드백 시각화
- VS Code Chat Panel 및 CLI UI에서 에이전트의 실시간 `Thought` 상태를 사용자에게 명시적으로 표시.

## 4. 추진 일정
1. **Plan & Design** (Strategy) -> `docs/pdca/01-plan/tao_agent.plan.md`, `docs/pdca/02-design/tao_agent.design.md` 작성
2. **Execution** (Do) -> `context.py`, `engine.py` 코드 수정
3. **Validation** (Check) -> 가상환경 CLI 테스트 및 연동 디버깅
4. **Wrap-up** (Act) -> 릴리즈 반영 및 Git Commit & Push
