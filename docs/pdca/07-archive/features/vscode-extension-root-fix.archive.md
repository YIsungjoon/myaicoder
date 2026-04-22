# VS Code Extension Root Fix — Archive

> **Status**: Archived
>
> **Project**: myAiCoder
> **Feature**: vscode-extension-root-fix
> **Archive Date**: 2026-04-22
> **Type**: Hotfix
> **Source Report**: [vscode-extension-root-fix.report.md](../../06-report/features/vscode-extension-root-fix.report.md)

---

## 1. Archive Summary

VS Code 익스텐션이 LLM URL/Model 기본값을 CLI 인수로 전달해 Python `.env` 설정을 덮어쓰던
근본 문제를 수정한 핫픽스. `MYAICODER_API_KEY` 환경변수 패턴을 `MYAICODER_LLM_URL` /
`MYAICODER_LLM_MODEL`에 동일하게 적용했다.

- **시작일**: 2026-04-22
- **완료일**: 2026-04-22 (당일 완료)
- **최종 Match Rate**: 100% (10/10 FR)
- **반복**: 0회 (1사이클 완료)
- **테스트**: 23개 전부 통과
- **CI**: ext-v1.0.3 Build Extension SUCCESS

---

## 2. 수정 내용

| 파일 | 변경 사항 |
|------|---------|
| `src/mcp/process.ts` | `--llm-url` / `--model-name` CLI 인수 → `MYAICODER_LLM_URL` / `MYAICODER_LLM_MODEL` env var |
| `src/config.ts` | `getLlmUrl()` / `getModelName()` 반환 타입 `string → string \| undefined` |
| `src/ui/mcp-status.ts` | 미설정 시 `(server default)` 표시 |
| `src/ui/statusbar.ts` | 미설정 시 `connected` fallback |
| `src/extension.ts` | 진단 로그 미설정 시 `(server default)` 표시 |
| `test/unit/config.test.ts` | 미설정 시 `undefined` 기대값으로 업데이트 |
| `test/unit/process.test.ts` | env var 전달 테스트 2개 추가 |

---

## 3. Archived Documents

- Plan: [vscode-extension-root-fix.plan.md](../../01-plan/features/vscode-extension-root-fix.plan.md)
- Design: [vscode-extension-root-fix.design.md](../../02-design/features/vscode-extension-root-fix.design.md)
- Check: [vscode-extension-root-fix.check.md](../../04-check/features/vscode-extension-root-fix.check.md)
- Report: [vscode-extension-root-fix.report.md](../../06-report/features/vscode-extension-root-fix.report.md)

---

## 4. 잔존 권고 사항

| 항목 | 우선순위 | 내용 |
|------|---------|------|
| `'(server default)'` 리터럴 상수화 | Low | `mcp-status.ts`, `extension.ts` 3곳 중복 |
| `'connected'` fallback 상수화 | Low | `statusbar.ts` 2곳 중복 |
| MCP 서버로부터 실제 설정값 조회 | Future | 현재는 VS Code 설정 미입력 시 `(server default)` 표시 |
