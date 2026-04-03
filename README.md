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
- 🛡️ Strict guardrails preventing invalid operations
- ⚙️ Deterministic execution — LLM is used for extraction only, never action execution
- 🤖 LLM fallback router (OpenAI) for natural language not matched by rules
- 🔐 JWT authentication with bcrypt password hashing
- 🚦 Rate limiting on agent and auth endpoints
- 📊 Structured logging across all modules
- 🖥️ Built-in test console frontend (login screen + chat UI)
- ✅ Full test coverage using pytest

---

## System Architecture

| Layer | Responsibility |
|-------|---------------|
| **Router** | Rule-based intent + entity extraction. Falls back to LLM (OpenAI) for unmatched input. |
| **Agent** | Orchestrates workflow, manages state transitions, applies guardrails, calls tools. |
| **Tools** | Encapsulate business logic, interact with the database, return structured results. |
| **State Layer** | Redis-backed per-user workflow state with automatic in-memory fallback. |
| **Auth Layer** | JWT bearer tokens, bcrypt password hashing, users stored in environment variables. |
| **API Layer** | FastAPI endpoints with rate limiting and authentication dependencies. |
| **Frontend** | Single-file HTML/JS test console with login screen, chat UI, and seed order reference panel. |

---

## Agent Workflow

```
1.  Receive message and user_id
2.  Load or initialize user state (Redis → memory fallback)
3.  Check if awaiting confirmation
4.  Route intent via rule-based router
        └─ if unknown → LLM fallback router (OpenAI)
5.  Validate required fields (slot filling)
6.  Apply guardrails
7.  Execute tool (if valid)
8.  Save state (Redis)
9.  Return structured response with metadata
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
│   ├── agent.py         # workflow orchestration
│   ├── router.py        # rule-based intent + entity extraction
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
└── generate_auth_users.py  # bcrypt hash generator for AUTH_USERS env var
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

# Auth
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=480
AUTH_USERS={"tester1":"$2b$12$...","tester2":"$2b$12$..."}

# OpenAI (optional — only needed for LLM fallback router)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
ROUTER_TIMEOUT=5
```

### Generating AUTH_USERS

Edit `scripts/generate_auth_users.py` with your usernames and plaintext passwords, then run:

```bash
python scripts/generate_auth_users.py
```

Copy the output value into your `.env` or deployment environment variables.

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

Tokens expire after 8 hours. Users are defined via the `AUTH_USERS` environment variable as a JSON object of `{username: bcrypt_hash}` pairs.

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
Common phrases are matched by fast, free keyword rules. The LLM (OpenAI `gpt-4o-mini`) is only called when the rule-based router returns `unknown` — minimising latency and cost while handling natural language gracefully.

**Redis state with in-memory fallback**
Multi-turn conversations require persistent context. Redis handles this with a 1-hour TTL per session. If Redis is unavailable, the app falls back to in-memory state and logs a warning — no crash, no data loss for active sessions.

**Separation of concerns**
Routing, orchestration, business logic, and persistence are kept in separate layers. This makes the system testable, observable, and easy to extend.

**Structured logging**
Every significant event — intent routing, tool calls, guardrail triggers, state transitions, Redis operations — is logged in a consistent `KEY=value` format, making logs grep-friendly and easy to pipe into external tooling.

---

## Limitations & Future Improvements

**Current limitations:**
- No conversation history — each message is stateless beyond the workflow fields
- Auth users are env-var based — no self-service registration
- Rule-based router relies on keyword matching and may miss edge cases
- No analytics or metrics dashboard

**Planned improvements:**
- Conversation history stored in Redis alongside workflow state
- Metrics dashboard (intent distribution, guardrail hit rate, LLM fallback rate)
- Expanded intents (`get_refund_status`, `update_address`, `contact_support`)
- Router improvement loop — promote frequent LLM-handled phrases to rule-based
- Persistent session logging to PostgreSQL for replay and audit