# Multi-Agent Travel Application

React + TypeScript frontend, FastAPI backend, PostgreSQL, and 12 specialized agents coordinated by an Orchestrator.

## What was wrong in the original agent files

See `docs/AGENT_ANALYSIS.md`. Short version:

- Travel Planner and Orchestrator both claimed to be the conductor — **Orchestrator runs the DAG**; Travel Planner is feasibility only.
- Airport radius was 20 / 30 / 150 km — **default 30 km**, overridable.
- Orchestrator costing invented credit-card discounts — **Finance Agent forbids that**.
- Dietitian prompt was a single Jain/Munnar trip — **generalized**.
- Goibibo / MakeMyTrip / Google Weather are **not configured public APIs**. The app uses OpenStreetMap and Open-Meteo for place/weather context, but leaves transport, hotel, guide, insurance, and retail prices unknown until a provider returns a current quote. It does not scrape booking sites or fill in fixed sample prices.
- The planner currently uses geocoding and an airport catalog, not an LLM. `OPENAI_API_KEY` is optional configuration only; no agent calls a model yet.
- Customer care has no standalone agent definition, so it is not registered.

The full input/output/dependency audit, conflict resolutions, corrected contracts, and live-production gaps are in `docs/AGENT_ANALYSIS.md`. The original source prompts are preserved. The corrected generalized Dietitian prompt is `docs/DietitianAgent.corrected.md`.

Current no-cost/live quote API options, required access, and provider gaps are listed in `docs/LIVE_DATA_OPTIONS.md`. The app currently has no quote-provider credentials configured, so exact rates and insurance terms remain dynamic/unknown rather than sample constants.

Origin and destination are live-searchable Indian city fields backed by the free countries.dev/GeoNames city endpoint. Suggestions are not a government-exhaustive register of every town or village; travelers can still type another place manually. The app keeps Ahmedabad → Munnar as the editable example route.

## Run with Docker

```bash
docker compose up --build
```

- UI: http://localhost:5173
- API: http://localhost:8000/docs
- Postgres: localhost:5432 (`travel` / `travel`)

Workflows persist agent attempts and results in PostgreSQL. `needs_input` ends before specialist execution; `needs_review` means the selected agents finished but a required audit could not verify a claim. A completed plan can still contain estimates, each of which carries its source/data status.

## Run locally

1. Set `DATABASE_URL` in `backend/.env` to your PostgreSQL host, port, database, user, and password. The database must exist; the API creates its application tables at startup. `backend/.env.example` shows the format.
2. Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

3. Frontend:

```bash
cd frontend
npm install
npm run dev
```

If Vite's esbuild worker cannot launch because child-process spawning is restricted, use `.\launch-ui.ps1`. It bundles directly with the installed esbuild executable and serves the UI on port 5173. Set `VITE_API_URL` before launching to point at another API URL.

4. Tests:

```bash
cd backend
pytest
```

The test command requires the dependencies in `backend/requirements.txt` to be installed. Live inventory, confirmed booking, exact schedules, verified hotel cancellation terms, and insurance quotes require provider credentials and are not supplied by the current agent files.

## Workflow

Validator (input) → Travel Planner → Weather → parallel Transportation / Hotel / Tour Guide → parallel Health / Dietitian / Document / Insurance → Fashion Designer → Finance → Validator (audit) → final plan.

Unused agents can be omitted with `trip.exclude_agents` or limited with `trip.include_agents`.

## Adding an agent

1. Implement `BaseAgent` in `backend/app/agents/`.
2. Register it in `registry.py`.
3. Add it to `PIPELINE` / `DEFAULT_AGENTS` in `orchestrator.py`.
