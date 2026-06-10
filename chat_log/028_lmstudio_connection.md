# LM Studio 연동을 위한 환경 변수 (.env) 설정 변경

## 1. 개요
사용자가 로컬에서 LM Studio를 실행하여 LLM 서버로 사용하고 있으므로, `myaicoder`가 LM Studio API 엔드포인트를 바라보도록 `.env` 환경 변수를 업데이트하였습니다.

## 2. 변경 내용
- 파일: [.env](file:///C:/Users/leehm/project/mycode/myaicoder/.env)
- `MYAICODER_LLM_URL` 값을 기존 `http://localhost:8080/v1`에서 LM Studio의 기본 포트인 `http://127.0.0.1:1234/v1`로 변경하였습니다.
- `MYAICODER_LLM_MODEL`의 기본값(qwen3.5-9b)을 제거하여, 사용자가 LM Studio에서 로드한 모델명을 기입하거나 빈 값으로 두어 서버 기본값으로 매칭될 수 있도록 하였습니다.
- `.env` 파일 내에 존재하던 인라인 한글 주석들(`# Gateway API 키 ...` 등)이 `python-dotenv` 라이브러리에 의해 환경 변수의 값 일부로 파싱되어, API 요청 시 `Authorization: Bearer <주석>` 형태로 잘못 삽입되어 ASCII 인코딩 에러(`\ud0a4` '키')를 발생시키던 문제를 해결하기 위해, 모든 인라인 주석을 이전 줄(Preceding line)로 분리 배치하였습니다.

## 3. 사용자 안내 사항
LM Studio API 서버가 정상적으로 켜져 있는지 확인하고, 필요 시 아래의 URL을 통해 로드된 모델의 정확한 이름을 받아와서 `.env` 파일의 `MYAICODER_LLM_MODEL`에 지정할 수 있습니다.
- API 엔드포인트: `http://127.0.0.1:1234/v1`
- 모델 목록 조회 API: `http://127.0.0.1:1234/v1/models`

## 4. 추가 개선 사항 (2026-06-10)
- **이중 `/v1` 경로 조립 버그 수정**: 
  VS Code Extension의 [client.ts](file:///C:/Users/leehm/project/mycode/myaicoder/apps/vscode-extension/src/mcp/client.ts)에서 사용자 지정 URL 뒤에 자동으로 `/v1`을 덧붙이는 과정에서 중복으로 `/v1/v1`이 되는 현상을 방지하는 예방 로직을 추가하였습니다.
- **VLLMProvider 에러 핸들링 강화**:
  API 호출 실패 시 단순히 `KeyError: 'choices'`로 비정상 종료되는 대신, LM Studio 등 LLM 서버가 반환한 구체적인 에러 메시지(HTTP 상태 코드 및 에러 바디)를 반환하도록 [vllm_provider.py](file:///C:/Users/leehm/project/mycode/myaicoder/services/myaicoder/src/myaicoder/llm/vllm_provider.py) 코드를 보완하였습니다.
- **VS Code 설정 업데이트**:
  사용자의 `settings.json` 내 `myaicoder.llmUrl`을 `http://127.0.0.1:1234`로 변경하고, `myaicoder.executablePath`를 디버깅 가능한 가상환경의 실행 파일 경로로 갱신하여 연동을 완결시켰습니다.

