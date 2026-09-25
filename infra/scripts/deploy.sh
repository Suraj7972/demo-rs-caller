#!/usr/bin/env bash
# Deploy on the VPS: pull latest code and rebuild/restart the stack.
set -euo pipefail
cd "$(dirname "$0")/../.."
git pull --ff-only
docker compose -f infra/docker-compose.yml --env-file .env up -d --build
docker compose -f infra/docker-compose.yml --env-file .env ps
