# Python Implementation Standards

이 프로젝트의 파이썬 코드 품질을 결정하는 절대 기준이다.

## 1. 클린 코드 & 타입 (Clean Code)
- 모든 함수와 클래스에는 `typing`을 사용한 타입 힌트(Type Hinting)를 명시한다.
- `Google Style` 또는 `NumPy Style` Docstring을 사용하여 자동 문서화가 가능하게 한다.

## 2. 견고한 예외 처리 (Robustness)
- 'LBYL (Look Before You Leap)'보다 'EAFP (Easier to Ask for Forgiveness than Permission)' 원칙을 선호하되, 비어있는 `except: pass`는 절대 금지한다.
- 외부 API 호출 시 반드시 재시도(Retry) 및 타임아웃(Timeout) 로직을 포함한다.

## 3. 도구(Tool) 구현 규칙
- 도구는 단일 책임 원칙(SRP)을 지키며, 가능한 외부 의존성을 최소화하고 표준 라이브러리를 적극 활용한다.
