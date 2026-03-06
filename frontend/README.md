# Frontend Workspace

This frontend is a Vite + React + TypeScript app built against the mock backend contract.

## Run

```bash
cd frontend
npm install
npm run dev
```

The Vite server runs on `http://localhost:5173` and proxies `/api/*` to `http://localhost:8000`.

## Contract inputs

- `../frontend_agent_contract.md`
- `src/shared/api/generated/backend-sdk.ts`

## Build

```bash
cd frontend
npm run build
```
