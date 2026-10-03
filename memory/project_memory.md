# Travel Planner Project Memory

## Project layout

- `backend/`: Python + FastAPI application, specialist agents, orchestration, database models, and API routes.
- `frontend/`: React + TypeScript UI. `src/App.tsx` contains the request form, Plan Builder, normalized final response, and Final Plan screen. `src/index.css` contains the dark theme and print styles.
- `docker-compose.yml`: local service configuration.

## Local development

- Backend (from `backend/`): `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- Frontend: `frontend/launch-ui.ps1 -Port 5173` (from `frontend/`). This bundles with esbuild and copies `src/index.css` into `dist/app.css`.
- API docs: `http://127.0.0.1:8000/docs`
- UI: `http://127.0.0.1:5173/`
- Frontend type check: `npx tsc -b` (from `frontend/`). Vite's standard build may fail in restricted environments with esbuild `spawn EPERM`; the project launcher avoids that path.

## Product behavior and data quality

- `buildFinalResponse()` in `frontend/src/App.tsx` is the normalized output source for the results UI and JSON.
- Plan selection is stateful: selected transport, hotel, itinerary, and extras drive the Final Plan.
- Unknown costs must remain `null`/Pending quote. Do not present an empty cost breakdown as INR 0.
- OpenStreetMap hotel results are location candidates, not verified inventory, ratings, category, availability, price, or cancellation terms.
- The current transport agent does not have live fares or schedules. Train options explicitly mark missing train numbers, stations, timetable, availability, and fares; the UI links to IRCTC for manual checking.
- Hotel cards link to a date/party-filtered Booking.com search. This is a manual supplier search and does not update the app's quote totals.
- Automated hotel rates require approved supplier API access. Booking.com Demand API access requires partner onboarding. IRCTC data access is not a free open fare API. Public Indian train timetable data found during research is stale and must not be treated as current fare/schedule data.
- Do not fabricate live fares, hotel rates, availability, or cancellation policies.

## UI result expectations

- Results show transport and hotel choices, recommended defaults, itinerary grouped by day, airport-distance warnings, and pending quote chips.
- Final Plan is read-only and includes the chosen plan, pending/open items, print, and JSON controls.
- Keep the existing dark theme and keep new work scoped to relevant UI/provider modules.
