# Windows 원클릭 설치 — 방안별 상세 비교

**작성일**: 2026-03-15
**결정**: 방안 1 (GitHub Actions CI) 채택

---

## 현재 oneclick-installer 현황

### 이미 완성된 것 (Linux/macOS에서 빌드)
- `install.bat` — Windows용 설치 스크립트 (관리자 상승, PATH, settings.json 주입)
- `install.command` — macOS용
- `myaicoder.spec` — PyInstaller spec
- `build-installer.sh` — Linux에서 빌드 → zip 패키지
- `config.json` — 서버 URL, 모델명 등

### 문제: Windows .exe 빌드 불가

현재 `build-installer.sh`는 Linux에서 실행되므로 Linux 바이너리만 생성됩니다. Windows .exe는 Windows 환경에서 PyInstaller를 돌려야 합니다.

---

## 방안별 상세 분석

### 방안 1. GitHub Actions CI에서 .exe 빌드 (채택)

**구조**: `git tag push → windows-latest runner → PyInstaller → Release 첨부`

| 장점 | 단점 |
|------|------|
| 태그 하나로 완전 자동화 (빌드→패키징→배포) | GitHub Actions 워크플로우 작성·디버깅 필요 |
| `windows-latest` runner에 Python/Node 사전 설치됨 | Private repo는 월 2,000분 무료 제한 (Public은 무제한) |
| 재현 가능한 빌드 환경 (팀원 누구나 태그만 push) | PyInstaller 첫 빌드 시 runner 캐시 없으면 3~5분 소요 |
| 기존 `ext-v*` CI 패턴과 통일 (학습 비용 0) | runner에서 실제 실행 테스트 불가 (빌드만 검증) |
| Linux + Windows 동시 빌드 가능 (matrix) | 코드 사이닝 없으면 SmartScreen 경고는 동일 |
| Release에 .zip 첨부 → 사내 인트라넷 배포 연계 용이 | |

**적합한 경우**: 반복 배포가 예상될 때, 팀 규모 2명 이상

---

### 방안 2. Windows 노트북에서 수동 빌드

**구조**: `Windows PC에서 Python + PyInstaller 설치 → 수동 빌드 → zip 배포`

| 장점 | 단점 |
|------|------|
| 즉시 시작 가능 (추가 인프라 불필요) | 매번 수동 실행 (빌드 스크립트는 작성 가능하나 트리거 수동) |
| 빌드 직후 실행 테스트 가능 (실제 Windows 환경) | Python/uv/Node 환경 세팅이 노트북마다 다름 |
| SmartScreen 동작도 바로 확인 가능 | 빌드 환경 재현 어려움 (다른 PC에서 같은 결과 보장 못 함) |
| 네트워크 없이도 가능 | 빌드 담당자 부재 시 빌드 불가 (버스 팩터 1) |
| | 버전 관리 실수 가능 (수동 태깅, 수동 Release 업로드) |

**적합한 경우**: 1회성 테스트, 또는 배포 빈도가 매우 낮을 때

---

### 방안 3. Wine / Cross-compile (Linux에서 Windows .exe) — 비권장

**구조**: `Linux에서 Wine + Windows Python → PyInstaller → .exe 생성`

| 장점 | 단점 |
|------|------|
| 기존 Linux 빌드 파이프라인 유지 | PyInstaller + Wine 조합은 공식 미지원 (커뮤니티 해킹) |
| Windows 머신 불필요 | Wine에서 Windows Python 설치 자체가 불안정 |
| CI에서도 가능 (Docker + Wine) | `ctypes`, `win32api` 등 Windows 전용 모듈 로드 실패 빈번 |
| | 생성된 .exe가 실제 Windows에서 동작 안 할 수 있음 (DLL 누락) |
| | 디버깅이 극도로 어려움 (Wine 로그 해석 필요) |
| | PyInstaller 업데이트마다 Wine 호환성 재검증 필요 |

**적합한 경우**: 거의 없음. 실험적 용도 외에는 비권장

---

### 방안 4. NSIS / Inno Setup 전문 인스톨러

**구조**: `PyInstaller .exe + Inno Setup 스크립트 → setup.exe (GUI 마법사)`

| 장점 | 단점 |
|------|------|
| "다음 → 다음 → 설치" 친숙한 GUI 경험 | Inno Setup 스크립트 학습·유지보수 비용 |
| 자동 시작 메뉴 등록, 바탕화면 바로가기 | 현재 install.bat과 기능 중복 (재작성) |
| 언인스톨러 자동 생성 (프로그램 추가/제거) | Inno Setup은 Windows 전용 → CI에서 Wine 필요 (방안 3 문제 재발) |
| 코드 사이닝 인증서 적용하면 SmartScreen 해결 | 코드 사이닝 인증서 연간 $100~$400 비용 |
| 전문적인 인상 (사내 배포라도 신뢰도 향상) | 25MB 바이너리에 인스톨러 오버헤드 추가 (~2MB) |
| 설치 경로 선택 등 유연한 옵션 제공 | 현재 요구사항 대비 과도한 복잡도 |

**적합한 경우**: 외부 고객 배포, 언인스톨 지원 필수, 전문적 이미지 필요 시

---

## 종합 비교

| 기준 | 방안 1 (CI) | 방안 2 (수동) | 방안 3 (Wine) | 방안 4 (Inno) |
|------|:-----------:|:------------:|:-------------:|:-------------:|
| 초기 구축 비용 | 중 | **낮음** | 높음 | 높음 |
| 반복 배포 비용 | **최소** | 높음 | 중 | 중 |
| 빌드 재현성 | **높음** | 낮음 | 낮음 | 중 |
| 실행 안정성 | 높음 | **높음** | **낮음** | 높음 |
| 사용자 경험 | 좋음 | 좋음 | 불확실 | **최고** |
| 유지보수 부담 | **낮음** | 중 | **높음** | 중 |
| 현재 아키텍처 호환 | **높음** | 높음 | 낮음 | 중 |

## 결정

```
채택 → 방안 1 (GitHub Actions CI)
이유 → 자동화, 재현성, 기존 CI 패턴 통일, 유지보수 최소
향후 → 필요 시 방안 4 (Inno Setup) UX 업그레이드 고려
```
