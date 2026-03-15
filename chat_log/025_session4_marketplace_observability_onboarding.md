# 세션 4 기록 — marketplace-deployment, observability, developer-onboarding

**날짜**: 2026-03-14
**세션**: 4

## 완료된 Feature

### Feature #14: marketplace-deployment (91%)
- VS Code Extension 사내 전용 패키징·배포 준비
- README.md, CHANGELOG.md, LICENSE, 128x128 아이콘 생성
- package.json 메타데이터 보강, .vscodeignore 업데이트
- CI/CD: GitHub Actions ext-v* 태그 → .vsix 빌드 → GitHub Releases 첨부
- **배포 전략 변경**: 퍼블릭 마켓플레이스 → 사내 전용 (인트라넷/카카오톡)
- 보안 검토 100% (CSP nonce, 시크릿 0건)

### Feature #15: observability (100%)
- Gateway에 Prometheus 메트릭 6종 계측
- SSE 스트리밍 핵심: latency/TTFT/tokens를 proxy.py finally에서 측정 (미들웨어 아님)
- 요청 상관 ID (X-Request-ID) + contextvars clear 패턴
- TTFT 버킷 20.0/30.0 추가 (콜드 스타트 대비)
- Grafana 대시보드 6패널 + JSON provisioning
- docker-compose에 Prometheus + Grafana 추가
- 테스트: 241 passed (0 regression)

### Feature #16: developer-onboarding (진행 중 — Plan + Design 완료)
- 신규 개발자 온보딩 문서 + 셋업 자동화
- **로컬 모드 + DGX 서버 모드** 두 가지 지원 결정
- setup-dev.sh 멱등성, 모델 자동 다운로드, backend_command 3-tier fallback
- getting-started.md 서버 모드(3분) + 로컬 모드(10분) Quick Start

## 주요 피드백 반영

| 피드백 | 내용 |
|--------|------|
| 사내 배포 | 퍼블릭 마켓플레이스 미사용, 인트라넷/카카오톡 배포 |
| SSE 계측 | 미들웨어가 아닌 proxy finally에서 측정 |
| contextvars | clear_contextvars() 먼저 호출 |
| TTFT 콜드스타트 | 버킷 끝에 20.0/30.0 추가 |
| 스크립트 멱등성 | cp -n으로 기존 config 보호 |
| 모델 다운로드 | huggingface-cli 자동 다운로드 |
| backend_command | 3-tier fallback (yaml → 환경변수 → PATH) |
| DGX 서버 | 로컬 + 서버 듀얼 모드 지원 |

## 테스트 현황

| 서비스 | 결과 |
|--------|------|
| Python (myaicoder) | 178 passed, 4 skipped |
| Gateway | 43 passed |
| Extension | 20 passed |
| 총합 | 241 passed |

## 추가 작업

### Feature #17: oneclick-installer (100%)
- PyInstaller frozen binary (25MB, onefile)
- install.bat (Windows 관리자 자동 상승, settings.json 주입)
- install.command (macOS code CLI 2-tier 폴백)
- build-installer.sh → myaicoder-setup.zip (24MB)

### CI 오류 수정
- pnpm-lock.yaml 미갱신으로 Extension Tests 실패 (Observability 커밋부터)
- pnpm install → lockfile 업데이트 → CI 3/3 PASS

### 코드베이스 정리
- 불필요 파일 7건 삭제 (중복 config, npm lockfile, 빈 폴더, 플레이스홀더)
- .gitignore에 package-lock.json, COMPLETION_SUMMARY_*.md 추가

### Windows 실제 접속 테스트 (일부 진행)
- 서버: LLM(8001) + Gateway(8080) 구동, 192.168.0.22
- Windows 노트북에서 /health OK 확인
- CLI + Extension 설치 → 다음 세션에서 채팅 테스트 이어서
