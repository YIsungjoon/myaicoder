# Design: marketplace-deployment

## 참조 문서
- Plan: `docs/pdca/01-plan/features/marketplace-deployment.plan.md`
- 기존 Extension: `apps/vscode-extension/` (archived, 99% match rate)

---

## 1. 설계 개요

VS Code Extension 사내 전용 배포를 위한 **7개 산출물** 설계.
코드 변경 없음 — 문서 + 메타데이터 + CI/CD만 추가.
**배포 전략**: 퍼블릭 마켓플레이스 미사용, .vsix 파일을 사내 인트라넷/카카오톡으로 배포.

### 변경 파일 목록

| # | 파일 | 작업 | 설계 항목 |
|---|------|------|----------|
| D1 | `apps/vscode-extension/README.md` | 신규 | Extension 설명 (VS Code 내 표시) |
| D2 | `apps/vscode-extension/CHANGELOG.md` | 신규 | 버전 히스토리 |
| D3 | `apps/vscode-extension/LICENSE` | 신규 | MIT 라이선스 |
| D4 | `apps/vscode-extension/media/icon.png` | 교체 | 128x128 아이콘 |
| D5 | `apps/vscode-extension/package.json` | 수정 | 메타데이터 보강 |
| D6 | `apps/vscode-extension/.vscodeignore` | 수정 | 추가 제외 항목 |
| D7 | `.github/workflows/publish-extension.yml` | 신규 | CI/CD 빌드 + GitHub Releases 배포 |

---

## 2. D1: README.md

VS Code 내 Extension 탭에서 렌더링되는 파일. .vsix 설치 후에도 이 파일이 표시됨.

### 구조

```markdown
# myAiCoder

> AI coding assistant powered by local LLM via MCP

## Features
- (기능 1): 로컬 LLM 기반 AI 코딩 어시스턴트
- (기능 2): MCP 프로토콜 기반 도구 실행 (파일 읽기/쓰기, 검색, 빌드 등)
- (기능 3): Activity Bar 채팅 패널
- (기능 4): 선택 영역 전송 (Ctrl+Shift+L)
- (기능 5): 에이전트 모드 (선택적 다단계 실행)

## Requirements
- myaicoder CLI (`pip install myaicoder` 또는 소스 빌드)
- 로컬 LLM 서버 (llama.cpp, vLLM 등) 또는 호환 API

## Quick Start
1. Extension 설치
2. myaicoder CLI 설치
3. LLM 서버 실행
4. Activity Bar에서 myAiCoder 클릭 → 채팅 시작

## Extension Settings
| Setting | Default | Description |
|---------|---------|-------------|
| myaicoder.executablePath | (auto-detect) | myaicoder CLI 경로 |
| myaicoder.llmUrl | http://localhost:8080 | LLM 서버 URL |
| myaicoder.modelName | qwen3.5-27b | 상태바 표시 모델명 |
| myaicoder.allowBash | false | Bash 도구 허용 여부 |
| myaicoder.maxConcurrent | 1 | 최대 동시 MCP 요청 |
| myaicoder.enableAgentic | false | 에이전트 모드 활성화 |

## Commands
| Command | Keybinding | Description |
|---------|-----------|-------------|
| myAiCoder: New Chat | - | 새 채팅 시작 |
| myAiCoder: Reconnect MCP Server | - | MCP 서버 재연결 |
| myAiCoder: Send Selection to Chat | Ctrl+Shift+L | 선택 영역 전송 |

## Architecture
(간략 다이어그램: Extension → MCP Client → myaicoder serve → LLM)

## License
MIT
```

### 검증 기준
- vsce package 시 README 경고 없음
- 마크다운 렌더링 정상 (헤더, 테이블, 코드블록)

---

## 3. D2: CHANGELOG.md

[Keep a Changelog](https://keepachangelog.com/) 형식 준수.

```markdown
# Changelog

All notable changes to "myAiCoder" will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-03-14

### Added
- Activity Bar 채팅 패널 (WebView 기반)
- MCP 프로토콜 기반 도구 실행 (9개 도구 지원)
- 선택 영역 전송 (Ctrl+Shift+L / Cmd+Shift+L)
- 자동 CLI 감지 (PATH, venv, 수동 설정)
- 상태바 연결 상태 표시
- 에이전트 모드 (선택적 다단계 실행)
- 코드 하이라이팅 (highlight.js)
- 마크다운 렌더링 (marked)
```

### 검증 기준
- Keep a Changelog 형식 유효
- 날짜 ISO 형식

---

## 4. D3: LICENSE

MIT License. 저작자: `myaicoder contributors`.

```
MIT License

Copyright (c) 2026 myaicoder contributors

Permission is hereby granted, free of charge, ...
(표준 MIT 전문)
```

### 검증 기준
- `license` 필드가 package.json에 "MIT"로 설정
- LICENSE 파일 존재

---

## 5. D4: 아이콘 (128x128 PNG)

### 설계

현재 `media/icon.png`은 299B 플레이스홀더. 프로그래밍 방식으로 SVG → PNG 변환하여 교체.

**아이콘 디자인 사양**:
- 크기: 128x128 px
- 배경: 둥근 사각형 (#1e1e1e, VS Code 다크 테마 매칭)
- 전경: "AI" 텍스트 또는 코드 브라켓 심볼 (흰색/파란색 계열)
- 형식: PNG (투명 배경 불가 — 마켓플레이스 요구)

**생성 방법**: Node.js 스크립트로 SVG 문자열 → sharp 라이브러리 PNG 변환
(또는 사용자가 직접 제공 시 교체)

### 검증 기준
- 파일 크기 > 1KB (플레이스홀더가 아님)
- 128x128 px 확인
- PNG 형식

---

## 6. D5: package.json 수정

### 추가/수정할 필드

```jsonc
{
  // 기존 유지: name, displayName, description, version, publisher, engines, ...

  // === 추가 필드 ===
  "license": "MIT",
  "icon": "media/icon.png",
  "repository": {
    "type": "git",
    "url": "https://github.com/myaicoder/myaicoder"
  },
  "homepage": "https://github.com/myaicoder/myaicoder#readme",
  "bugs": {
    "url": "https://github.com/myaicoder/myaicoder/issues"
  },
  "keywords": [
    "ai",
    "coding-assistant",
    "llm",
    "mcp",
    "local-ai",
    "copilot-alternative"
  ],
  "galleryBanner": {
    "color": "#1e1e1e",
    "theme": "dark"
  },

  // === scripts 추가 ===
  "scripts": {
    // 기존 유지
    "build": "node esbuild.config.mjs",
    "watch": "node esbuild.config.mjs --watch",
    "package": "vsce package --no-dependencies",
    "test": "vitest run",
    "lint": "tsc --noEmit -p tsconfig.json",
    // 신규
    "prepackage": "npm run build"
  },

  // === devDependencies 추가 ===
  "devDependencies": {
    // 기존 유지
    "@vscode/vsce": "^3.0.0"  // 신규: vsce CLI
  }
}
```

### 주요 결정

| 결정 | 이유 |
|------|------|
| `--no-dependencies` | esbuild가 이미 dependencies 번들 |
| `@vscode/vsce` devDep | CI에서 npx 대신 로컬 설치 사용 |
| `icon` 필드 추가 | VS Code 내 아이콘 표시 (기존에 activity bar만 참조) |
| preview 제거 | 사내 전용 배포이므로 불필요 |

### 검증 기준
- `vsce ls` 출력에 필수 필드 포함
- `vsce package` 경고 0개
- JSON 유효성

---

## 7. D6: .vscodeignore 수정

### 현재

```
.vscode/**
.vscode-test/**
src/**
test/**
node_modules/**
.gitignore
tsconfig.json
esbuild.config.mjs
**/*.map
```

### 추가할 항목

```
# 기존 유지
.vscode/**
.vscode-test/**
src/**
test/**
node_modules/**
.gitignore
tsconfig.json
esbuild.config.mjs
**/*.map

# 신규 추가
.claude/**
vitest.config.ts
pnpm-lock.yaml
**/*.test.ts
**/*.spec.ts
CONTRIBUTING.md
.github/**
```

### 검증 기준
- `vsce ls`에 src/, test/, .claude/ 미포함
- dist/, media/, README.md, CHANGELOG.md, LICENSE 포함

---

## 8. D7: CI/CD 빌드 + GitHub Releases 배포 파이프라인

### 파일: `.github/workflows/publish-extension.yml`

```yaml
name: Build Extension

on:
  push:
    tags:
      - 'ext-v*'  # ext-v0.1.0, ext-v0.2.0 등

jobs:
  build:
    name: Build & Release VS Code Extension
    runs-on: ubuntu-latest
    permissions:
      contents: write

    defaults:
      run:
        working-directory: apps/vscode-extension

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install dependencies
        run: npm ci

      - name: Typecheck
        run: npm run lint

      - name: Test
        run: npm test

      - name: Build
        run: npm run build

      - name: Package
        run: npx @vscode/vsce package --no-dependencies

      - name: Upload .vsix artifact
        uses: actions/upload-artifact@v4
        with:
          name: myaicoder-vsix
          path: apps/vscode-extension/*.vsix

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: apps/vscode-extension/*.vsix
          generate_release_notes: true
```

### 설계 결정

| 결정 | 이유 |
|------|------|
| `ext-v*` 태그 트리거 | 메인 코드 태그(`v*`)와 분리, extension만 빌드 |
| GitHub Releases 첨부 | 사내 배포용 .vsix 다운로드 링크 자동 생성 |
| `permissions: contents: write` | Release 생성에 필요 |
| `--no-dependencies` | esbuild 번들이 이미 dependencies 포함 |
| 마켓플레이스 publish 없음 | 사내 전용 배포 (보안 및 자산 보호) |
| npm ci (pnpm 대신) | Extension 독립 패키지, 워크스페이스 불필요 |

### 배포 플로우

```
git tag ext-v0.1.0 → GitHub Actions → .vsix 빌드 → GitHub Release 첨부
                                                        ↓
                                        사내 인트라넷 / 카카오톡으로 .vsix 공유
                                                        ↓
                            code --install-extension myaicoder-0.1.0.vsix
```

### 검증 기준
- YAML 구문 유효
- 태그 없는 push에서 트리거 안 됨
- GitHub Release에 .vsix 파일 첨부 확인

---

## 9. 보안 검토 체크리스트

| # | 검토 항목 | 확인 방법 | 기대 결과 |
|---|----------|----------|----------|
| S1 | 하드코딩 시크릿 | `grep -r "token\|secret\|password\|api_key" src/` | 0건 |
| S2 | .vscodeignore 누락 | `vsce ls` | src/, test/, .claude/ 미포함 |
| S3 | 소스맵 제외 | `vsce ls \| grep .map` | 0건 |
| S4 | WebView CSP | src/chat/panel.ts의 CSP 설정 확인 | nonce 기반 CSP |
| S5 | 권한 최소화 | package.json contributes 검토 | 파일시스템 접근 없음 |
| S6 | dependencies 안전 | `npm audit` (highlight.js, marked, mcp-sdk) | 0 vulnerabilities |

---

## 10. 구현 순서

```
S1. README.md 작성                    [D1]
S2. CHANGELOG.md 작성                 [D2]
S3. LICENSE 작성                      [D3]
S4. 아이콘 생성/교체                   [D4]
S5. package.json 메타데이터 보강       [D5]
S6. .vscodeignore 업데이트             [D6]
S7. 보안 검토 수행                     [S1-S6]
S8. vsce package 테스트               [D5 검증]
S9. CI/CD 파이프라인 작성              [D7]
S10. 기존 테스트 통과 확인             [전체 검증]
```

## 11. 검증 매트릭스

| 설계 항목 | 검증 명령 | 성공 기준 |
|----------|----------|----------|
| D1 README | `vsce package` 경고 확인 | README 경고 없음 |
| D2 CHANGELOG | 파일 존재 확인 | Keep a Changelog 형식 |
| D3 LICENSE | `cat LICENSE \| head -1` | "MIT License" |
| D4 아이콘 | `file media/icon.png` | PNG 128x128 |
| D5 package.json | `node -e "JSON.parse(...)"` | 유효 JSON, 필수 필드 |
| D6 .vscodeignore | `vsce ls` | 불필요 파일 미포함 |
| D7 CI/CD | YAML lint | 구문 유효 |
| S1-S6 보안 | grep + vsce ls | 이슈 0건 |
| 전체 | `pnpm --filter myaicoder test` | 20 passed |
| 전체 | `vsce package --no-dependencies` | .vsix 생성, 경고 0개 |
