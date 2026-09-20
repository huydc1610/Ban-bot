#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="${BASH_SOURCE[0]%/*}"
if [[ "$script_dir" == "${BASH_SOURCE[0]}" ]]; then
  script_dir="."
fi

repo_dir="$(cd "$script_dir/.." && pwd)"
cd "$repo_dir"

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "Docker Engine and the Docker Compose plugin are required." >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Missing .env. Copy .env.example to .env and set TOKEN before deploying." >&2
  exit 1
fi

mkdir -p data
docker compose config --quiet
docker compose up -d --build
docker compose ps
