# myAiCoder - Project CLAUDE.md

## Level: Enterprise

## Overview
- Project: myAiCoder
- Architecture: Microservices (Monorepo)
- Frontend: Next.js 14+ (Turborepo)
- Backend: Python FastAPI
- Infrastructure: AWS EKS + Terraform
- CI/CD: GitHub Actions + ArgoCD

## Language
- Default: Korean (한국어)
- Code/Comments: English
- Documentation: Korean

## Directory Structure
```
apps/          → Frontend apps (Turborepo)
packages/      → Shared packages (UI, API client, config)
services/      → Backend microservices (FastAPI)
infra/         → Terraform + Kubernetes manifests
docs/pdca/     → PDCA documents (plan → design → do → check → act)
chat_log/      → Session logs (numbered for traceability)
scripts/       → Utility scripts
```

## Architecture: Clean Architecture (4-Layer)
- API Layer → Application Layer → Domain Layer → Infrastructure Layer
- Dependency direction: Top → Bottom
- Domain Layer depends on nothing

## Key Conventions
- Repository Pattern for data access
- Async/await for all I/O operations
- Type hints required (Python) / TypeScript strict mode
- All inter-service communication via internal API or message queue
- Secrets from AWS Secrets Manager only (never hardcoded)

## PDCA Workflow
1. Plan → docs/pdca/01-plan/
2. Design → docs/pdca/02-design/
3. Do → Implementation
4. Check → docs/pdca/04-check/
5. Act → docs/pdca/05-act/

## SoR (Source of Record) Priority
1. Code (source of truth)
2. CLAUDE.md / Convention docs
3. docs/ design documents
