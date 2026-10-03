# Agent analysis, corrections, and workflow map

This document records what was in the original `.md` agent files, what conflicted or was missing, and the **canonical contracts** the application implements.

## 1. Agent inventory

| Canonical ID | Source file | Purpose |
|---|---|---|
| `orchestrator` | `ORCHESTRATOR 1.md` + `travelplanneragent 4.md` | Conducts workflow; does not own domain search |
| `validator` | Specified inside `ORCHESTRATOR 1.md` (no standalone file) | Input sanitization + cross-agent audit |
| `travel_planner` | `travelplanneragent 4.md` | Feasibility, corridor, itinerary synthesis inputs |
| `weather` | `weatheragent.md` | Forecast / climate baseline |
| `transportation` | `transportationagent.md` | Flights, trains, buses, transfers, 30 km airport rule |
| `hotel` | `hotel-agent.md` | Stay search, rooms, cancellation, Jain food flag |
| `tour_guide` | `Tour Guide Agent 1 1.md` | Sightseeing, guides, activity fees |
| `fashion_designer` | `FashionDesignerAgent.md` | Clothing, packing, colour/fit |
| `document` | `Document agent requirement and prompt.md` | Travel document checklist (not a DMS) |
| `health` | `health_agent.md` | Non-diagnostic travel health plan |
| `dietitian` | `DietitiansAgent.md` | Meal plan from food preference |
| `insurance` | `travel_insurance.md` | Coverage comparison (no invented policies) |
| `finance` | `finance_agent.md` | Costing, budget, cancellation exposure, payment plan |

Not implemented as agents (mentioned in `Requirement.txt` only, no spec): **customer care**. Vehicle rental is handled inside **transportation**.

## 2. Conflicts resolved (canonical rules)

| Topic | Conflicting sources | Canonical rule |
|---|---|---|
| Who orchestrates | Travel Planner claims to be orchestrator; Orchestrator file also does | **Orchestrator** runs the DAG. **Travel Planner** is a specialist for feasibility + day-wise itinerary skeleton. |
| Airport distance | 20 km (Dietitian notes), 30 km (Orchestrator), 150 km (Travel Planner) | Default **`max_airport_distance_km = 30`**, overridable on the request. |
| Room occupancy | Orchestrator “strictly 2”; Hotel Agent uses hotel occupancy rules | Default occupancy **2**; rooms = `ceil(total / occupancy)` unless hotel occupancy rules differ. |
| Offers / discounts | Orchestrator Costing invents CC 10%/12% discounts; Finance forbids invented offers | **Finance Agent wins**: apply discounts only if `verified == true`. No hardcoded bank offers. |
| Health vaccinations | Orchestrator lists vaccines; Health Agent forbids prescribing | **Health Agent wins**: no diagnosis, no prescriptions, no invented hospital phone numbers. |
| Dietitian scope | File is a one-trip Jain/Munnar prompt | Generalized: any destination/dates; food preference drives rules; Jain is a strict subset of veg. |
| Weather file | Build prompt for LangChain, not an RTCCO agent | Implemented as a first-class agent with Open-Meteo + climate fallback. |
| Document Agent | Generic document CRM vs travel ID checklist | Trip **checklist + classification** (mandatory / recommended / if_applicable). No fabricated visa law. |
| Live booking APIs | Goibibo, MakeMyTrip, BookMyShow, Google Weather | **No provider is configured.** Use geocoding + Open-Meteo + OSM POI for context only; price, schedule, availability, and cancellation fields stay unknown until a provider quote exists. Never scrape booking sites. |
| Child ages | Required by Dietitian/Finance/Requirement; optional in Hotel | **Required when `children > 0`**. Validator returns `needs_input`. |
| Food vs Dietitian | Health mentions a Food Agent | **Dietitian Agent** owns meals. No separate Food Agent. |

## 3. Canonical workflow

```
User request
    → Orchestrator
    → Validator (Stage 0: input)
    → Parallel: Travel Planner + Weather
    → Feasibility gate (stop if trip impossible)
    → Parallel logistics: Transportation + Hotel + Tour Guide
    → Parallel advisory: Health + Dietitian + Document + Insurance
    → Sequential: Fashion Designer (needs weather + tour + health)
    → Sequential: Finance (needs transport + hotel + tour + insurance + optional fashion costs)
    → Validator (Stage 5: cross-agent + finance audit)
    → Orchestrator combine → Final travel plan
```

Unused agents are skipped (example: skip `transportation` flight search if mode is `car` only; skip `dietitian` only if user explicitly opts out).

Retry: each agent up to **2 retries** on transport/tool failure, then continue with `PARTIAL` unless the agent is on the feasibility-critical path (`travel_planner`).

## 4. Shared request contract

```json
{
  "origin": "Ahmedabad",
  "destination": "Munnar",
  "adults": 12,
  "children": 2,
  "child_ages": [6, 9],
  "travel_mode": "flight",
  "start_date": "2026-11-08",
  "end_date": "2026-11-15",
  "hotel_category": "5 Star",
  "room_occupancy": 2,
  "food_preference": "Jain",
  "payment_method": "Credit Card",
  "hotel_cancellation_required": true,
  "max_airport_distance_km": 30,
  "budget_min": 300000,
  "budget_max": 500000,
  "currency": "INR"
}
```

Derived: `total_travelers`, `duration_days`, `duration_nights`, `required_rooms`.

## 5. Still missing from original specs (handled in code)

1. Unified Pydantic schemas across agents (each file used different key names).
2. Standalone Validator Agent file.
3. Auth / user model (added minimal users table).
4. Provider credentials for Goibibo / MMT / Google Weather (not available).
5. Child ages in Dietitian source prompt (now required).
6. Customer-care agent (omitted).

## 6. Canonical agent contracts

These contracts resolve the source prompts into the interfaces used by the application. They are the corrected versions to use when adding providers or replacing an adapter.

| Agent | Inputs | Output | Dependencies / tools | Canonical correction |
|---|---|---|---|---|
| Validator | Trip request; then selected agent envelopes | Input decision; final reconciliation | Pydantic request schema; deterministic arithmetic/policy checks | Must gate the workflow before any specialist starts. An unverified claim cannot pass as verified. |
| Travel Planner | Origin, destination, mode, dates, airport limit | Feasibility, coordinates, distance, itinerary skeleton | Nominatim geocoder; airport catalog | Resolves places with geospatial data. No configured LLM or border-status source; do not claim geopolitical verification. |
| Weather | Planner coordinates and dates | Daily forecast or explicitly labeled seasonal archive | Open-Meteo forecast/archive | Google Weather is not configured. Archive data is historical context, not a forecast. |
| Transportation | Trip and resolved route | Airport, transfer distance, and mode candidates | Airport catalog; meal-code helper | No live flight, rail, bus, rental, schedule, fare, cancellation, or booking API. Never invent flight numbers, fares, timestamps, or availability. |
| Hotel | Trip, dates, occupancy and cancellation requirement | Candidate POIs, room math, unknown price/policy status | OpenStreetMap POIs | POIs do not prove star rating, inventory, price, Jain food, or cancellation. Those fields stay unknown until a hotel provider confirms them. |
| Tour Guide | Trip, weather, destination | Attractions and weather notes; price/capacity unknown | Local attraction catalog; OSM POIs | No licensed-guide or ticket inventory API. Do not create fixed guide rates or claim availability. |
| Health | Trip, weather, activities | General precautions, health flags and kit checklist | Specialist outputs; static guidance | No diagnosis, prescription, vaccine mandate, or invented emergency contact. |
| Dietitian | Trip, child ages, food preference, optional weather | Day-wise adult/child meal outline and meal code | Jain rule checker and meal helpers | Generalize the trip-specific prompt. Allergy and restaurant-menu confirmation are missing; never claim a restaurant dish is Jain-verified. See [DietitianAgent.corrected.md](DietitianAgent.corrected.md). |
| Document | Trip and traveler split | Mandatory/recommended/conditional checklist | Static checklist rules | This is a checklist, not a document store or visa-law service. Nationality and official jurisdiction data are required for visa determinations. |
| Insurance | Dates and travelers | No quote until provider configured | None | No insurer quote or underwriting API. Do not invent provider names, coverage or premiums. |
| Fashion Designer | Weather, activities, health flags, party | Day-wise clothing and packing; prices unknown | Weather/tour/health envelopes | Missing body/colour profiles are optional; use neutral fit guidance and disclose assumptions. Never infer body type or invent retail prices. |
| Finance | Trip and transport/hotel/tour/insurance/style outputs | Sums verified quotes dynamically; otherwise returns a known subtotal and null grand total | Deterministic calculator | Discounts only with a verifiable offer source. A missing quote is never treated as zero or a confirmed price. |

## 7. Corrected execution and trust rules

1. **Validate → resolve route → weather → logistics in parallel → advisory in parallel → style → finance → audit → synthesize.** A stage may consume only completed outputs from its declared dependencies.
2. Input validation that returns `needs_input` ends the run before specialist execution. A failed specialist is retried twice after the first attempt; persistent failures are recorded and downstream agents receive an absent/failed dependency instead of fabricated data.
3. Each parallel execution writes through its own database session. Results are passed as validated `AgentEnvelope` values and recorded with the request/context snapshot used for that run.
4. `completed` means the workflow finished its selected stages. `needs_review` means the final required audit did not approve the plan. Estimate-only data is never presented as a confirmed booking.
5. Agents omitted by `include_agents` or listed in `exclude_agents` do not execute, except the input validator and feasibility planner, which remain required. Unknown agent IDs are rejected by request validation.
6. The source specs request a customer-care agent, live booking/hotel/guide/insurance APIs, and LLM validation/resolution. There is no customer-care `.md` specification and no provider credentials or contracts in the supplied files. The current application therefore omits customer care and reports live inventory as unavailable or estimated; it does not claim these integrations are complete.

## 8. Implementation limits to resolve for live production

- Add credentials and provider contracts for live transport, hotel, guide, rental, insurance, offers, and booking/cancellation status.
- If model-based place interpretation is a hard requirement, configure an LLM provider and define a validated, auditable output contract. The current planner uses geocoding and an airport catalog, not an LLM.
- Add authentication/authorization before exposing user-linked requests. The `users` table currently provides a minimal guest identity only.
- Move workflow dispatch from in-process `asyncio.create_task` to a durable job queue for restart-safe execution.
- Add database migrations and integration coverage against PostgreSQL. The current schema is created at API startup for local development.
