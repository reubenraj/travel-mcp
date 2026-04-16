# Agentic Travel Recommendations API

An AI-powered travel concierge service built with FastAPI, Claude AI, and MCP (Model Context Protocol). The service enforces partner-specific business rules before generating personalised travel recommendations — meaning each partner brand controls what the AI can and cannot recommend to their members.

Built as a technical challenge submission for arrivia / Provn.

---

## What it does

- A member asks for travel recommendations through a chat interface
- The recommendation service fetches member context and partner rules, enforces category exclusions and caps deterministically, then passes the filtered results to the Claude agent
- Claude calls three MCP tools in sequence — independently discovering member profile, partner rules, and the pre-filtered recommendations
- Claude generates a personalised response using only the rule-compliant offers

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop) installed and running
- An [Anthropic API key](https://console.anthropic.com)

That's it. No Python installation required.

---

## Getting started

**1. Clone the repository**

```bash
git clone https://github.com/reubenraj/travel-mcp.git
cd travel-mcp
```

**2. Set up your environment file**

```bash
cp .env.example .env
```

Open `.env` and replace `your_api_key_here` with your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
MEMBER_SERVICE_URL=http://localhost:8001
PARTNER_SERVICE_URL=http://localhost:8002
```

**3. Start all services**

```bash
docker compose up --build
```

This will:
- Pull the Python base image (first run only, ~2 minutes)
- Install all dependencies
- Seed the SQLite database with mock data
- Start all four containers in the correct order

**4. Open the app**

Once you see all four services print `Application startup complete`, open your browser:

```
http://localhost:8501
```

---

## Service URLs

| Service | URL | Description |
|---|---|---|
| Chat UI | http://localhost:8501 | Streamlit chat interface |
| Recommendation API | http://localhost:8000 | Main FastAPI service |
| Recommendation API docs | http://localhost:8000/docs | Interactive Swagger UI |
| Member service | http://localhost:8001 | Mock member data API |
| Member service docs | http://localhost:8001/docs | Interactive Swagger UI |
| Partner service | http://localhost:8002 | Mock partner config API |
| Partner service docs | http://localhost:8002/docs | Interactive Swagger UI |

---

## Useful commands

**Stop all containers**
```bash
docker compose down
```

**Stop and reset the database (full clean start)**
```bash
docker compose down -v
docker compose up --build
```

**View live logs from all containers**
```bash
docker compose logs -f
```

**View logs from a specific service**
```bash
docker compose logs -f api
docker compose logs -f ui
docker compose logs -f member-service
docker compose logs -f partner-service
```

**Rebuild after code changes**
```bash
docker compose up --build
```

---

## Testing the partner rules

The demo is most useful when you switch between members from different partners. Use the member dropdown in the sidebar:

| Member | Partner | Rules |
|---|---|---|
| Alice Johnson (MBR001) | GlobalBank Rewards | Unlimited, no exclusions |
| Bob Martinez (MBR002) | GlobalBank Rewards | Unlimited, no exclusions |
| Carol Williams (MBR003) | PremiumCard Travel | Capped at 3 recommendations |
| David Chen (MBR004) | PremiumCard Travel | Capped at 3 recommendations |
| Eva Rosario (MBR005) | FamilyFirst Points | Capped at 5, cruises excluded |
| Frank Okafor (MBR006) | FamilyFirst Points | Capped at 5, cruises excluded |

Ask any member: `"What travel options do you recommend for me?"`

Watch the **Rules enforcement log** in the sidebar — for Eva and Frank you will see cruise recommendations removed before Claude responds. For Bob and Alice, cruises appear freely.

---

## Project structure

```
travel-mcp/
│
├── main.py                     # Main recommendation API (port 8000)
├── agent.py                    # Claude agentic loop
├── mcp_server.py               # MCP tool definitions
├── rules_engine.py             # Partner rule enforcement logic
├── app.py                      # Streamlit chat UI (port 8501)
│
├── services/
│   ├── mock_member_service.py  # Mock member data API (port 8001)
│   ├── mock_partner_service.py # Mock partner config API (port 8002)
│   └── __init__.py
│
├── db/
│   ├── seed.py                 # Creates and seeds the SQLite database
│   └── __init__.py
│
├── Dockerfile.api              # Shared image for all backend services
├── Dockerfile.ui               # Streamlit container image
├── docker-compose.yml          # Orchestrates all four containers
├── .dockerignore               # Excludes venv, .env, __pycache__ from image
├── .env.example                # Environment variable template
└── requirements.txt            # Python dependencies
```

---

## File descriptions

### `main.py`
The orchestration layer. Receives `POST /recommend` requests, calls the member and partner services via HTTP, runs the rules engine, then calls the Claude agent. Returns a structured response including the AI reply, filtered recommendations, enforcement log, and tools called.

### `agent.py`
The Claude agentic loop. Sends the member's message to Claude along with the three MCP tool definitions. Executes tool calls as Claude requests them, feeds results back into the conversation, and loops until Claude reaches `end_turn`. Claude decides the call order — the loop does not hardcode any sequencing.

### `mcp_server.py`
Defines three MCP tools with typed input schemas:
- `get_member_profile` — fetches member name, loyalty tier, partner ID, and last 5 bookings
- `get_partner_rules` — fetches recommendation cap and excluded categories for a partner
- `get_recommendations` — runs the full pipeline and returns rule-enforced recommendations

### `rules_engine.py`
Pure Python module with no web framework dependencies. Applies rules in this order:
1. Category exclusion — removes any recommendation in an excluded category
2. Recommendation cap — truncates results to the partner's cap limit

Order matters: exclusions run before the cap so excluded categories cannot consume cap slots. Returns an `enforcement_log` list that documents every decision made.

### `app.py`
Streamlit chat interface. Fetches the member list dynamically from the member service (cached 60 seconds). Shows member card, tools called, and enforcement log in the sidebar. Sends messages to `POST /recommend` and displays the AI response in a chat layout.

### `services/mock_member_service.py`
Standalone FastAPI app on port 8001. Simulates arrivia's internal member data service. Exposes `GET /members/{member_id}` returning member profile and last 5 travel bookings from SQLite.

### `services/mock_partner_service.py`
Standalone FastAPI app on port 8002. Simulates arrivia's internal partner config service. Exposes `GET /partners/{partner_id}` returning recommendation cap and excluded categories. Read-only — never modified by the recommendation service.

### `db/seed.py`
Creates the SQLite database and seeds it with test data. Runs automatically during Docker build. Can be re-run manually to reset the database. Creates four tables: `partners`, `members`, `travel_history`, and `recommendations`.

---

## Database

The app uses SQLite (`db/travel.db`) stored in a Docker named volume so data persists across container restarts.

### Tables

**`partners`** — stores partner configuration rules

| Column | Type | Description |
|---|---|---|
| partner_id | TEXT | Primary key (e.g. PARTNER_A) |
| name | TEXT | Display name |
| rec_cap | INTEGER | Max recommendations (NULL = unlimited) |
| excluded_cats | TEXT | JSON array of excluded categories |

**`members`** — stores member profiles, each belonging to one partner

| Column | Type | Description |
|---|---|---|
| member_id | TEXT | Primary key (e.g. MBR001) |
| name | TEXT | Full name |
| loyalty_tier | TEXT | Silver, Gold, or Platinum |
| partner_id | TEXT | Foreign key to partners |

**`travel_history`** — stores last 5 bookings per member, used for personalisation

| Column | Type | Description |
|---|---|---|
| id | INTEGER | Auto-increment primary key |
| member_id | TEXT | Foreign key to members |
| destination | TEXT | City or region |
| booking_type | TEXT | flight, hotel, cruise, or car |
| travel_date | TEXT | ISO date string |

**`recommendations`** — the full catalog of available travel offers

| Column | Type | Description |
|---|---|---|
| rec_id | INTEGER | Auto-increment primary key |
| destination | TEXT | City or region |
| category | TEXT | flight, hotel, cruise, or car |
| description | TEXT | Offer description |
| base_price | INTEGER | Starting price in USD |

---

## Architecture

```
Browser
  └── Streamlit UI (8501)
        └── POST /recommend
              └── Recommendation API (8000)
                    ├── GET /members/{id}  →  Member service (8001)
                    ├── GET /partners/{id} →  Partner service (8002)
                    ├── rules_engine.py    →  enforce exclusions + cap
                    └── agent.py           →  Claude + MCP tools
                                                └── SQLite (travel.db)
```

All four services run as Docker containers orchestrated by `docker-compose.yml`. The three backend containers share a single named volume (`sqlite-data`) so they all read from the same database file.

---

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key | Required |
| `MEMBER_SERVICE_URL` | Member service base URL | `http://localhost:8001` |
| `PARTNER_SERVICE_URL` | Partner service base URL | `http://localhost:8002` |
| `API_URL` | Recommendation API base URL | `http://localhost:8000` |

Inside Docker, `localhost` URLs are automatically overridden by `docker-compose.yml` to use container service names (`http://member-service:8001` etc.).

---

## Tech stack

| Layer | Technology |
|---|---|
| AI model | Claude (Anthropic API) |
| Agent protocol | MCP (Model Context Protocol) |
| Backend API | FastAPI + Uvicorn |
| Chat UI | Streamlit |
| Database | SQLite |
| HTTP client | httpx |
| Data validation | Pydantic |
| Containerisation | Docker + Docker Compose |
