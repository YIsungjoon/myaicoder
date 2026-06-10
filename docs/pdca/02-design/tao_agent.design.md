# TAO 에이전트 상세 설계 (Design)

## 1. 시스템 프롬프트 (AGENTIC_BASE_PROMPT) 설계
에이전트가 모든 추론 단계에서 아래 형식을 따르도록 강제합니다.

```markdown
너는 TAO (Thought-Action-Observation) 루프를 수행하는 AI 에이전트이다.
모든 추론 단계에서 다음의 구조로 답변을 출력해야 한다:

THOUGHT: <현재 태스크 상태를 진단하고, 다음 행동 및 필요한 도구를 결정하는 생각 과정>
ACTION: <호출할 도구와 파라미터 정보 (이후 실제 OpenAI tool_calls를 함께 반환해야 함)>

예시:
THOUGHT: 사용자가 스마트팜 관련 계획서 파일 분석을 요청했다. 먼저 워크스페이스에 계획서 파일이 있는지 확인하기 위해 glob_search를 수행해야겠다.
ACTION: glob_search(pattern="*plan*.md")
```

## 2. 엔진 (Engine) 구현 설계
`services/myaicoder/src/myaicoder/core/engine.py` 의 `MiddlewareEngine.chat()`을 다음과 같이 수정합니다.

### 2.1. Thought 파싱 및 progress 알림
LLM이 반환한 `response.content`에서 `THOUGHT:`로 표기된 텍스트를 정규식으로 파싱하여 `on_progress` 콜백으로 방출합니다.

```python
# Thought 파싱 정규식 예시
import re
if response.content:
    thought_match = re.search(r'(?i)thought:\s*(.*?)(?=\n(?:action|observation):|$)', response.content, re.DOTALL)
    if thought_match:
        thought_text = thought_match.group(1).strip()
        await send_progress(f"💡 Thought: {thought_text}")
```

### 2.2. Observation 전달
툴 실행이 완료되면 그 결과물(Observation)을 `role: tool` 메시지 형태로 대화 이력에 추가하여 다음 단계의 Thought 입력으로 공급합니다. 이는 기존의 구조를 유지하되, 프롬프트에서 이를 `Observation`으로 인식하도록 정의합니다.

## 3. UI 및 진행 표시 설계
- 에이전트가 `on_progress` 콜백으로 보내는 메시지 중 `💡 Thought:`로 시작하는 로그는 UI(VS Code Extension Chat Panel 또는 CLI 화면)에서 사용자에게 시각적으로 잘 구분되도록 출력합니다.
