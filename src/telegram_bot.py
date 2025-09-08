from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackContext,
    CommandHandler,
    ContextTypes,
    Defaults,
)

from .config import Config
from .influx import fetch_probe_window
from .reducer import (
    format_markdown_v2,
    payload_hash,
    reduce_status,
    format_board_zh,
)
from .state import MessageRef, load_message_ref, save_message_ref


logger = logging.getLogger(__name__)


@dataclass
class BotState:
    msg_ref: Optional[MessageRef]
    last_hash: Optional[str] = None


def build_application(cfg: Config) -> Application:
    app = (
        Application.builder()
        .token(cfg.telegram_bot_token)
        .defaults(Defaults(parse_mode=ParseMode.MARKDOWN_V2))
        .build()
    )

    # /init_status handler
    async def init_status(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if update.effective_chat is None or update.effective_user is None:
            return

        # Only allow in groups/supergroups
        if update.effective_chat.type not in {"group", "supergroup"}:
            await update.effective_message.reply_text(
                "Please run this in a group where the bot is a member."
            )
            return

        # Post initial message (or reply to the replied message)
        reply_to = update.effective_message.reply_to_message
        try:
            sent: Message = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Initializing status…",
                reply_to_message_id=reply_to.message_id if reply_to else None,
                parse_mode=ParseMode.MARKDOWN_V2,
            )
        except Exception as e:
            logger.error("Failed to send init message: %s", e)
            await update.effective_message.reply_text(
                "Failed to send init message. Ensure the bot can send messages here."
            )
            return

        ref = MessageRef(chat_id=sent.chat_id, message_id=sent.message_id)
        save_message_ref(ref)
        await update.effective_message.reply_text("Status message initialized and saved.")

    app.add_handler(CommandHandler("init_status", init_status))

    return app


async def update_cycle(
    cfg: Config, state: BotState, context: CallbackContext
) -> None:
    """One cycle: fetch → reduce → format → edit if changed."""
    now = datetime.now(timezone.utc)
    try:
        if cfg.status_template == "board_zh":
            # Domestic vantage
            dom_data = fetch_probe_window(
                url=cfg.influx_url,
                token=cfg.influx_token,
                org=cfg.influx_org,
                bucket=cfg.influx_bucket,
                minutes=cfg.time_range_minutes,
                probe_node=cfg.domestic_probe_node,
            )
            dom_status = reduce_status(
                dom_data,
                minutes=cfg.time_range_minutes,
                latency_warn_ms=cfg.latency_warn_ms,
            )
            # Foreign vantage (optional)
            if cfg.foreign_probe_node:
                for_data = fetch_probe_window(
                    url=cfg.influx_url,
                    token=cfg.influx_token,
                    org=cfg.influx_org,
                    bucket=cfg.influx_bucket,
                    minutes=cfg.time_range_minutes,
                    probe_node=cfg.foreign_probe_node,
                )
                for_status = reduce_status(
                    for_data,
                    minutes=cfg.time_range_minutes,
                    latency_warn_ms=cfg.latency_warn_ms,
                )
            else:
                for_status = {}

            def is_alert(ns) -> bool:
                return (not ns.up) or (cfg.include_degraded_as_alert and ns.degraded)

            domestic_alerts = [s.name for s in dom_status.values() if is_alert(s)]
            foreign_alerts = [s.name for s in for_status.values() if is_alert(s)]

            text = format_board_zh(
                now=now,
                domestic_alerts=domestic_alerts,
                foreign_alerts=foreign_alerts,
            )
        else:
            # Default compact list
            data = fetch_probe_window(
                url=cfg.influx_url,
                token=cfg.influx_token,
                org=cfg.influx_org,
                bucket=cfg.influx_bucket,
                minutes=cfg.time_range_minutes,
            )
            statuses = reduce_status(
                data, minutes=cfg.time_range_minutes, latency_warn_ms=cfg.latency_warn_ms
            )
            text = format_markdown_v2(
                cfg.status_title,
                statuses,
                minutes=cfg.time_range_minutes,
                show_protocol=cfg.show_protocol,
                now=now,
            )
        h = payload_hash(text)

        # Determine message ref precedence: explicit in env, else persisted
        ref = state.msg_ref
        if cfg.telegram_chat_id and cfg.telegram_message_id:
            ref = MessageRef(
                chat_id=cfg.telegram_chat_id, message_id=cfg.telegram_message_id
            )

        if ref is None:
            # Try load from disk (in case not loaded yet)
            ref = load_message_ref()
            state.msg_ref = ref

        if ref is None:
            logger.info(
                "No target message configured. Run /init_status in your group or set "
                "TELEGRAM_CHAT_ID + TELEGRAM_MESSAGE_ID."
            )
            return

        # Avoid redundant edits
        if state.last_hash == h:
            logger.info("No change; skipping edit.")
            return

        # Try editing with basic retry
        tries = 3
        for attempt in range(1, tries + 1):
            try:
                await context.bot.edit_message_text(
                    chat_id=ref.chat_id,
                    message_id=ref.message_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    disable_web_page_preview=True,
                )
                state.last_hash = h
                logger.info("Edited status message (chat=%s, msg=%s)", ref.chat_id, ref.message_id)
                break
            except Exception as e:
                if attempt == tries:
                    logger.error("Failed to edit message after %s attempts: %s", attempt, e)
                else:
                    logger.warning("Edit failed (attempt %s/%s): %s", attempt, tries, e)
                    await asyncio.sleep(1.0 * attempt)

    except Exception as e:
        logger.error("Update cycle error: %s", e)
