# AGENTS.md

This repository includes guidance for agents and contributors working inside the project. Follow these rules for changes, state persistence, and conventions.

## Memory & Persistence
- Runtime state lives in `data/state.json` and stores `{ chat_id, message_id }` so the bot can edit the correct Telegram message on subsequent runs.
- Do not remove or rename `data/state.json`. If you change its schema, update `src/state.py` and the README accordingly.
- Never commit secrets or runtime state:
  - `.env` contains credentials and must not be committed.
  - `data/state.json` is created at runtime and must not be committed.
- The bot avoids redundant Telegram edits by hashing the full Markdown payload (see `payload_hash` in `src/reducer.py`). Maintain this behavior to respect rate limits.

## Configuration
- All configuration comes from environment variables loaded via `.env` (see `src/config.py`).
- Required: `INFLUX_URL`, `INFLUX_TOKEN`, `INFLUX_ORG`, `TELEGRAM_BOT_TOKEN`.
- Optional/derived: bucket name, polling interval, time range, latency threshold, and explicit Telegram message IDs.
- An interactive config helper exists at `scripts/setup_config.py` (`make configure`).

## Coding Conventions
- Language: Python 3.11+
- Libraries: `influxdb-client`, `python-telegram-bot` v21, `python-dotenv`.
- Keep changes minimal and focused; prefer surgical edits over broad refactors.
- Follow existing structure under `src/`:
  - `config.py` – env parsing and defaults
  - `influx.py` – Flux query and window fetch
  - `reducer.py` – status reduction, formatting, hashing
  - `state.py` – persistence of message reference
  - `telegram_bot.py` – bot wiring, `/init_status`, update cycle
  - `main.py` – app entrypoint and scheduler
- Markdown rendering uses MarkdownV2 with escaping via `telegram.helpers.escape_markdown`. Do not switch parse mode without updating all escaping and tests.

## Testing & Linting
- Minimal unit tests live in `tests/`. Run with `make test`.
- Lint with `flake8` via `make lint`.
- When adding logic to reduction/formatting, extend tests rather than removing existing ones.

## Error Handling & Resilience
- Update cycles must not crash the process on partial failures.
- Telegram edits include a small retry loop with backoff. Preserve this behavior.
- If message editing fails due to permissions or wrong IDs, provide actionable logs guiding users to use `/init_status`.

## Git & Secrets
- Ensure `.env` and `data/state.json` are ignored by git (see `.gitignore`).
- Do not embed tokens, org names, buckets, or chat/message IDs in code or tests.
- Use environment variables and the setup script for configuration.

## When Making Changes
- If you add or change environment variables, update `.env.example` and the README.
- If you alter persistence format, update `src/state.py`, README, and migration notes if needed.
- Keep Dockerfile and docker-compose.yml functional; verify `docker compose up` still runs the bot.

