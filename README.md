# PropCall

AI calling + WhatsApp agent for real estate. Architecture, rules and data model live in [CLAUDE.md](CLAUDE.md).

## Layout

| Path | What |
|---|---|
| `apps/api` | FastAPI REST + webhooks (`api` package) |
| `apps/voice` | Pipecat voice bot + telephony websocket (`voice` package) |
| `apps/worker` | arq workers (`worker` package) |
| `apps/dashboard` | Next.js (App Router, TS strict, Tailwind, shadcn/ui) |
| `packages/shared` | Shared Python (`shared` package): config, models, prompt builder, providers |
| `supabase` | SQL migrations + seed |
| `infra` | docker-compose, Caddyfile, Dockerfile, deploy script |
| `audio_cache` | Pre-generated TTS clips (git-ignored) |

The Python apps form one **uv workspace** (root `pyproject.toml`, single `uv.lock`, single `.venv`).

## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/) (`pip install uv` or the official installer)
- Node 20+ and npm
- Docker with Compose v2 (for Redis locally, and the full stack)
- [Supabase CLI](https://supabase.com/docs/guides/cli) (for migrations)
- GNU make. On Windows, use Git Bash/WSL with make (`scoop install make` or `choco install make`), or run the commands inside the Makefile directly.

## Local setup

```bash
# 1. Env
cp .env.example .env                                   # fill in keys
cp apps/dashboard/.env.example apps/dashboard/.env.local

# 2. Deps
make install          # uv sync + npm install

# 3. Run everything with hot reload
make dev              # redis (docker) + api :8000, voice :8765, worker, dashboard :3000
```

Check: `curl localhost:8000/healthz` and `curl localhost:8765/healthz`.

## Database

Schema, RLS and seed live in `supabase/`. The hosted project is already migrated and seeded;
for a fresh project run `make migrate` (or `supabase db push`), then run `supabase/seed.sql`.

Backend code talks to Postgres with **asyncpg** through the repositories in
`packages/shared/db` (see the module docstring for why not supabase-py). The dashboard uses
supabase-js, where RLS applies.

Repository tests (every test runs in a rolled-back transaction):

| Command | Runs against |
|---|---|
| `make test-db` | throwaway embedded Postgres, no Docker (applies migrations + seed itself) |
| `make test-db-local` | `supabase start` (Docker) |

## Test call (voice smoke test)

**1. Env** (`.env` at the repo root):

| Var | Value |
|---|---|
| `PLIVO_AUTH_ID`, `PLIVO_AUTH_TOKEN` | Plivo console → Overview |
| `PLIVO_CALLER_ID` | Your Plivo number in E.164, e.g. `+9180XXXXXXXX` |
| `SARVAM_API_KEY` | Sarvam dashboard → API keys (STT, TTS and the live LLM) |
| `PUBLIC_BASE_URL` | The tunnel URL from step 3, e.g. `https://abc.ngrok-free.app` |
| `APP_SECRET_KEY` | Any long random string |
| optional | `SARVAM_TTS_SPEAKER`, `LLM_LIVE_MODEL`, `SILENCE_TIMEOUT_S`, `MAX_CALL_DURATION_S` |

**2. Plivo console**
- Outbound only needs the Auth ID/Token and a voice-enabled number: the answer URL is sent
  per call, so no Plivo Application is required.
- Trial accounts can only call numbers verified under *Phone Numbers → Sandbox Numbers*.
- Calling Indian numbers requires Plivo's India compliance/KYC on the account and number.
- For inbound: *Voice → Applications → New*: Answer URL `https://<tunnel>/plivo/answer` (POST),
  Hangup URL `https://<tunnel>/plivo/status` (POST); then attach the application to your number.
- Webhooks are signed (`X-Plivo-Signature-V3`) automatically; we verify them with your Auth Token.

**3. Tunnel to the voice server (port 8765)**. It serves `/plivo/*` and `/ws/plivo`:

```bash
ngrok http 8765
```

```bash
cloudflared tunnel --url http://localhost:8765
```

Both give an `https://` URL that also carries the `wss://` media stream. Put it in `PUBLIC_BASE_URL`
and (re)start the voice server so it picks it up.

**4. Run**

```bash
make dev-voice
```

```bash
make test-call to=+91XXXXXXXXXX
```

The bot greets in Hindi (`lang=mr` / `lang=en` also work), says it is an AI assistant, and chats.
The voice console prints transcripts and, per turn, `[latency] ... user-stop -> first bot audio = N ms`
plus a per-service TTFB breakdown and a p50/p90 summary at hang-up.

## Common tasks

| Command | Does |
|---|---|
| `make test` | pytest across all Python packages |
| `make test-db` | DB repository tests (embedded Postgres) |
| `make test-call to=+91…` | Real smoke-test call through Plivo |
| `make lint` | ruff + black --check + eslint + tsc |
| `make fmt` | ruff --fix + black |
| `make migrate` | `supabase db push` to `SUPABASE_DB_URL` |
| `make up` / `make down` | Build + start / stop the Docker stack |
| `make logs` (`s=voice`) | Tail stack logs |

## Deploy (Mumbai VPS)

1. Point a DNS A record for `DOMAIN` at the VPS; open ports 80/443.
2. Clone the repo and create `.env` (compose overrides `REDIS_URL` to `redis://redis:6379/0`).
3. `make up` (or `infra/scripts/deploy.sh`). Caddy obtains TLS automatically:
   - `wss://$DOMAIN/ws/*` and `https://$DOMAIN/plivo/*` → voice
   - everything else → api
4. Dashboard deploys to Vercel from `apps/dashboard` (set its `NEXT_PUBLIC_*` env vars there).
