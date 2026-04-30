# Consulting Dashboard Frontend MVP

## Run locally (mock mode default)

1. Install dependencies:
   - `cd frontend`
   - `npm install`
2. Run the app:
   - `npm run dev`
3. Open:
   - `http://localhost:3000`

Mock mode is enabled by default via `NEXT_PUBLIC_USE_MOCK=true` fallback in `src/lib/api.ts`.

## Optional real backend integration

1. From project root install web adapter deps:
   - `pip install -r requirements-web.txt`
2. Start API server:
   - `uvicorn api_server:app --reload --port 8000`
3. In `frontend/.env.local` set:
   - `NEXT_PUBLIC_USE_MOCK=false`
   - `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
4. Restart Next dev server.

## Endpoint contract

- `POST /api/intake/chat`
  - Request: `{ session_id?: string, mode: "quick" | "guided" | "detailed", user_message: string }`
  - Response: `{ session_id, assistant_message, messages, structured_case_draft, missing_fields, readiness_score, can_run_analysis }`

- `POST /api/analyze-case`
  - Request: `{ mode, session_id }` or `{ mode, case: { ...canonical_fields } }`
  - Response: `{ founder_report: string, agents: { intake, finance, operations, strategy, review } }`

- `GET /api/agent-info`
  - Returns agent descriptions + orchestration steps for dashboard explainer panels.
