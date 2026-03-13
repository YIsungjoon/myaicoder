# Backend Services CLAUDE.md

## Stack
- Python 3.12+ / FastAPI
- PostgreSQL (schema separation per service)
- Redis (cache, Pub/Sub)
- SQLAlchemy (async ORM)

## Clean Architecture
```
services/{service}/
├── app/
│   ├── api/           # Routers, DTOs
│   ├── application/   # Service classes, Use Cases
│   ├── domain/        # Entities, Repository interfaces
│   └── infrastructure/ # Repository impl, External clients
├── Dockerfile
├── requirements.txt
└── main.py
```

## Rules
- All endpoints async
- Type hints required
- Repository Pattern (ABC interface in domain/)
- No direct DB access from API layer
- Internal APIs use X-Internal-Token header
- Health check endpoint: GET /health
