# Frontend Apps CLAUDE.md

## Stack
- Next.js 14+ (App Router)
- TypeScript (strict mode)
- Tailwind CSS
- TanStack Query (server state)
- Zustand (client state)

## Structure
```
apps/{app}/
├── src/
│   ├── app/          # Next.js App Router pages
│   ├── components/   # UI components
│   ├── hooks/        # Custom hooks
│   ├── lib/          # Utilities
│   └── types/        # TypeScript types
├── next.config.js
├── tailwind.config.ts
└── tsconfig.json
```

## Rules
- Server Components by default, 'use client' only when needed
- API calls through packages/api-client
- Shared UI from packages/ui
