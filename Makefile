# PropCall task runner. Requires: uv, node/npm, docker (compose v2), supabase CLI.
# On Windows run from Git Bash / WSL with GNU make installed.

COMPOSE := docker compose -f infra/docker-compose.yml --env-file .env
UV      := uv run

.PHONY: help install dev dev-api dev-voice dev-worker dev-dashboard test test-db test-db-local test-call lint fmt migrate up down logs

help: ## List targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

install: ## Install Python (uv) and dashboard (npm) deps
	uv sync
	cd apps/dashboard && npm install

dev: ## Run redis (docker) + api, voice, worker, dashboard locally with reload
	$(COMPOSE) up -d redis
	$(MAKE) -j4 dev-api dev-voice dev-worker dev-dashboard

dev-api:
	$(UV) uvicorn api.main:app --reload --port 8000 --reload-dir apps/api --reload-dir packages/shared

dev-voice:
	$(UV) uvicorn voice.main:app --reload --port 8765 --reload-dir apps/voice --reload-dir packages/shared

dev-worker:
	$(UV) arq worker.main.WorkerSettings --watch apps/worker

dev-dashboard:
	cd apps/dashboard && npm run dev

test: ## Run pytest (DB tests skip unless TEST_DATABASE_URL is set)
	$(UV) pytest

test-db: ## DB repository tests on a throwaway embedded Postgres (no Docker)
	uv run --with pgserver python infra/scripts/test_db_embedded.py

test-db-local: ## DB repository tests against `supabase start`
	TEST_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres $(UV) pytest packages/shared/tests/db

test-call: ## Place a smoke-test call: make test-call to=+91XXXXXXXXXX [lang=hi|mr|en]
	$(UV) python -m apps.voice.test_call $(to) --lang $(or $(lang),hi)

lint: ## ruff + black --check + dashboard eslint/tsc
	$(UV) ruff check .
	$(UV) black --check .
	cd apps/dashboard && npm run lint && npx tsc --noEmit

fmt: ## Auto-fix: ruff --fix + black
	$(UV) ruff check --fix .
	$(UV) black .

migrate: ## Apply supabase/migrations to SUPABASE_DB_URL
	@set -a; . ./.env; set +a; supabase db push --db-url "$$SUPABASE_DB_URL"

up: ## Build + start the full stack (api, voice, worker, redis, caddy)
	$(COMPOSE) up -d --build

down: ## Stop the stack
	$(COMPOSE) down

logs: ## Tail stack logs (make logs s=voice for one service)
	$(COMPOSE) logs -f --tail=200 $(s)
