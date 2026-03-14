# Plan: marketplace-deployment

## Feature 정보

| 항목 | 내용 |
|------|------|
| Feature | marketplace-deployment |
| Track | A-2 (UX 완성 및 제품화) |
| 우선순위 | 중간 |
| 의존 | vscode-extension (archived, 99%) |
| 로드맵 | docs/roadmap-2026-03.md |

## 1. 목적

VS Code Extension을 사내 전용으로 패키징·배포하여, 사내 개발자가 `.vsix` 파일로 간편하게 설치할 수 있게 한다.

### 배경

- vscode-extension feature 완료 (99% match rate, archived)
- 코드는 production-ready이나 패키징 메타데이터 미충족
- 현재 상태: `.vsix` 수동 빌드만 가능
- **배포 전략**: 사내 전용 (퍼블릭 마켓플레이스 미사용 — 보안 및 사내 자산 보호)
- **배포 채널**: 사내 인트라넷, 카카오톡 메신저로 .vsix 파일 공유

## 2. 현재 상태 분석

### 2.1 이미 있는 것 (Ready)

| 항목 | 상태 |
|------|------|
| Extension 코드 | 완료 (src/, webview/, test/) |
| package.json 기본 구조 | publisher, contributes, engines 설정됨 |
| .vscodeignore | src, test, config 제외 설정 |
| esbuild 번들링 | dist/extension.js 생성 |
| `npm run package` 스크립트 | `vsce package` 명령 설정 |
| 테스트 | 20 passed (unit + integration) |

### 2.2 없는 것 (Missing)

| 항목 | 필요 이유 | 복잡도 |
|------|----------|--------|
| README.md | Extension 설명 페이지 (VS Code 내 표시) | 중 |
| CHANGELOG.md | 버전 히스토리 (필수) | 낮 |
| LICENSE | 라이선스 명시 (필수) | 낮 |
| 아이콘 (128x128 PNG) | VS Code 내 표시 (필수, 현재 299B 플레이스홀더) | 중 |
| package.json 메타데이터 | repository, homepage, bugs, keywords | 낮 |
| 보안 검토 | API key 노출 방지, 권한 최소화 | 중 |
| CI/CD 자동 빌드 | GitHub Actions → .vsix 빌드 → GitHub Releases 첨부 | 중 |

## 3. 요구사항

### 3.1 필수 요구사항 (P0)

| ID | 요구사항 | 검증 기준 |
|----|----------|----------|
| R1 | README.md 작성 | 기능 설명, 스크린샷 영역, 설치/사용법, 설정 목록 포함 |
| R2 | CHANGELOG.md 작성 | Keep a Changelog 형식, 0.1.0 초기 릴리스 |
| R3 | LICENSE 파일 | MIT 라이선스 |
| R4 | 아이콘 생성 (128x128 PNG) | VS Code 내 표시 정상 |
| R5 | package.json 메타데이터 보강 | repository, homepage, bugs, keywords, galleryBanner |
| R6 | 보안 검토 | 시크릿 미포함, 권한 최소화 확인 |
| R7 | vsce package 성공 | .vsix 파일 생성, 경고 0개 |

### 3.2 권장 요구사항 (P1)

| ID | 요구사항 | 검증 기준 |
|----|----------|----------|
| R8 | GitHub Actions 빌드 파이프라인 | tag push → .vsix 빌드 → GitHub Releases 첨부 |
| R9 | 버전 관리 전략 | SemVer, pre-release 지원 |

### 3.3 이연 항목 (P2)

| ID | 요구사항 | 이유 |
|----|----------|------|
| R10 | 스크린샷/GIF | 실행 환경 필요 (llama.cpp 서버 + 실제 대화) |
| R11 | 퍼블릭 마켓플레이스 배포 | 사내 전용 배포로 결정, 불필요 |

## 4. 구현 범위

### 4.1 마케팅 자산 (Documentation)

```
apps/vscode-extension/
├── README.md          ← 신규: Extension 설명 (VS Code 내 표시)
├── CHANGELOG.md       ← 신규: 버전 히스토리
├── LICENSE            ← 신규: MIT
└── media/
    └── icon.png       ← 교체: 128x128 적절한 아이콘
```

### 4.2 package.json 보강

```jsonc
{
  // 추가할 필드
  "repository": { "type": "git", "url": "..." },
  "homepage": "...",
  "bugs": { "url": "..." },
  "keywords": ["ai", "coding-assistant", "llm", "mcp", "local-ai"],
  "galleryBanner": { "color": "#1e1e1e", "theme": "dark" },
  "badges": [],
  "license": "MIT",
  // preview 플래그 불필요 (사내 전용)
}
```

### 4.3 보안 검토 항목

| 검토 대상 | 확인 사항 |
|----------|----------|
| src/ 전체 | 하드코딩된 토큰/키 없음 |
| webview/ | XSS 방지 (CSP 설정) |
| .vscodeignore | 불필요 파일 제외 확인 |
| package.json permissions | 최소 권한 원칙 |
| dist/ 번들 | 소스맵 미포함 확인 |

### 4.4 CI/CD 빌드 파이프라인

```yaml
# .github/workflows/publish-extension.yml
trigger: tag push (ext-v*)
steps:
  1. Checkout + Node.js setup
  2. npm ci
  3. lint + test + build
  4. vsce package → .vsix artifact
  5. GitHub Release 생성 + .vsix 첨부
```

**배포 채널**: GitHub Releases → 사내 인트라넷/카카오톡으로 .vsix 공유

## 5. 구현 순서

| 단계 | 작업 | 산출물 |
|------|------|--------|
| S1 | README.md 작성 | apps/vscode-extension/README.md |
| S2 | CHANGELOG.md + LICENSE 작성 | apps/vscode-extension/CHANGELOG.md, LICENSE |
| S3 | 아이콘 생성 (SVG→PNG 128x128) | apps/vscode-extension/media/icon.png |
| S4 | package.json 메타데이터 보강 | package.json 수정 |
| S5 | 보안 검토 수행 | 검토 결과 기록 |
| S6 | vsce package 테스트 | .vsix 파일 생성 확인 |
| S7 | CI/CD 파이프라인 작성 | .github/workflows/publish-extension.yml |
| S8 | 기존 테스트 통과 확인 | 20 passed 유지 |

## 6. 리스크

| 리스크 | 영향 | 대응 |
|--------|------|------|
| 아이콘 품질 | 사내 개발자 인상 저하 | SVG 기반 프로그래밍 생성 (외부 디자인 불필요) |
| vsce 버전 호환성 | 패키징 실패 | @vscode/vsce 최신 버전 고정 |
| .vsix 파일 공유 누락 | 신규 개발자 설치 불가 | 인트라넷 고정 링크 + 카카오톡 공지 |

## 7. 성공 기준

| 기준 | 측정 방법 |
|------|----------|
| vsce package 경고 0개 | CLI 출력 확인 |
| .vsix 파일 정상 생성 | 파일 존재 + 크기 확인 |
| README VS Code 내 렌더링 | vsce ls로 내용물 확인 |
| 기존 테스트 20개 통과 | pnpm --filter myaicoder test |
| 보안 이슈 0건 | 수동 검토 체크리스트 |
| CI 파이프라인 정상 | GitHub Actions dry-run |
