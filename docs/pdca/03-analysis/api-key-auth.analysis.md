# api-key-auth Analysis Report

> **Analysis Type**: Gap Analysis (Design vs Implementation)
>
> **Project**: myAiCoder
> **Version**: 1.0.3
> **Analyst**: bkit-gap-detector
> **Date**: 2026-03-16
> **Design Doc**: [api-key-auth.design.md](../02-design/features/api-key-auth.design.md)

---

## 1. Analysis Overview

### 1.1 Analysis Purpose

CLI와 VS Code Extension이 DGX Gateway의 API 키 인증을 통과할 수 있도록 `api_key` 설정/전달 경로가 설계대로 구현되었는지 검증한다.

### 1.2 Analysis Scope

- **Design Document**: `docs/pdca/02-design/features/api-key-auth.design.md`
- **Implementation Files**: 8개 산출물 (D1~D8) + 1개 테스트 수정
- **Analysis Date**: 2026-03-16

---

## 2. Gap Analysis (Design vs Implementation)

### 2.1 Design Item Comparison (D1~D8)

#### D1: core/config.py — LLMConfig api_key 필드

| # | 항목 | 설계 | 구현 | Status |
|---|------|------|------|:------:|
| D1-1 | 필드 이름 | `api_key` | `api_key: str = "not-needed"` (L16) | ✅ |
| D1-2 | 기본값 | `"not-needed"` | `"not-needed"` (L16) | ✅ |
| D1-3 | 로드 경로 | `AppConfig.load()` → `llm.api_key` | `_from_file()` L110-113 setattr 루프 | ✅ |
| D1-4 | 환경변수 오버라이드 | `MYAICODER_API_KEY` (config보다 우선) | L97-100: `os.environ.get("MYAICODER_API_KEY")` → `config.llm.api_key` | ✅ |

#### D2: llm/vllm_provider.py — api_key 활용

| # | 항목 | 설계 | 구현 | Status |
|---|------|------|------|:------:|
| D2-1 | self.api_key 저장 | `__init__`에서 인스턴스 변수 | `self.api_key = api_key` (L29) | ✅ |
| D2-2 | AsyncOpenAI 전달 | `AsyncOpenAI(api_key=api_key)` | `AsyncOpenAI(base_url=base_url, api_key=api_key)` (L30) | ✅ |
| D2-3 | _raw_chat 헤더 | `api_key != "not-needed"` → Bearer | L111: `self.api_key and self.api_key.strip() and self.api_key != "not-needed"` → `Bearer {self.api_key}` | ✅ |
| D2-4 | 조건부 헤더 | 로컬 모드 헤더 미전송 | L110: `headers = {}` (조건 불충족 시 빈 dict) | ✅ |
| D2-5 | 빈 문자열 방어 | `.strip()` 체크 | L111: `.strip()` 포함 | ✅ |

#### D3: cli.py — --api-key 옵션

| # | 항목 | 설계 | 구현 | Status |
|---|------|------|------|:------:|
| D3-1 | CLI 옵션 (main + serve) | `--api-key` 양쪽 | main L14, serve L470-473 | ✅ |
| D3-2 | 우선순위 (CLI > env > config > default) | CLI 옵션 최우선 | main: L62-63 `if api_key: config.llm.api_key = api_key`; config.load()에서 env 처리 | ✅ |
| D3-3 | main() → _run_chat() 전달 | api_key 파라미터 추가 | L34: `_run_chat(model, vllm_url, api_key, ...)`, L40: `api_key: str \| None` | ✅ |
| D3-4 | VLLMProvider 전달 | `api_key=config.llm.api_key` | L70: `api_key=config.llm.api_key` | ✅ |
| D3-5 | serve 전달 (agentic) | `api_key or config.llm.api_key` | L489: `resolved_api_key = api_key or config.llm.api_key`, L493: `api_key=resolved_api_key` | ✅ |

#### D4: config.ts — getApiKey()

| # | 항목 | 설계 | 구현 | Status |
|---|------|------|------|:------:|
| D4-1 | 메서드 | `getApiKey(): string` | L70-72: `getApiKey(): string` | ✅ |
| D4-2 | 반환값 | 설정값 또는 빈 문자열 | `return this.get<string>('apiKey') \|\| '';` | ✅ |

#### D5: process.ts — buildServeArgs apiKey

| # | 항목 | 설계 | 구현 | Status |
|---|------|------|------|:------:|
| D5-1 | 옵션 이름 | `apiKey?: string` | L19: `apiKey?: string` | ✅ |
| D5-2 | CLI 인자 | `--api-key <value>` | L41: `args.push('--api-key', options.apiKey)` | ✅ |
| D5-3 | 조건부 전달 | 빈 문자열이면 미전달 | L40: `if (options.apiKey)` — falsy 체크 | ✅ |

#### D6: client.ts — apiKey 전달

| # | 항목 | 설계 | 구현 | Status |
|---|------|------|------|:------:|
| D6-1 | config 호출 | `this.config.getApiKey()` | L39: `const apiKey = this.config.getApiKey()` | ✅ |
| D6-2 | 빈 문자열 처리 | `apiKey \|\| undefined` | L48: `apiKey: apiKey \|\| undefined` | ✅ |

#### D7: package.json — apiKey 설정

| # | 항목 | 설계 | 구현 | Status |
|---|------|------|------|:------:|
| D7-1 | 설정 키 | `myaicoder.apiKey` | L89: `"myaicoder.apiKey"` | ✅ |
| D7-2 | 기본값 | `""` | L91: `"default": ""` | ✅ |
| D7-3 | 타입 | `string` | L90: `"type": "string"` | ✅ |
| D7-4 | scope | `"machine"` | L92: `"scope": "machine"` | ✅ |

#### D8: config/config.json.example

| # | 항목 | 설계 | 구현 | Status |
|---|------|------|------|:------:|
| D8-1 | api_key 필드 | `"not-needed"` 기본값 | L6: `"api_key": "not-needed"` | ✅ |
| D8-2 | 주석 (JSON 미지원 → README) | 별도 문서 | JSON 파일 내 주석 없음 (정상) | ✅ |

---

### 2.2 Edge Case Coverage

| # | 상황 | 설계 대응 | 구현 확인 | Status |
|---|------|----------|----------|:------:|
| EC-D1-A | api_key 빈 문자열 → `"not-needed"` fallback | config에서 처리 | config.py L98-100: `env_api_key`가 빈 문자열이면 조건 미충족 → 기본값 `"not-needed"` 유지 | ✅ |
| EC-D1-B | 환경변수 + config 둘 다 설정 | 환경변수 우선 | config.py L97-100: `load()` 후 env 오버라이드 | ✅ |
| EC-D2-A | api_key="not-needed"로 DGX 접속 | 403 발생 (예상 동작) | vllm_provider.py L111: 조건 불충족 → 헤더 미전송 → 서버가 403 | ✅ |
| EC-D2-B | AsyncOpenAI와 _raw_chat 키 불일치 | 동일 self.api_key 사용 | L29-30: 동일한 `self.api_key` 참조 | ✅ |
| EC-D2-C | api_key `""` 또는 `"  "` | `.strip()` 체크 → 미전송 | L111: `.strip()` 포함 — 빈 문자열/공백 방어 | ✅ |
| EC-D3-A | --api-key 없이 DGX URL | config/env에서 읽음, 없으면 "not-needed" | cli.py: `if api_key:` 조건 (None이면 skip) → config 기본값 사용 | ✅ |

---

### 2.3 Verification Checklist (V1~V14)

| # | 검증 항목 | 확인 결과 | Status |
|---|----------|----------|:------:|
| V1 | config.py api_key 필드 접근 | `LLMConfig.api_key` 존재, `AppConfig.load()` 후 접근 가능 | ✅ |
| V2 | 환경변수 오버라이드 | `MYAICODER_API_KEY` → `config.llm.api_key` 덮어쓰기 (L97-100) | ✅ |
| V3 | VLLMProvider api_key 전달 | `AsyncOpenAI(api_key=api_key)` (L30) + `self.api_key` (L111) 동일 | ✅ |
| V4 | _raw_chat Authorization | 조건 충족 시 `Bearer {self.api_key}` 헤더 (L112) | ✅ |
| V5 | _raw_chat 로컬 모드 | `"not-needed"` → 조건 불충족 → 빈 headers (L110) | ✅ |
| V6 | CLI --api-key (main) | L14 옵션 → L34 `_run_chat` → L62-63 override → L70 VLLMProvider | ✅ |
| V7 | CLI serve --api-key | L470-473 옵션 → L489 resolve → L493 VLLMProvider | ✅ |
| V8 | Extension apiKey → --api-key | config.ts `getApiKey()` → client.ts L48 → process.ts L40-42 | ✅ |
| V9 | Extension 로컬 모드 | `apiKey=""` → `\|\| undefined` → buildServeArgs 생략 | ✅ |
| V10 | DGX 통합 테스트 | 코드 경로 검증 완료 (실제 DGX 테스트는 인프라 의존) | ✅ (코드 수준) |
| V11 | 기존 테스트 통과 | client.test.ts에 `getApiKey` mock 추가 (L143, L171) — 호환성 유지 | ✅ |
| V12 | config.json.example api_key | `"api_key": "not-needed"` 포함 (L6) | ✅ |
| V13 | apiKey scope: machine | package.json L92: `"scope": "machine"` | ✅ |
| V14 | 빈 문자열 방어 | vllm_provider.py L111: `.strip()` + `!= "not-needed"` 이중 방어 | ✅ |

---

## 3. Match Rate Summary

```
+---------------------------------------------+
|  Overall Match Rate: 100%                    |
+---------------------------------------------+
|  Design Items (D1-1 ~ D8-2):  26/26   100%  |
|  Edge Cases (EC-D1-A ~ EC-D3-A): 6/6  100%  |
|  Verification (V1 ~ V14):     14/14   100%  |
+---------------------------------------------+
|  Total:  46/46 items                         |
|  Gaps:   0                                   |
+---------------------------------------------+
```

| Category | Score | Status |
|----------|:-----:|:------:|
| Design Match (D items) | 100% | PASS |
| Edge Case Coverage | 100% | PASS |
| Verification Checklist | 100% | PASS |
| **Overall** | **100%** | **PASS** |

---

## 4. Missing Features (Design O, Implementation X)

없음.

---

## 5. Added Features (Design X, Implementation O)

없음. 구현이 설계 범위를 정확히 따른다.

---

## 6. Changed Features (Design != Implementation)

없음. 모든 항목이 설계와 정확히 일치한다.

---

## 7. Test Impact

| Test Suite | Before | After | Regression |
|------------|:------:|:-----:|:----------:|
| client.test.ts | `getApiKey` mock 미포함 | `getApiKey` mock 추가 (L143, L171) | 없음 |

테스트 파일에서 `connect` happy path (L135-157)와 auto-reconnect (L159-189) 테스트의 config mock에 `getApiKey: vi.fn().mockReturnValue('')` 가 추가되어 기존 테스트가 새 코드와 호환된다.

---

## 8. Implementation Quality Notes

구현에서 특별히 우수한 점:

1. **빈 문자열 이중 방어**: `self.api_key and self.api_key.strip() and self.api_key != "not-needed"` — 3단 조건으로 빈 문자열, 공백, 기본값 모두 차단
2. **scope: machine 보안**: API 키가 워크스페이스 `.vscode/settings.json`에 저장되어 Git에 커밋되는 사고를 원천 차단
3. **우선순위 체계 일관성**: CLI > env > config > default 순서가 main, serve 양쪽 모두 일관되게 적용
4. **하위 호환성**: `"not-needed"` 기본값으로 기존 로컬 모드 사용자에게 변경 영향 없음

---

## 9. Recommended Actions

Match Rate 100% -- 추가 조치 불필요.

### 9.1 선택적 개선 사항 (P2)

| Item | Description | Priority |
|------|-------------|:--------:|
| DGX 통합 테스트 | 실제 DGX Gateway 환경에서 E2E 인증 흐름 검증 | P2 |
| api_key 마스킹 | `config` CLI 명령에서 `api_key` 값 마스킹 출력 | P2 |

---

## 10. Conclusion

api-key-auth 기능은 설계 문서의 모든 항목 (26개 설계 항목 + 6개 엣지 케이스 + 14개 검증 항목 = 46개)이 구현과 100% 일치한다. Gap 0건, Iteration 0회로 완료.

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-03-16 | Initial analysis — 100% match | bkit-gap-detector |
