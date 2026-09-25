# CLAUDE.md — PropCall (AI calling + WhatsApp agent for real estate)

> Codename "PropCall" is a placeholder — rename freely. Keep this file at the repo root. Claude Code reads it at the start of every session.

## What we are building
A multi-tenant SaaS that replaces a real estate builder's / broker's telecalling (BPO) team:
1. **AI voice agent** calls leads (outbound) and answers call-backs (inbound) in **Marathi, Hindi or English**, sounds natural, qualifies the lead, handles objections, books site visits, schedules callbacks, and hands off hot leads to a human.
2. **After every call**: recording, transcript, AI summary, lead score (hot/warm/cold + reason), structured fields, sentiment, next action.
3. **WhatsApp agent**: sends project kit (brochure, floor plans, location pin, EMI link, "Book site visit" button) and answers questions.
4. **Dashboard**: campaigns, leads, calls, recordings, analytics per project, CSV export.

Customers: real estate builders, brokers/agents, channel partners. Pilot: 2 small clients, go-live in 10 days.

## Tech stack (do not change without asking)
| Layer | Choice |
|---|---|
| Voice pipeline | Python 3.11+, **Pipecat** (open source), FastAPI, WebSockets |
| Telephony | **Plivo** (Audio Stream API over WebSocket). Keep a `TelephonyProvider` interface so **Exotel** can be added later |
| STT | **Sarvam AI** streaming STT (code-mixed Indian speech) |
| TTS | **Sarvam AI Bulbul** streaming TTS |
| LLM (live call) | Fast, cheap model behind an `LLMProvider` interface (default: Sarvam chat; swappable via env) |
| LLM (post-call) | Stronger model, runs async after the call (summary, scoring, extraction) |
| DB / Auth / Storage | **Supabase** (Postgres + Auth + Storage for recordings & brochures) |
| Jobs / scheduling | **Redis + arq** (dialer queue, callbacks, reminders, post-call jobs) |
| WhatsApp | **Meta WhatsApp Cloud API** directly (no BSP markup) |
| Dashboard | **Next.js (App Router) + TypeScript + Tailwind + shadcn/ui**, Supabase client |
| Hosting | Voice agent + API + workers on a **Mumbai-region VPS** (Docker Compose). Dashboard on Vercel |

Always check the **current official docs** (Pipecat, Plivo, Sarvam, Meta WhatsApp Cloud API) before writing integration code — model names and SDK APIs change. Never guess an API signature.

## Repo layout
```
/apps/voice        Python: Pipecat bot, telephony websocket, call tools
/apps/api          Python: FastAPI REST + webhooks (Plivo, Meta, WhatsApp, lead sources)
/apps/worker       Python: arq workers (dialer, callbacks, reminders, post-call, whatsapp)
/apps/dashboard    Next.js dashboard
/packages/shared   Python shared: db models, config, prompt builder, provider interfaces
/supabase          SQL migrations + seed
/infra             docker-compose, Caddy/nginx, deploy scripts
/audio_cache       Pre-generated TTS clips (per org/project/language)
```

## Core data model (Postgres)
- `orgs` (id, name, type: builder|broker|channel_partner, plan, minutes_quota, minutes_used)
- `users` (Supabase auth) + `org_members` (org_id, user_id, role: owner|manager|agent)
- `projects` (org_id, builder_name, name, location, rera_no, config JSON: BHK types, price ranges, amenities, possession date, loan partners, brochure/floor-plan URLs, map pin, EMI link, FAQ, objection library, allowed-claims list)
- `project_access` (project_id, org_id) — channel-partner mode: one broker org can access many builders' projects
- `leads` (org_id, project_id, name, phone E.164, source: csv|meta_ads|google_ads|portal|website|inbound, language_pref, status, score hot|warm|cold, score_reason, fields JSON: bhk, budget_min, budget_max, location_pref, timeline, loan_needed, purpose live|invest, assigned_agent_id, created_at)
- `campaigns` (org_id, project_id, name, status, calling_window, max_concurrency, retry_policy)
- `calls` (lead_id, campaign_id, direction, provider_call_id, status, language, started_at, ended_at, duration_s, recording_url, transcript JSON, summary, sentiment, objections JSON, outcome, next_action, cost_estimate)
- `callbacks` (lead_id, scheduled_at, reason, status)
- `site_visits` (lead_id, project_id, slot_start, slot_end, status booked|confirmed|done|no_show|cancelled, reminders_sent JSON, feedback)
- `visit_slots` (project_id, day_of_week, start, end, capacity)
- `wa_messages` (lead_id, direction, type, template_name, body, status, wa_message_id)
- `dnc` (org_id nullable = global, phone, reason, added_at)
- `handoffs` (call_id, agent_phone, status)
- `usage_events` (org_id, kind: call_minute|wa_message|tts_chars|stt_seconds|llm_tokens, qty, cost)

Row Level Security on every table by `org_id`.

## Call flow (outbound)
1. Dialer picks lead → checks DNC, calling window (09:00–21:00 IST, configurable narrower), org minute quota → Plivo outbound call.
2. On answer → Plivo streams audio to `/apps/voice` websocket → Pipecat pipeline: STT → LLM (with tools) → TTS.
3. **Opening (mandatory)**: greet, say it is an **AI assistant calling on behalf of <company>**, that the call is recorded, then ask/confirm language (Marathi / Hindi / English). If `language_pref` is known, confirm instead of asking.
4. **Language lock**: after selection, the whole call stays in that language. Natural code-mixing (Hinglish, Marathi + English words) is allowed. Switch ONLY if the customer explicitly asks.
5. Qualify: interest, BHK, budget, location, timeline, loan, purpose. Handle objections from the project's objection library.
6. Tools the LLM can call: `book_site_visit`, `schedule_callback`, `transfer_to_human`, `send_whatsapp_kit`, `mark_not_interested`, `add_to_dnc`, `end_call`.
7. Answering machine / no speech for N seconds → hang up. Hard max call duration (default 6 min).
8. After hangup → enqueue post-call job.

## Post-call job
Fetch recording → store in Supabase Storage → run post-call LLM on transcript → strict JSON: `summary, score, score_reason, fields, sentiment, objections[], outcome, next_action` → update lead & call → trigger WhatsApp kit if warm/hot or requested → create callback if needed → log usage/cost.

## Non-negotiable rules
- **AI disclosure** in the first sentence of every call. Never claim to be human, even if asked — answer honestly and offer a human callback.
- **Recording notice** at call start.
- **Only state facts from the project config.** Never invent prices, discounts, possession dates, approvals, or loan offers. If unsure → "our sales team will confirm" + schedule callback.
- **DNC**: check before every call and every WhatsApp; "don't call me" → add to DNC immediately, end politely.
- Respect calling window and retry limits. Never call a number more than the retry policy allows.
- Secrets only via env vars. Never log full phone numbers in plain logs (mask middle digits).
- Latency target: bot starts speaking < 1s after user stops. Stream everything.

## Cost rules
- Pre-generate and cache fixed utterances (greeting, disclosure, language question, project intro, top objection answers) as audio per project+language; play from `/audio_cache` instead of live TTS.
- Keep the system prompt stable (project data at the top) to benefit from prompt caching.
- Cheap LLM live, stronger LLM only post-call.
- Log estimated cost per call in `calls.cost_estimate` and `usage_events`.

## Coding conventions
- Python: type hints, pydantic models, ruff + black, pytest. Async everywhere in voice/api.
- TS: strict mode, server components by default, zod for validation.
- Every external integration behind an interface in `/packages/shared/providers`.
- Write tests for: prompt builder, language lock logic, DNC/calling-window guard, post-call JSON parsing, webhook signature verification.
- Small commits with clear messages. Update this file when architecture changes.

## Implementation notes (keep current)
- **DB access**: backend uses **asyncpg** via `packages/shared/db/repositories.py` (connects with `SUPABASE_DB_URL`, bypasses RLS, so every repo method takes `org_id`). Dashboard uses supabase-js + RLS. Transaction pooler (port 6543) → statement cache disabled automatically.
- **Tenancy**: every child table carries `org_id`; composite FKs `(x_id, org_id)` stop cross-org references. RLS helpers live in the `private` schema (`is_org_member`, `has_org_role`, `can_access_project`, `can_manage_project`).
- **Channel partner**: broker orgs see builder projects via `project_access`; their leads/calls stay private to the broker.
- **Migrations**: `supabase/migrations/<version>_*.sql` versions match the hosted project's history — keep new ones in the same format and apply with `supabase db push`/MCP. DB tests: `make test-db` (embedded Postgres, no Docker).
- **Voice routes** (in `apps/voice`, Caddy sends `/plivo/*` + `/ws/*` there): `POST /plivo/answer` → `<Stream>` XML with a call-bound HMAC token; `POST /plivo/status`; `POST /plivo/transfer` (target number Fernet-encrypted in URL); `WS /ws/plivo`. All Plivo POSTs verify `X-Plivo-Signature-V3` against `PUBLIC_BASE_URL`.
- **Pipeline** (Pipecat 1.11): Plivo serializer → Sarvam STT (saaras) → user aggregator (Silero VAD, smart-turn, barge-in) → LLM (`LLMProvider`) → Sarvam Bulbul TTS @ 8 kHz → Plivo. Greeting/disclosure is a verbatim `TTSSpeakFrame`, never LLM-generated. Per-turn latency logged by `voice/latency.py`.
