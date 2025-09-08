# Telegram Status Page Bot (InfluxDB 2.0 → Telegram)

A small, ready-to-run bot that reads probe metrics from InfluxDB 2.0 and keeps a Telegram message updated as a compact, live status page.

- Stack: Python 3.11+, `influxdb-client`, `python-telegram-bot[job-queue]` v21
- Loop: query → reduce → format → edit message
- Two ways to target the message: explicit IDs via env, or bootstrap with `/init_status` which stores IDs in `data/state.json`.

## Features

- Pulls last N minutes of `probe` metrics (`alive`, `delay_ms`)
- Per-node reduction: latest `alive`/`delay_ms` within the window
- Status: ✅ UP, ⚠️ DEGRADED (optional latency threshold), ❌ DOWN
- Stable MarkdownV2 output (UP → DEGRADED → DOWN; alpha within group)
- Avoids redundant edits via SHA-256 payload hash
- Graceful error handling and small Telegram retry loop

## Quick Start

1) Copy `.env.example` → `.env` and fill in values:

```
INFLUX_URL=http://localhost:8086
INFLUX_TOKEN=...
INFLUX_ORG=...
INFLUX_BUCKET=clashprobe
TIME_RANGE_MINUTES=5
POLL_INTERVAL_SECONDS=30
LATENCY_WARN_MS=
TELEGRAM_BOT_TOKEN=...
# Option A: explicit IDs
# TELEGRAM_CHAT_ID=
# TELEGRAM_MESSAGE_ID=
STATUS_TITLE=Network Status
SHOW_PROTOCOL=true
```

2) Configure interactively (optional):

```
make configure
```

This writes a `.env` with your InfluxDB and Telegram settings and can run quick connectivity tests.

3) Run (local Python):

- One-off: `make run`
- With a venv: `make init && make dev`

4) Or with Docker:

```
docker compose up --build
```

On first run without `TELEGRAM_MESSAGE_ID`, use `/init_status` in your target group. The bot will post an initial message and persist `{ chat_id, message_id }` in `data/state.json`.

## How It Works

- Every `POLL_INTERVAL_SECONDS`, the bot queries the last `TIME_RANGE_MINUTES` from InfluxDB:

  ```flux
  from(bucket: "clashprobe")
    |> range(start: -5m)
    |> filter(fn: (r) => r._measurement == "probe")
    |> filter(fn: (r) => r._field == "alive" or r._field == "delay_ms")
  ```

- Reduce per `name`:
  - `alive` = most recent `alive` value in window
  - `latency` = most recent `delay_ms` in window
  - No data ⇒ DOWN (dead/unknown)
- Decision:
  - `alive == true` ⇒ UP
  - Optional: if `delay_ms > LATENCY_WARN_MS`, mark as DEGRADED
- Formatting: MarkdownV2 with proper escaping via `telegram.helpers.escape_markdown`
- Edit message only if content changed (hash check). Handles Telegram edit errors with small retries.

## Configuration

- `INFLUX_URL` (e.g., `http://localhost:8086`)
- `INFLUX_TOKEN`
- `INFLUX_ORG`
- `INFLUX_BUCKET` (default `clashprobe`)
- `TIME_RANGE_MINUTES` (default `5`)
- `POLL_INTERVAL_SECONDS` (default `30`)
- `LATENCY_WARN_MS` (optional)
- `TELEGRAM_BOT_TOKEN`
- Either:
  - `TELEGRAM_CHAT_ID` and `TELEGRAM_MESSAGE_ID`, or
  - Run `/init_status` in the group and the bot will persist IDs to `data/state.json`
- `STATUS_TITLE` (default `Network Status`)
- `SHOW_PROTOCOL` (true/false)

## Usage

- Explicit message IDs: set `TELEGRAM_CHAT_ID` and `TELEGRAM_MESSAGE_ID`. The bot will edit that message each cycle. Note: the bot may only edit messages it sent.
- Bootstrap: add the bot to a group and run `/init_status`. The bot posts the initial status message (or replies to the message you replied to) and persists its IDs. Subsequent cycles edit that message.

### Example Output

```
*Network Status (last 5m)*

✅ [SS][IPLC][SHCU-HK] Azure (Shadowsocks) — 82 ms
❌ MyNode-2 — no recent heartbeat

_Updated: 2025-09-07 16:15:03Z_
```

## Development

- Lint: `make lint`
- Test: `make test`

Unit tests cover reducer/formatter logic (`tests/test_reducer.py`).

## Notes & Troubleshooting

- The bot can only edit messages it sent. If you see errors like "message can't be edited" or "message to edit not found", initialize with `/init_status`.
- Names and protocols are escaped for MarkdownV2 safety. If you change parse mode, adjust escaping accordingly.
- Display timestamps are UTC.
- If you have no points for a node within the window, it will not appear (there’s no prior knowledge of nodes). Continuous probes ensure down nodes stop reporting and effectively disappear; those are treated as DOWN when seen within the window.
- Ensure the Influx token has read access to the bucket.

## License

MIT
