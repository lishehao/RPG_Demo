# Frontend Contract Mirror

This directory mirrors the current frontend-facing backend contract.

## Current Source Of Truth

Contract governance is defined in:

- `/Users/lishehao/Desktop/Project/RPG_Demo/specs/interface_governance_20260319.md`
- `/Users/lishehao/Desktop/Project/RPG_Demo/specs/interface_stability_matrix_20260319.md`

Frontend should treat the following as the current mirror of backend product APIs:

- `specs/FRONTEND_PRODUCT_SPEC.md`
- `specs/BACKEND_UI_REQUIREMENTS.md`
- `src/api/contracts.ts`
- `src/api/route-map.ts`
- `src/api/http-client.ts`

## Runtime Mode

Current and only supported dev mode is real HTTP.

## What Is In Here

- `specs/FRONTEND_PRODUCT_SPEC.md`
  Product goal, user mental model, page flow, and the stable frontend-facing API surface.
- `specs/BACKEND_UI_REQUIREMENTS.md`
  Only the remaining backend-facing deltas that are not yet fully promoted into the stable product API.
- `src/api/contracts.ts`
  TypeScript mirrors of the stable backend product contracts.
- `src/api/route-map.ts`
  One-to-one mapping from frontend client methods to backend routes.
- `src/api/http-client.ts`
  Real HTTP client for the stable backend routes.
- `src/index.ts`
  Single entry export for frontend consumption.

## Frontend Rules

- Do not bind UI to `/benchmark/*` routes.
- Do not invent frontend-only API fields when the backend contract does not define them.
- Promote product-safe data into backend public contracts first, then mirror it into `src/api/contracts.ts`.
- If a field is benchmark-only or provider-facing, keep it out of product UI contracts.
- Public transcript history is available at `GET /play/sessions/{session_id}/history`.
