# Infrastructure CLAUDE.md

## Stack
- Terraform (IaC)
- Kubernetes (EKS)
- ArgoCD (GitOps)
- Docker

## Environments
| Environment | Infra | Deploy |
|-------------|-------|--------|
| Local | Docker Compose | Manual |
| Staging | EKS | ArgoCD Auto Sync |
| Production | EKS | ArgoCD Manual Sync |

## Security Rules
- No hardcoded secrets
- DB in private subnet only
- IAM role-based access
- mTLS for inter-service communication
