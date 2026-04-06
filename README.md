# 🛒 E-commerce Order Operations Agent

A deterministic, stateful backend agent for handling order lookup, cancellations, and refunds — with strict guardrails, JWT authentication, Redis-backed state, centralized logging, and an LLM fallback router.

---

## Table of Contents

- [Demo](#demo)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Agent Workflow](#agent-workflow)
- [Guardrails & Safety Design](#guardrails--safety-design)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Run Instructions](#setup--run-instructions)
- [Environment Variables](#environment-variables)
- [API Endpoints](#api-endpoints)
- [Test Users & Seed Data](#test-users--seed-data)
- [Authentication](#authentication)
- [Rate Limiting](#rate-limiting)
- [Testing](#testing)
- [Design Decisions](#design-decisions)
- [Limitations & Future Improvements](#limitations--future-improvements)

---

## Demo

**Login then send a message:**
```json
POST /agent/chat
Authorization: Bearer <token>

{
  "user_id": "user_1",
  "message": "Cancel my order ORD-2001"
}
```

**Response:**
```json
{
  "response": "You're about to cancel order ORD-2001.\n\nReply 'yes' to confirm or 'no' to keep the order.",
  "success": true,
  "intent": "cancel_order",
  "workflow_state": "awaiting_confirmation",
  "action_result": "pending_confirmation",
  "state_before": { "pending_intent": null, "order_id": null, "awaiting_confirmation": false },
  "state_after":  { "pending_intent": "cancel_order", "order_id": "ORD-2001", "awaiting_confirmation": true }
}
```

---

## Features

- 🔍 Order lookup by ID
- ❌ Cancellation flow with explicit confirmation step
- 💰 Refund request flow with slot-filling (order ID + reason)
- 🔄 Stateful multi-turn interactions via Redis (in-memory fallback)
- 🧠 Conversational order memory — agent remembers the last mentioned order across turns
- 🛡️ Strict guardrails preventing invalid operations
- ⚙️ Deterministic execution — LLM is used for extraction only, never action execution
- 🤖 LLM fallback router (OpenAI) for natural language not matched by rules
- 📝 Order ID normalisation — accepts `ORD-2001`, `ORD_2001`, `ORD 2001`, `ORD2001`
- 🔐 JWT authentication with bcrypt password hashing
- 🚦 Rate limiting on agent and auth endpoints
- 📊 Structured logging across all modules with consistent `KEY=value` format
- 🖥️ Built-in test console frontend (login screen + chat UI + live order status updates)
- ✅ Comprehensive test coverage using pytest

---

## System Architecture

| Layer | Responsibility |
|-------|---------------|
| **Router** | Rule-based intent + entity extraction with order ID normalisation. Falls back to LLM (OpenAI) for unmatched input. |
| **Agent** | Orchestrates workflow, manages state transitions, resolves conversational context, applies guardrails, calls tools. |
| **Tools** | Encapsulate business logic, interact with the database, return structured results. |
| **State Layer** | Redis-backed per-user workflow state with automatic in-memory fallback. Persists `last_mentioned_order_id` across workflow resets. |
| **Auth Layer** | JWT bearer tokens, bcrypt password hashing, users stored as flat environment variable pairs. |
| **API Layer** | FastAPI endpoints with rate limiting and authentication dependencies. |
| **Frontend** | Single-file HTML/JS test console with login screen, chat UI, live order status updates, and seed order reference panel. |

---

## Agent Workflow

```
1.  Receive message and user_id
2.  Load or initialize user state (Redis → memory fallback)
3.  Check if awaiting confirmation
4.  Check if pending slot-filling (refund or cancel)
5.  Route intent via rule-based router
        └─ if unknown → LLM fallback router (OpenAI)
6.  Resolve order ID (message → last_mentioned_order_id fallback)
7.  Validate required fields (slot filling)
8.  Apply guardrails
9.  Execute tool (if valid)
10. Save state (Redis)
11. Return structured response with metadata
```

---

## Guardrails & Safety Design

All actions are validated before execution. Guardrails are enforced in the service layer, exposed via `guardrail_triggered`, and never bypassed by the agent.

**Cancellation restrictions:**
- Cannot cancel shipped orders
- Cannot cancel delivered orders
- Cannot cancel already cancelled or refunded orders

**Refund restrictions:**
- Only delivered orders are eligible
- Refund reason is required
- Duplicate refunds are prevented

---

## Tech Stack

- **FastAPI** — API framework
- **PostgreSQL / SQLite** — Database (SQLite for local, configurable via env)
- **SQLAlchemy** — ORM
- **Redis** — State persistence (falls back to in-memory if unavailable)
- **OpenAI** — LLM fallback router (`gpt-4o-mini`)
- **python-jose** — JWT encoding/decoding
- **bcrypt** — Password hashing
- **slowapi** — Rate limiting
- **Docker** — Containerization
- **pytest** — Testing

---

## Project Structure

```
app/
├── agent/
│   ├── agent.py         # workflow orchestration + conversational memory
│   ├── router.py        # rule-based intent + entity extraction + order ID normalisation
│   ├── state.py         # Redis-backed state management
│   └── schemas.py       # request/response models
├── api/
│   ├── auth_routes.py   # POST /auth/login
│   ├── dependencies.py  # JWT auth FastAPI dependency
│   └── routes.py        # all other API endpoints
├── services/
│   └── order_service.py # business logic + guardrails
├── tools/
│   ├── orders.py        # tool wrappers
│   └── validators.py
├── utils/
│   ├── auth.py          # JWT creation, validation, password hashing
│   ├── config.py        # settings (pydantic-settings, reads .env)
│   ├── limiter.py       # slowapi rate limiter instance
│   ├── llm_router.py    # OpenAI fallback intent extraction
│   └── logger.py        # shared structured logger
├── db/
│   ├── database.py      # DB setup
│   ├── models.py        # Order, RefundRequest models
│   └── seed.py          # seed data (auto-runs on startup if DB is empty)
├── frontend/
│   └── index.html       # test console (login + chat UI)
├── main.py              # app entrypoint, lifespan, middleware
scripts/
└── generate_auth_users.py  # bcrypt hash generator for env var credentials
```

---

## Setup & Run Instructions

### Using Docker

```bash
docker-compose up --build
```

### Local Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Start Redis (required for state persistence)
redis-server

# Copy and fill in environment variables
cp .env.example .env

# Run
uvicorn app.main:app --reload
```

The database is seeded automatically on first startup if empty.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the values:

```env
# Database
DATABASE_URL=sqlite:///./orders.db

# Redis
REDIS_URL=redis://localhost:6379
STATE_TTL=3600

# Auth — stored as flat env vars to avoid $ mangling on deployment platforms
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=480
AUTH_USER_1=user_1
AUTH_PASS_1=$2b$12$...
AUTH_USER_2=user_2
AUTH_PASS_2=$2b$12$...

# OpenAI (optional — only needed for LLM fallback router)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
ROUTER_TIMEOUT=5
ROUTER_TEMPERATURE=0.0
```

### Generating credentials

Edit `scripts/generate_auth_users.py` with your usernames and plaintext passwords, then run:

```bash
python scripts/generate_auth_users.py
```

This outputs individual `AUTH_USER_N` / `AUTH_PASS_N` pairs ready to paste into your `.env` or set as deployment environment variables. Credentials are stored as flat pairs rather than a JSON blob to avoid `$` character mangling on platforms like Koyeb.

### Generating a SECRET_KEY

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## API Endpoints

### Public

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/auth/login` | Exchange credentials for JWT token |

### Protected (Bearer token required)

| Method | Path | Description | Rate limit |
|--------|------|-------------|------------|
| `POST` | `/agent/chat` | Send message to agent | 30/min |
| `POST` | `/agent/reset` | Reset user session state | — |
| `GET` | `/orders/{order_id}` | Look up an order | — |
| `POST` | `/orders/{order_id}/cancel` | Cancel an order | — |
| `POST` | `/orders/{order_id}/refund` | Request a refund | — |

---

## Test Users & Seed Data

The database is seeded automatically on first startup. Each test user has 3 orders covering different flows:

| User | Order | Status | Tests |
|------|-------|--------|-------|
| user_1 | ORD-2001 | pending | Cancel flow, lookup |
| user_1 | ORD-2002 | shipped | Cancel guardrail |
| user_1 | ORD-2005 | delivered | Refund success |
| user_2 | ORD-2003 | delivered | Refund success |
| user_2 | ORD-2006 | pending | Cancel flow |
| user_2 | ORD-2007 | shipped | Cancel guardrail |
| user_3 | ORD-2004 | cancelled | Cancel + refund guardrail |
| user_3 | ORD-2008 | pending | Cancel flow |
| user_3 | ORD-2009 | delivered | Refund success |
| user_4 | ORD-2010 | pending | Cancel flow |
| user_4 | ORD-2011 | refunded | Duplicate refund guardrail |
| user_4 | ORD-2013 | delivered | Refund success |
| user_5 | ORD-2012 | pending | Cancel flow |
| user_5 | ORD-2014 | delivered | Refund success |
| user_5 | ORD-2015 | shipped | Cancel guardrail |

---

## Authentication

All agent and order endpoints require a valid JWT bearer token.

**Login:**
```json
POST /auth/login
{
  "username": "tester1",
  "password": "your-password"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

**Using the token:**
```
Authorization: Bearer eyJ...
```

Tokens expire after 8 hours. Users are defined via flat `AUTH_USER_N` / `AUTH_PASS_N` environment variable pairs — up to 5 users supported by default, extendable in `config.py`. Generate hashed credentials using the provided script.

---

## Rate Limiting

| Endpoint | Limit |
|----------|-------|
| `POST /auth/login` | 10 requests/minute per IP |
| `POST /agent/chat` | 30 requests/minute per IP |

Exceeding the limit returns HTTP `429 Too Many Requests`.

---

## Testing

```bash
pytest -q
```

Coverage includes agent workflows, tool logic, API endpoints, guardrails, and edge cases.

---

## Design Decisions

**Deterministic execution over AI autonomy**
LLMs are used only for intent and entity extraction. All business logic, guardrails, and state transitions run through controlled backend code. The LLM cannot trigger actions directly.

**Rule-based router with LLM fallback**
Common phrases are matched by fast, free keyword rules. The LLM (`gpt-4o-mini`) is only invoked when the rule-based router returns `unknown` — minimising latency and cost while handling natural language gracefully. Both routing paths pass their extracted order ID through the same normalisation function, ensuring canonical `ORD-XXXX` format regardless of what the user typed.

**Order ID normalisation**
`extract_order_id()` in `router.py` is the single normalisation point for the whole system. It accepts `ORD-2001`, `ORD_2001`, `ORD 2001`, and `ORD2001` (case-insensitive) and always returns `ORD-XXXX`. The LLM router imports and reuses this same function so both paths behave identically.

**Conversational order memory**
`WorkflowState` stores a `last_mentioned_order_id` field that persists across workflow resets. When a user says "cancel that" or "refund it" after a previous lookup, the agent resolves the order ID from context rather than prompting again. This field survives `clear_state()` deliberately — workflow state is reset after each action, but conversational context is not.

**Redis state with in-memory fallback**
Multi-turn conversations require persistent context. Redis handles this with a configurable TTL per session. If Redis is unavailable, the app falls back to in-memory state and logs a warning — no crash, no data loss for active sessions.

**Flat env var credentials**
User credentials are stored as individual `AUTH_USER_N` / `AUTH_PASS_N` pairs rather than a JSON blob. This avoids `$` character mangling that occurs when bcrypt hashes are embedded in JSON strings on deployment platforms such as Koyeb.

**Separation of concerns**
Routing, orchestration, business logic, and persistence are kept in separate layers. This makes the system testable, observable, and easy to extend without cross-layer side effects.

**Structured logging**
Every significant event — intent routing, tool calls, guardrail triggers, state transitions, Redis operations — is logged in a consistent `LAYER | user_id=X | key=value` format across all modules. `WARNING` is used for guardrail blocks and fallbacks; `INFO` for normal flow. Every log line includes `user_id` so concurrent sessions can be traced independently.

**Frontend order card updates**
After a successful cancel or refund, the sidebar order card status updates in-place with a brief highlight animation. The update only fires when `action_taken` is `cancel_order` or `request_refund` and `action_result` is `completed` — preventing lookup responses from incorrectly updating card status.

---

## Limitations & Future Improvements

**Current limitations:**
- No conversation history beyond workflow fields and last mentioned order
- Auth users are env-var based — no self-service registration
- No analytics or metrics dashboard

**Planned improvements:**
- Conversation history stored in Redis alongside workflow state
- Metrics dashboard (intent distribution, guardrail hit rate, LLM fallback rate)
- Expanded intents (`get_refund_status`, `update_address`, `contact_support`)
- Router improvement loop — promote frequent LLM-handled phrases to rule-based
- Persistent session logging to PostgreSQL for replay and audit