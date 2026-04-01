# 🛒 E-commerce Order Operations Agent

A deterministic, stateful backend agent for handling order lookup, cancellations, and refunds with strict guardrails.

---

## 📋 Table of Contents

- [Demo](#demo)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Agent Workflow](#agent-workflow)
- [Guardrails & Safety Design](#guardrails--safety-design)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Run Instructions](#setup--run-instructions)
- [API Endpoints](#api-endpoints)
- [Example Scenarios](#example-scenarios)
- [Testing](#testing)
- [Design Decisions](#design-decisions)
- [Limitations & Future Improvements](#limitations--future-improvements)

---

## Demo

**Request**
```json
POST /agent/chat
{
  "user_id": "user_1",
  "message": "Cancel my order ORD-1001"
}
```

**Response**
```json
{
  "response": "You're about to cancel order ORD-1001.\n\nReply 'yes' to confirm or 'no' to keep the order.",
  "success": true,
  "intent": "cancel_order",
  "workflow_state": "awaiting_confirmation",
  "action_result": "pending_confirmation",
  "state_before": {
    "pending_intent": null,
    "order_id": null,
    "reason": null,
    "awaiting_confirmation": false
  },
  "state_after": {
    "pending_intent": "cancel_order",
    "order_id": "ORD-1001",
    "reason": null,
    "awaiting_confirmation": true
  }
}
```

---

## Features

- 🔍 Order lookup by ID
- ❌ Cancellation flow with explicit confirmation step
- 💰 Refund request flow with slot-filling (order ID + reason)
- 🔄 Stateful multi-turn interactions
- 🛡️ Strict guardrails preventing invalid operations
- ⚙️ Deterministic execution (LLM does not execute actions)
- 📊 Structured workflow metadata for observability
- ✅ Full test coverage using pytest

---

## System Architecture

The system separates responsibilities into clearly defined layers:

| Layer | Responsibility |
|-------|---------------|
| **Router** | Extracts intent and entities from user input. Can be rule-based or LLM-assisted (extraction only). |
| **Agent** | Orchestrates workflow, manages state transitions, applies guardrails, calls tools. |
| **Tools** | Encapsulate business logic, interact with database, return structured results. |
| **State Layer** | Maintains per-user workflow state in memory to enable multi-turn conversations. |
| **API Layer** | FastAPI endpoints that handle the request/response lifecycle. |

---

## Agent Workflow

```
1. Receive message and user_id
2. Load or initialize user state
3. Check if awaiting confirmation
4. Route intent and extract entities
5. Validate required fields
6. Apply guardrails
7. Execute tool (if valid)
8. Update state
9. Return response with metadata
```

---

## Guardrails & Safety Design

All actions are validated before execution:

**Cancellation restrictions:**
- Cannot cancel shipped orders
- Cannot cancel delivered orders
- Cannot cancel already cancelled orders

**Refund restrictions:**
- Only delivered orders are eligible
- Refund reason is required
- Duplicate refunds are prevented

Guardrails are:
- ✅ Enforced in the service layer
- ✅ Exposed via `guardrail_triggered`
- ✅ Never bypassed by the agent

---

## Tech Stack

- **FastAPI** — API framework
- **PostgreSQL** — Database
- **SQLAlchemy** — ORM
- **Docker** — Containerization
- **pytest** — Testing

---

## Project Structure

```
app/
├── agent/
│   ├── agent.py         # workflow orchestration
│   ├── router.py        # intent + entity extraction
│   ├── state.py         # in-memory state management
│   ├── schemas.py      # request/response models
├── └──api/
│       └── routes.py        # FastAPI endpoints
├── services/
│   └── order_service.py # business logic
├── tools/
│   ├── orders.py        # tool wrappers
│   └── validators.py
├── utils/
│   ├── config.py     
│   └── logger.py
├── db/
│   ├── database.py      # DB setup
│   ├── models.py
│   └── seed.py          # seed data
├── main.py
├── orders.db
├── README.md
└── requirements.txt

```

---

## Setup & Run Instructions

### Using Docker

```bash
docker-compose up --build
```

### Local Setup

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

---

## API Endpoints

### `POST /agent/chat`

Processes user messages through the agent.

**Request**
```json
{
  "user_id": "user_1",
  "message": "ORD-1002"
}
```

**Response**
```json
{
  "response": "Order ORD-1002 is currently shipped.",
  "success": true
}
```

---

## Example Scenarios

### 🔍 Order Lookup
```
User: ORD-1002
→ Returns order status
```

### ❌ Cancel Flow
```
User: Cancel my order ORD-1001
→ Confirmation requested

User: yes
→ Order cancelled
```

### 💰 Refund Flow (Slot Filling)
```
User: I want a refund
→ Asks for order ID

User: ORD-1003
→ Asks for reason

User: It arrived damaged
→ Refund processed
```

### 🛡️ Guardrail Trigger
```
User: Cancel my order ORD-1002 (shipped)
→ Blocked with explanation
```

---

## Testing

```bash
pytest -q
```

Coverage includes:
- Agent workflows
- Tool logic
- API endpoints
- Guardrails and edge cases

---

## Design Decisions

### Deterministic execution over AI autonomy
LLMs are used only for intent/entity extraction. All actions are executed through controlled backend logic.

### Stateful workflow
Multi-turn interactions require persistent context, implemented using in-memory state per user.

### Separation of concerns
- **Routing** handles intent
- **Agent** handles workflow
- **Tools** handle business logic

This keeps the system testable and maintainable.

### Structured metadata
Each response includes intent, workflow state, state transitions, and action outcome for debugging and observability.

---

## Limitations & Future Improvements

**Current limitations:**
- In-memory state is not persistent
- No authentication layer
- Limited natural language flexibility
- Logging not yet centralized

**Planned improvements:**
- Redis-backed state
- LLM fallback router
- Analytics on workflow performance
- Persistent logging system

---

## Why This Project Matters

This project demonstrates:

- 🏗️ Backend system design for real-world workflows
- 🤖 Safe integration of AI into deterministic systems
- 🔄 Multi-step user interaction handling
- 🛡️ Enforcement of business rules through guardrails
- 🏭 Production-oriented thinking (testing, logging, structure)

> The focus is on **reliability, control, and correctness** — not AI novelty.