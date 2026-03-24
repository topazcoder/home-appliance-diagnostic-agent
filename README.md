# SHS Appliance Diagnostic Agent

> **Sears Home Services — AI Engineering Team**

A conversational AI voice agent that handles inbound appliance repair calls for Sears Home Services customers — no hold music, no menu trees, no human agent required. Customers call a real phone number, describe their problem in plain language, and walk away with a diagnosis, a repair appointment, or both.

**Call the agent now: `+1 (866) 609-2486`**

---

## The Product

Home appliance repairs start with a phone call. Today that call goes to a queue. This product replaces the queue with an intelligent voice agent that is always available, never fatigued, and capable of diagnosing appliance problems, escalating to a technician booking, and even analyzing a photo of the broken appliance — all within a single phone call.

The experience feels like talking to a knowledgeable service representative:

> **Customer:** "My washer is making a loud banging noise during the spin cycle."
>
> **Agent:** "That sounds like it could be an unbalanced drum or a worn bearing. Let me pull up some troubleshooting steps for you..."
>
> *(A few minutes later)*
>
> **Agent:** "If none of those steps resolve it, I can book a certified technician for you. What is your zip code?"

No scripts. No IVR menus. Just a conversation.

---

## Core Capabilities

### Intelligent Appliance Diagnosis
The agent draws on a curated knowledge base of real appliance repair documentation. When a customer describes symptoms, the agent retrieves the most relevant passages and generates grounded, step-by-step troubleshooting guidance. It only recommends steps supported by the documentation — it never guesses.

Supported appliances: **washer, dryer, refrigerator** (expandable to any appliance by ingesting additional documentation).

### Visual Inspection via Photo Upload
When a symptom is ambiguous or physical damage is suspected, the agent offers to analyze a photo. It sends the customer an email with a secure, one-time upload link. The customer uploads the photo on their phone while still on the call. The agent receives the image instantly and describes what it sees — visible rust, broken components, worn seals — then adjusts its recommendations accordingly.

### Technician Scheduling
When self-service troubleshooting is not enough, the agent finds available certified technicians near the customer's location who specialize in their appliance type. It presents available time slots, confirms the customer's choice, and books the appointment — all within the same call.

### Natural Conversation
The agent speaks and listens like a person. Customers can interrupt at any point ("barge in") and the agent adjusts immediately. There are no fixed conversation paths — the agent follows the customer's needs wherever they lead.

---

## Services and Ecosystem

This product is built on a modern, cloud-native service ecosystem. Each component was chosen to be best-in-class for its role while keeping the overall stack simple to operate and cost-effective to run.

### Twilio — Voice and Telephony
Twilio powers the phone call infrastructure. Inbound calls are routed to the agent via a Twilio phone number. Real-time bidirectional audio is streamed over Twilio Media Streams (WebSocket), giving the agent a continuous, low-latency audio channel to the caller.

**Role in this product:** Call routing, real-time audio transport, call lifecycle management (answer, hold, hang up).

### OpenAI — Intelligence Layer
OpenAI provides the core AI capabilities across four distinct functions:

| Capability | Model | Role |
|------------|-------|------|
| Conversational agent | GPT-4o | Understands the customer, decides what to do next, calls tools |
| Speech-to-text | Whisper | Converts the customer's voice into text in real time |
| Text-to-speech | TTS-1 (`alloy` voice) | Converts the agent's responses back into natural-sounding speech |
| Visual analysis | GPT-4o Vision | Analyzes uploaded appliance photos and describes findings |
| Knowledge embeddings | text-embedding-3-small | Powers semantic search over the repair knowledge base |

**Role in this product:** The brain — perception (hearing and seeing), reasoning (what is wrong, what should happen next), and speech (speaking back to the customer).

### Brevo — Email Delivery
Brevo delivers the secure photo upload link to the customer's email address during the call. When the agent determines a visual inspection would help, it collects the customer's email, generates a one-time upload URL, and dispatches the email within seconds via the Brevo transactional API.

**Role in this product:** Bridging the voice channel to the visual inspection workflow.

### PostgreSQL + pgvector — Data and Knowledge
PostgreSQL is the system of record for everything: technician profiles, availability schedules, booked appointments, conversation sessions, and the appliance repair knowledge base. The pgvector extension stores the knowledge base as high-dimensional vector embeddings, enabling fast semantic similarity search — the mechanism that powers grounded diagnosis.

**Role in this product:** Persistent storage for operational data and the AI knowledge base.

### Redis — Real-time Session State
Redis holds live call session data and acts as a lightweight notification bus between the photo upload endpoint and the active voice session. When a customer uploads a photo, the upload service writes a notification key to Redis. The agent's active call session detects this within milliseconds and triggers visual analysis — no polling, no delay.

**Role in this product:** Low-latency state sharing between the upload flow and the live phone call.

### Nginx — Traffic Entry Point
Nginx acts as the public-facing reverse proxy, routing inbound HTTP traffic from Twilio, browsers (for photo upload), and API clients to the FastAPI application.

**Role in this product:** Stable, high-performance HTTP entry point.

---

## Deployment

The entire system — application, database, cache, and proxy — ships as a single Docker Compose stack. One command brings everything up:

```bash
docker compose up --build
```

For a public endpoint (required for Twilio webhooks), point ngrok or any reverse proxy at port 80:

```bash
ngrok http 80
```

Set the resulting URL as the Twilio webhook and in the `PUBLIC_BASE_URL` environment variable. The agent is then live and reachable by phone.

See [docs/TECHNICAL.md](docs/TECHNICAL.md) for full setup instructions, environment variable reference, API documentation, and development guide.

---

## Documentation

| Document | Audience | Contents |
|----------|----------|----------|
| This file | Everyone | Product overview, capabilities, service ecosystem |
| [docs/TECHNICAL.md](docs/TECHNICAL.md) | Developers | Architecture, setup, environment variables, API reference, development workflow |

---

## Requirements

| Credential | Where to get it |
|------------|----------------|
| OpenAI API key | [platform.openai.com](https://platform.openai.com/) — GPT-4o access required |
| Twilio account + phone number | [twilio.com](https://www.twilio.com/) |
| Brevo API key | [brevo.com](https://www.brevo.com/) — free tier, no credit card |
| Public HTTPS URL | [ngrok.com](https://ngrok.com/) for local development; any domain for production |

**Role in this product:** Low-latency state sharing between the upload flow and the live phone call.

### Nginx — Traffic Entry Point
Nginx acts as the public-facing reverse proxy, routing inbound HTTP traffic from Twilio, browsers (for photo upload), and API clients to the FastAPI application.

**Role in this product:** Stable, high-performance HTTP entry point.

---
