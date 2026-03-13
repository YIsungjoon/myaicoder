# 002. Plan 작성: AI Coder CLI

**날짜**: 2026-03-13
**작업 유형**: PDCA Plan
**Feature**: ai-coder-cli

## 수행 내용

### MCP 프로토콜 조사
- MCP = Model Context Protocol, JSON-RPC 2.0 기반 오픈 프로토콜
- 공식 SDK: TypeScript(Tier 1), Python(Tier 1), Go(Tier 1), Rust(Tier 2) 등 10개
- 트랜스포트: stdio(로컬), Streamable HTTP(원격)
- Claude Code는 MCP 클라이언트 + 서버 양쪽 역할 수행

### 언어 평가 (5개 언어 분석)
1. **TypeScript** ★★★★★ — Claude Code와 동일, MCP SDK 최상, IDE 확장 네이티브
2. **Rust** ★★★★☆ — 최고 성능, 단일 바이너리, LLM 바인딩 가능
3. **Python** ★★★★☆ — AI/ML 최강 생태계, CLI 시작 속도 약점
4. **Go** ★★★☆☆ — 배포 우수, AI/ML 생태계 약함
5. **C++** ★★☆☆☆ — llama.cpp 네이티브 성능만 강점

### 추천 조합 3가지
- **옵션 A (추천)**: TypeScript(메인) + Python(추론 서버)
- **옵션 B**: Rust(코어) + TypeScript(IDE 확장)
- **옵션 C**: Python(메인) + TypeScript(IDE 확장)

## 생성 문서
- `docs/pdca/01-plan/features/ai-coder-cli.plan.md`

## 결정 대기 사항
- [ ] 구현 언어 조합 선택
- [ ] LLM 추론 방식 선택 (vLLM / llama.cpp / Ollama)
- [ ] 우선 지원 IDE
- [ ] 프로젝트 이름 확정

## 다음 단계
- 언어 조합 결정 후 → `/pdca design ai-coder-cli`
