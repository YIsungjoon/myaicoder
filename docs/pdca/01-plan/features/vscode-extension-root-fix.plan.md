# Plan: vscode-extension-root-fix

## Overview
- **Feature**: vscode-extension-root-fix
- **Type**: Bug Fix (Hotfix)
- **Date**: 2026-04-22
- **Priority**: High

## Problem Statement

VS Code 익스텐션의 MCP 상태 패널이 실제 Python 프로세스 설정이 아닌 익스텐션 하드코딩 기본값을 표시함.

- **증상**: 상태바에 `qwen3.5-27b` (기본값), `100.78.49.9:8080` (VS Code 설정값)가 표시됨
- **근본 원인**: `getLlmUrl()` / `getModelName()`이 hardcoded 기본값을 반환하고, 이를 CLI 인수로 전달해 Python의 `.env` 설정을 덮어씀

## Goals

1. VS Code 설정에서 명시적으로 설정하지 않은 경우 LLM URL/Model을 Python 프로세스에 전달하지 않음
2. LLM URL/Model을 CLI 인수 대신 환경변수로 전달 (`MYAICODER_API_KEY` 패턴 통일)
3. 상태 표시: 미설정 시 `(server default)` 표시

## Scope

- `apps/vscode-extension/src/mcp/process.ts` — CLI arg → env var 전환
- `apps/vscode-extension/src/config.ts` — 반환 타입 `string | undefined`
- `apps/vscode-extension/src/ui/mcp-status.ts` — undefined 표시 처리
- `apps/vscode-extension/src/ui/statusbar.ts` — undefined 표시 처리
- `apps/vscode-extension/src/extension.ts` — 진단 로그 undefined 처리
- `apps/vscode-extension/test/unit/config.test.ts` — 기대값 업데이트
- `apps/vscode-extension/test/unit/process.test.ts` — env var 테스트 추가

## Out of Scope

- Python 서버로부터 실제 설정값 조회 (MCP 프로토콜 확장 필요)
- `workingDir` CLI 인수 — 민감하지 않아 현행 유지
