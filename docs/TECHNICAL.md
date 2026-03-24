# SHS Appliance Diagnostic Agent — Technical Design Document

## Overview

This document describes the internal architecture, design decisions, data flows, and development conventions for the SHS Appliance Diagnostic Agent. It is intended for engineers working on or extending the system.

---

## System Architecture

The system is a three-tier AI voice agent:

```
PSTN / Phone
     │
     ▼
  Twilio  ─── HTTP webhook ──▶  POST /voice/incoming
     │                                │
     │                         Creates session in DB
     │                                │
     └──── Media Streams WS ──▶  WS /voice/stream
                                      │
                          ┌───────────▼───────────────┐
                          │   WhisperSTTClient         │
                          │   (buffers μ-law audio)    │
                          │   transcribes via Whisper  │
                          └───────────┬───────────────┘
                                      │ on_transcript(text)
                          ┌───────────▼───────────────┐
                          │   run_agent()              │
                          │   GPT-4o + function calls  │
                          └──┬────────────────────┬───┘
                             │                    │
                    ┌────────▼───────┐   ┌────────▼────────┐
                    │ DiagnosticsService│ │SchedulingService│
                    │ (RAG)          │   │ (DB + bookings) │
                    └────────┬───────┘   └────────┬────────┘
                             │                    │
                    ┌────────▼────────────────────▼────────┐
                    │    Repositories (async SQLAlchemy)    │
                    └───────────────────┬──────────────────┘
                                        │
               ┌────────────────────────▼─────────────────┐
               │   PostgreSQL 16 + pgvector               │  Redis 7
               │   knowledge_chunks, sessions,            │  (session buffer,
               │   technicians, availability_slots,       │   image_ready key)
               │   appointments                           │
               └──────────────────────────────────────────┘
```

---

## Directory Structure

```
app/
  api/
    chat.py            # run_agent() — the core agentic loop
    httpserver.py      # FastAPI app factory, router registration
    mcpserver.py       # FastMCP server exposing tools to external agents
    request_context.py # AsyncContextVar for per-request DB session
  db/
    database.py        # SQLAlchemy async engine + session factory
    mixins.py          # TimestampMixin (created_at, updated_at)
    models/            # SQLAlchemy ORM models
  entities/
    api_entities/      # Pydantic request/response schemas (FastAPI)
    service_entities/  # Pydantic internal service models (SessionData, etc.)
  middleware/
    request_response_logger_middleware.py  # structlog request logging
  prompts/
    __init__.py        # SYSTEM_PROMPT + build_system_prompt()
  repositories/        # One file per DB table; thin async query layer
  routes/
    sessions.py        # POST/PUT /api/v1/sessions
    technicians.py     # CRUD /api/v1/technicians
    twilio.py          # POST /voice/incoming, WS /voice/stream
    media.py           # GET/POST /media/upload/{session_id}/{token}
  services/
    diagnostics_service.py   # RAG diagnosis
    scheduling_service.py    # Technician lookup + appointment booking
    email_service.py         # Brevo email sending
    vision_service.py        # GPT-4o image analysis
    session_service.py       # Session CRUD
    technician_service.py    # Technician CRUD
  settings/
    __init__.py        # Pydantic BaseSettings (all env vars)
  utils/
    ingest.py          # CLI tool: embed + store repair docs
    prompt.py          # build_system_prompt() helper
    twiml_builder.py   # TwiML response builder
    speech/
      stt.py           # WhisperSTTClient (μ-law → PCM → Whisper API)
      tts.py           # stream_tts() (OpenAI TTS → μ-law → Twilio WS)
docs/                  # Source appliance repair documents
migrations/            # Alembic migration scripts
scripts/
  seed.py              # DB seed: 10 technicians + 280 availability slots
```

---

## Core Component: `run_agent()` (app/api/chat.py)

This is the central orchestration function. It accepts `(session_id, user_text, session_data, db)` and returns `(reply: str, end_call: bool)`.

**Flow:**

1. Check Redis for `image_ready:{session_id}`. If present, delete the key and prepend a synthetic `[System: ...object_key=...]` message to `user_text` so the agent knows to call `analyze_appliance_image`.
2. Append the user turn to `session_data.history`.
3. Build the messages array: `[system_prompt] + session_data.history`.
4. Call `openai.chat.completions.create()` with `tools=TOOLS, tool_choice="auto"`.
5. If the model returns tool calls, dispatch each via `dispatch_tool()`, append the tool result to history, then loop (call the model again with the updated history).
6. Once the model returns a plain text message, extract it as the reply.
7. If `end_call` tool was called, `dispatch_tool` returns `(farewell_message, True)` — the loop exits with `end_call=True`.

**TOOLS array** (function calling schemas):

| Name | Key Parameters | Service |
|------|---------------|---------|
| `diagnose_appliance` | `appliance_type`, `symptoms` | `DiagnosticsService.diagnose()` |
| `find_available_technicians` | `zip_code`, `appliance_type` | `SchedulingService.find_available_technicians()` |
| `book_appointment` | `session_id`, `slot_id`, `technician_id`, `customer_name`, `customer_phone`, `appliance_type`, `symptoms` | `SchedulingService.book_appointment()` |
| `send_image_upload_email` | `customer_email`, `customer_name`, `session_id`, `appliance_type` | `EmailService.send_image_upload_email()` |
| `analyze_appliance_image` | `object_key`, `appliance_type` | `VisionService.analyze_appliance_image()` |
| `end_call` | `farewell_message` | Handled inline — sets `end_call=True` |

---

## Voice Pipeline (app/routes/twilio.py)

### Inbound call
`POST /voice/incoming`:
- Creates a `sessions` row (or retrieves existing by `call_sid`)
- Responds with TwiML `<Connect><Stream url="wss://.../voice/stream"/></Connect>`

### WebSocket handler (`WS /voice/stream`)
A long-lived WebSocket that manages the entire call:

```
Twilio sends:   {"event": "start", "streamSid": ..., "callSid": ...}
                {"event": "media", "media": {"payload": "<base64 mulaw>"}}
                {"event": "stop"}
```

Key state variables:
- `tts_task` — the currently running TTS coroutine (can be cancelled on barge-in)
- `interrupt_event` — `asyncio.Event` shared between the TTS streamer and the transcript handler
- `stream_sid` — needed to address Twilio's `clear` event (flush audio buffer)

**`on_transcript(text)` callback flow:**
1. Fetch accumulated content from Redis (`get call_sid`)
2. Append new text, validate with `is_valid_text()` (rejects noise/filler)
3. Write back to Redis
4. Check `image_ready:{call_sid}` — if set and no speech: proceed to agent anyway
5. If valid speech: cancel the current TTS task, send `{"event": "clear"}` to Twilio, clear interrupt event
6. Call `run_agent()` → get reply
7. Create new TTS task with `stream_tts()`

### Speech-to-Text (app/utils/speech/stt.py)
`WhisperSTTClient` buffers incoming base64 μ-law frames, converts to 16-bit PCM WAV in memory, and POSTs to `openai.audio.transcriptions.create(model="whisper-1")`. The callback fires per utterance (VAD is managed by accumulated audio length).

### Text-to-Speech (app/utils/speech/tts.py)
`stream_tts()` calls `openai.audio.speech.create(model="tts-1", response_format="pcm")`, encodes each PCM chunk to μ-law, base64-encodes it, and sends `{"event": "media", "media": {"payload": ...}}` over the Twilio WebSocket. It polls `interrupt_event` between chunks to support barge-in cancellation.

---

## RAG / Diagnostic Pipeline

### Document ingestion (app/utils/ingest.py)

CLI usage:
```bash
python -m app.utils.ingest \
  --file docs/washer_repair.txt \
  --appliance washer \
  --source whirlpool_washer_manual \
  --tags "leaking,not spinning"
```

Steps:
1. Read file → split into 500-character chunks with 50-character overlap; discard chunks < 50 chars
2. Embed each chunk in batches of 100 using `text-embedding-3-small` (1536 dims)
3. Upsert into `knowledge_chunks` table with `appliance_type`, `source`, `symptom_tags`, `content`, `embedding`

### Retrieval (app/services/diagnostics_service.py)

1. Embed the query string `"{appliance_type} {symptoms}"`
2. `KnowledgeRepository.similarity_search()` — pgvector cosine distance, filtered by `appliance_type`, returns top-K rows (default K=4 via `RAG_TOP_K`)
3. Format as context block
4. GPT-4o generates numbered troubleshooting steps strictly grounded in retrieved content

The pgvector SQL uses `<=>` (cosine distance) operator:
```sql
SELECT * FROM knowledge_chunks
WHERE appliance_type = :appliance_type
ORDER BY embedding <=> :query_embedding
LIMIT :k
```

---

## Scheduling System

### Database schema

```
technicians
  id (UUID PK), name, phone, email (unique), zip_codes (text, comma-separated),
  specialties (text, comma-separated), rating (float)

availability_slots
  id (UUID PK), technician_id (FK → technicians), slot_datetime, is_booked (bool)

appointments
  id (UUID PK), session_id, call_sid, technician_id (FK), slot_id (FK),
  customer_name, customer_phone, appliance_type, symptoms
```

### find_available_technicians

Filters in application code (not SQL):
- `zip_code in tech.zip_codes.split(",")`
- `appliance_type in tech.specialties.split(",")`

Returns up to 3 unbooked slots per matching technician with UUID `slot_id` and `technician_id` for the booking call.

### book_appointment (idempotency)

If `slot.is_booked` is already true, the service checks whether the existing appointment's `call_sid` matches the current caller. If it matches, it returns a success response (handles agent retries). If it doesn't match, it returns a failure ("booked by another caller").

---

## Visual Diagnosis Flow (Tier 3)

```
LLM calls send_image_upload_email(email, name, session_id, appliance_type)
  → EmailService generates upload_token (UUID)
  → Constructs upload URL: {PUBLIC_BASE_URL}/media/upload/{session_id}/{upload_token}
  → POSTs to Brevo SMTP API with HTML email containing upload button

Customer opens URL in browser
  → GET /media/upload/{session_id}/{token} → serves HTML upload form

Customer submits photo
  → POST /media/upload/{session_id}/{token}
  → Validates MIME type (JPEG/PNG/WebP/GIF) + size (≤ 10 MB)
  → Saves to {UPLOADS_DIR}/{session_id}/{uuid}.{ext}
  → Sets Redis: image_ready:{session_id} = object_key (TTL: 3600s)

Next agent turn (voice or image-triggered)
  → run_agent() reads image_ready:{session_id} from Redis
  → Deletes the key
  → Prepends [System: customer uploaded photo, object_key=...] to user_text

LLM calls analyze_appliance_image(object_key, appliance_type)
  → VisionService reads file from {UPLOADS_DIR}/{object_key}
  → Base64-encodes it
  → Sends to GPT-4o with vision prompt
  → Returns analysis text to agent → agent reads it to customer
```

---

## Database Migrations (Alembic)

Migrations live in `migrations/versions/`. Run manually or via container entrypoint:

```bash
alembic upgrade head
```

The migrations are ordered by dependency chain (each has `down_revision`). Current head creates all five tables and adds `call_sid` to `appointments`.

To generate a new migration after model changes:
```bash
alembic revision --autogenerate -m "describe change"
```

---

## Settings (app/settings/__init__.py)

All configuration is managed through a single Pydantic `BaseSettings` class. Values are read from environment variables (with `.env` file support via `python-dotenv`).

Key fields and their defaults:

| Field | Default | Notes |
|-------|---------|-------|
| `OPENAI_API_KEY` | `""` | Required |
| `LLM_MODEL` | `gpt-4o` | |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | |
| `RAG_TOP_K` | `4` | Number of RAG chunks per query |
| `OPENAI_TTS_MODEL` | `tts-1` | |
| `OPENAI_TTS_VOICE` | `alloy` | |
| `DATABASE_URL` | `postgresql+asyncpg://...` | asyncpg driver required |
| `REDIS_URL` | `redis://localhost:6379` | |
| `TWILIO_ACCOUNT_SID` | `""` | Required |
| `TWILIO_AUTH_TOKEN` | `""` | Required |
| `TWILIO_PHONE_NUMBER` | `""` | Required |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Must be public for Twilio + upload links |
| `BREVO_API_KEY` | `""` | Required for email |
| `BREVO_FROM_EMAIL` | `noreply@searsappliancecare.com` | |
| `BREVO_FROM_NAME` | `Sears Home Services` | |
| `UPLOADS_DIR` | `/tmp/appliance-uploads` | Local image storage directory |
| `SESSION_TTL_SECONDS` | `3600` | Redis key TTL |

---

## System Prompt Design (app/prompts/__init__.py)

The static `SYSTEM_PROMPT` defines four behaviour tiers:

1. **Tier 1 — Diagnosis:** Collect appliance type and symptoms → call `diagnose_appliance` → read out numbered steps. Never invent diagnostic steps.
2. **Tier 2 — Scheduling:** After diagnosis, offer to book a technician. Collect zip code → call `find_available_technicians` → present options → collect customer details → call `book_appointment` with exact UUIDs from the previous tool result.
3. **Tier 3 — Visual diagnosis:** Offer photo upload proactively when visual inspection would help. Collect email and name → call `send_image_upload_email` → wait for `[System: ...object_key=...]` injection → call `analyze_appliance_image`.
4. **Call termination:** Call `end_call` with a farewell message when done.

`build_system_prompt(context: dict)` appends a `## Current Session Context` block (key-value pairs) to the static prompt at runtime, giving the model live state (e.g. `appliance_type: washer`, `customer_zip: 90210`).

---

## Logging

`structlog` is configured to emit structured JSON logs. The `RequestResponseLoggerMiddleware` logs every HTTP request/response with method, path, status code, and duration. All services and the WebSocket handler log key events with contextual fields (`call_sid`, `session_id`, `reply`, etc.).

---

## MCP Server (app/api/mcpserver.py)

A `FastMCP` server (`ApplianceAgentMCP`) that exposes three tools to external MCP clients or agent frameworks:

- `diagnose_appliance(appliance_type, symptoms)` — calls `DiagnosticsService`
- `send_image_upload_email(customer_email, customer_name, session_id, appliance_type)` — calls `EmailService`
- `analyze_appliance_image(object_key, appliance_type)` — calls `VisionService`

This allows the same business logic to be consumed by external orchestrators (e.g. Claude Desktop, custom MCP clients) without duplicating service code.

---

## Development Notes

### Adding a new LLM tool

1. Define the JSON schema in the `TOOLS` list in `app/api/chat.py`
2. Add a branch in `dispatch_tool()` calling the appropriate service method
3. Add the corresponding service method (and repository query if DB access is needed)
4. Update the system prompt in `app/prompts/__init__.py` with instructions on when/how to use the tool

### Adding a new appliance type

1. Add a repair document to `docs/`
2. Run the ingest CLI with `--appliance <new_type>`
3. Ensure technicians in the seed data (or added via the API) have the new appliance type in their `specialties` field

### Running locally without Docker

```bash
# Start deps
docker compose up db redis -d

# Install deps
pip install -e .

# Run migrations
alembic upgrade head

# Seed DB
python -m scripts.seed

# Start app
uvicorn app.api.httpserver:app --reload --port 8000
```
