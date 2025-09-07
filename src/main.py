"""
Polling → reduce → format → edit loop:
- On a fixed interval, query InfluxDB for the last N minutes of probe metrics.
- Reduce per node name: latest `alive` and `delay_ms` values within the window.
- Decide status: if `alive` is true and recent ⇒ UP; else DOWN. If a latency
  threshold is provided and `delay_ms` exceeds it, mark as DEGRADED.
- Format a compact MarkdownV2 message and edit the configured Telegram message.

Missing data handling:
- If a node has no data within the window, treat it as DOWN (dead/unknown).

Hashing to avoid redundant edits:
- Before editing, compute a SHA-256 hash of the formatted payload. If the hash
  is unchanged from the previous cycle, skip the edit to respect Telegram rate limits.

Failure handling and retries:
- Each cycle is wrapped with error handling so transient errors do not crash the bot.
- Editing the Telegram message uses a small retry loop with backoff.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Optional

from telegram.ext import Application

from .config import load_config
from .state import load_message_ref
from .telegram_bot import BotState, build_application, update_cycle


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def main_async() -> None:
    setup_logging()
    cfg = load_config()

    app: Application = build_application(cfg)

    # Initial state: load persisted message ref if any
    state = BotState(msg_ref=load_message_ref(), last_hash=None)

    # Schedule periodic job
    async def job_callback(context):
        await update_cycle(cfg, state, context)

    app.job_queue.run_repeating(job_callback, interval=cfg.poll_interval_seconds, first=0)

    # Run polling with graceful shutdown
    await app.run_polling(close_loop=False)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
