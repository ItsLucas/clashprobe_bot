import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Config:
    influx_url: str
    influx_token: str
    influx_org: str
    influx_bucket: str = "clashprobe"

    time_range_minutes: int = 5
    poll_interval_seconds: int = 30
    latency_warn_ms: Optional[int] = None

    telegram_bot_token: str = ""
    telegram_chat_id: Optional[int] = None
    telegram_message_id: Optional[int] = None

    status_title: str = "Network Status"
    show_protocol: bool = True


def _to_bool(val: Optional[str], default: bool) -> bool:
    if val is None or val == "":
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config() -> Config:
    # Load .env if present
    load_dotenv(override=False)

    missing = []
    influx_url = os.getenv("INFLUX_URL") or ""
    influx_token = os.getenv("INFLUX_TOKEN") or ""
    influx_org = os.getenv("INFLUX_ORG") or ""

    if not influx_url:
        missing.append("INFLUX_URL")
    if not influx_token:
        missing.append("INFLUX_TOKEN")
    if not influx_org:
        missing.append("INFLUX_ORG")

    influx_bucket = os.getenv("INFLUX_BUCKET", "clashprobe")

    def _int_env(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None or raw.strip() == "":
            return default
        try:
            v = int(raw)
            if v <= 0:
                raise ValueError
            return v
        except Exception:
            raise ValueError(f"Invalid integer for {name}: {raw}")

    time_range_minutes = _int_env("TIME_RANGE_MINUTES", 5)
    poll_interval_seconds = _int_env("POLL_INTERVAL_SECONDS", 30)

    latency_warn_raw = os.getenv("LATENCY_WARN_MS")
    latency_warn_ms = None
    if latency_warn_raw and latency_warn_raw.strip() != "":
        try:
            latency_warn_ms = int(latency_warn_raw)
            if latency_warn_ms < 0:
                raise ValueError
        except Exception:
            raise ValueError(f"Invalid integer for LATENCY_WARN_MS: {latency_warn_raw}")

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or ""
    if not telegram_bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")

    def _opt_int(name: str) -> Optional[int]:
        raw = os.getenv(name)
        if raw is None or raw.strip() == "":
            return None
        try:
            return int(raw)
        except Exception:
            raise ValueError(f"Invalid integer for {name}: {raw}")

    telegram_chat_id = _opt_int("TELEGRAM_CHAT_ID")
    telegram_message_id = _opt_int("TELEGRAM_MESSAGE_ID")

    status_title = os.getenv("STATUS_TITLE", "Network Status")
    show_protocol = _to_bool(os.getenv("SHOW_PROTOCOL"), True)

    if missing:
        raise RuntimeError(
            "Missing required environment variables: " + ", ".join(missing)
        )

    return Config(
        influx_url=influx_url,
        influx_token=influx_token,
        influx_org=influx_org,
        influx_bucket=influx_bucket,
        time_range_minutes=time_range_minutes,
        poll_interval_seconds=poll_interval_seconds,
        latency_warn_ms=latency_warn_ms,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        telegram_message_id=telegram_message_id,
        status_title=status_title,
        show_protocol=show_protocol,
    )

