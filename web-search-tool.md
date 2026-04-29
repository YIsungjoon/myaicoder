# Plan: WebSearch 도구 추가 (DDGS 기반)

## Objective
myAiCoder에 인터넷 검색 기능(WebSearch)을 추가하여 LLM이 외부 최신 정보를 수집할 수 있도록 한다. API 키가 필요 없는 `duckduckgo-search` (DDGS) 패키지를 활용하며, 검색 결과(URL)를 기존 `WebFetch` 도구와 연계하여 읽어올 수 있도록 시너지를 창출한다.

## Context Anchor
| Dimension | Content |
|-----------|---------|
| WHY | LLM의 학습 데이터가 최신이 아니거나 로컬 환경에 정보가 부족할 때, 외부 지식을 능동적으로 탐색하기 위함 |
| WHO | myAiCoder를 사용하는 개발자 및 에이전트 (Sub-Agent 포함) |
| RISK | DDGS 라이브러리의 Rate Limiting 제약 및 간헐적인 연결 차단 발생 가능성 |
| SUCCESS | `web_search` 도구 호출 시 정상적으로 검색 결과를 반환하고, 에이전트가 이를 이해하여 요약 또는 `WebFetch`와 연계하는 흐름을 완수함 |
| SCOPE | DDGS를 이용한 일반 텍스트 기반 웹 검색 구현 (이미지, 비디오 검색 제외) |

## Key Files & Context
- `services/myaicoder/src/myaicoder/tools/external/web_search.py` (신규 파일)
- `services/myaicoder/src/myaicoder/tools/registry.py` (기존 파일 수정 - 도구 등록)
- `pyproject.toml` / `uv.lock` (기존 파일 수정 - 패키지 의존성 추가)

## Implementation Steps
1. **패키지 의존성 추가**:
   - `services/myaicoder` 디렉토리 내에서 `uv add duckduckgo-search` 명령어를 실행하여 패키지 설치.
2. **WebSearch 도구 구현**:
   - `BaseTool`을 상속받는 `WebSearchTool` 클래스 작성.
   - **스키마 파라미터**: `query` (검색어, 필수), `max_results` (최대 반환 개수, 기본값 5).
   - **반환값**: 각 결과의 `title`, `href`(URL), `body`(스니펫 요약)를 포함하는 JSON 형태.
   - **에러 핸들링**: Rate Limit 오류 시 재시도 안내를 포함한 우아한 실패 처리.
3. **도구 레지스트 연동**:
   - `registry.py`의 기본 도구 목록에 `WebSearchTool`을 추가하여 시스템(및 MCP)에 노출.
4. **단위 테스트 작성**:
   - `services/myaicoder/tests/test_tools/test_web_search.py` 생성.
   - 실제 네트워크를 타거나 모킹(Mocking)을 통해 도구 실행이 정상적인 포맷을 반환하는지 검증.

## Verification & Testing
- 도구 단독 실행 테스트: `web_search`에 "2026 AI 동향" 입력 후 반환 포맷 검증.
- E2E 시나리오 검증: CLI 또는 확장 프로그램을 통해 에이전트에게 "가장 최신 React 19의 변경 사항을 검색하고 요약해줘"라고 요청하여, `WebSearch` -> (선택적 `WebFetch`) -> 최종 답변으로 이어지는 흐름 확인.