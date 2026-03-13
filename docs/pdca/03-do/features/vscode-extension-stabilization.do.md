# Do: VS Code Extension Stabilization (Phase 5.1)

**Feature**: vscode-extension
**날짜**: 2026-03-13
**Phase**: Do
**Iteration**: 5.1 stabilization

---

## 1. 목적

아카이브 이후 backlog로 남아 있던 안정화 항목 중, 구현과 테스트로 즉시 닫을 수 있는 항목을 우선 반영한다.

## 2. 이번에 반영한 변경

### 2.1 아이콘 추가

- `apps/vscode-extension/media/icon.png`
- `package.json`에서 참조하던 activity bar 아이콘 파일을 실제로 추가

### 2.2 `buildServeArgs` 중복 제거

- `src/mcp/client.ts`의 인자 조합 로직을 `src/mcp/process.ts`의 `buildServeArgs()`로 통합
- 향후 serve 인자 변경 시 테스트 기준과 실제 연결 코드가 분리되지 않도록 정리

### 2.3 프로세스 종료 감지 및 자동 재연결

- `StdioClientTransport.onclose`를 사용해 예기치 않은 종료를 감지
- 수동 `disconnect()`가 아닌 경우 자동으로 `connect()` 재시도
- 연결/해제/재연결 실패를 extension 쪽 status bar 및 사용자 메시지와 연결

### 2.4 테스트 보강

- `test/unit/config.test.ts`
  - `resolveExecutablePath()` happy-path 3종 추가
    - 설정 경로
    - PATH lookup
    - workspace `.venv`
- `test/unit/client.test.ts`
  - `connect()` happy-path 추가
  - 예기치 않은 transport close 시 auto-reconnect 검증 추가
- `test/integration/extension.test.ts`
  - activate/deactivate 통합 성격 테스트 추가

## 3. 검증 결과

실행 명령:

```bash
pnpm --filter myaicoder test
```

결과:

- 4 test files passing
- 20 tests passing
- failure 없음

## 4. 남은 항목

이번 안정화에서 남아 있을 수 있는 항목:

- auto-reconnect 동작의 실제 VS Code 런타임 수동 검증
- 필요 시 더 강한 통합 테스트(`@vscode/test-electron`) 확장
- 후속 gap analysis 갱신

## 5. 다음 단계

- `Check`: 변경 후 match rate 재평가
- 필요하면 `vscode-extension` archive backlog를 갱신하거나 후속 report 작성
