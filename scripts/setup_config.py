from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    def load_dotenv(*args, **kwargs):  # type: ignore
        return False


ENV_PATH = Path(".env")


def prompt(text: str, default: Optional[str] = None, secret: bool = False) -> str:
    import getpass

    suffix = f" [default: {default}]" if default else ""
    if secret:
        val = getpass.getpass(f"{text}{suffix}: ")
    else:
        val = input(f"{text}{suffix}: ")
    if not val and default is not None:
        return default
    return val.strip()


def write_env(data: dict) -> None:
    lines = []
    ordered_keys = [
        "INFLUX_URL",
        "INFLUX_TOKEN",
        "INFLUX_ORG",
        "INFLUX_BUCKET",
        "TIME_RANGE_MINUTES",
        "POLL_INTERVAL_SECONDS",
        "LATENCY_WARN_MS",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "TELEGRAM_MESSAGE_ID",
        "STATUS_TITLE",
        "SHOW_PROTOCOL",
        "TZ",
    ]
    for k in ordered_keys:
        v = data.get(k)
        if v is None:
            continue
        if isinstance(v, str) and any(ch in v for ch in [' ', '#', '"', "'"]):
            # wrap in quotes if it has special chars
            v_out = '"' + v.replace('"', '\\"') + '"'
        else:
            v_out = str(v)
        lines.append(f"{k}={v_out}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {ENV_PATH.resolve()}")


async def test_telegram(token: str) -> bool:
    try:
        from telegram import Bot
        me = await Bot(token=token).get_me()
        print(f"Telegram OK: @{me.username} (id={me.id})")
        return True
    except Exception as e:
        print(f"Telegram test failed: {e}")
        return False


def test_influx(url: str, token: str, org: str) -> bool:
    try:
        from influxdb_client import InfluxDBClient
        with InfluxDBClient(url=url, token=token, org=org) as c:
            health = c.health()
        if getattr(health, "status", None) == "pass":
            print(f"InfluxDB OK: {url} (status=pass)")
            return True
        print(f"InfluxDB health not pass: {getattr(health, 'status', None)}")
        return False
    except Exception as e:
        print(f"InfluxDB test failed: {e}")
        return False


def main() -> None:
    print("Configure Telegram Status Page Bot (.env generator)\n")

    # Load existing env as defaults
    if ENV_PATH.exists():
        load_dotenv(dotenv_path=ENV_PATH, override=False)
        print(f"Found existing {ENV_PATH}. Values will be used as defaults.\n")

    # Gather values
    influx_url = prompt("InfluxDB URL", os.getenv("INFLUX_URL", "http://localhost:8086"))
    influx_org = prompt("InfluxDB Org", os.getenv("INFLUX_ORG", ""))
    influx_token = prompt("InfluxDB Token", os.getenv("INFLUX_TOKEN", ""), secret=True)
    influx_bucket = prompt("InfluxDB Bucket", os.getenv("INFLUX_BUCKET", "clashprobe"))

    time_range = prompt("Time range minutes", os.getenv("TIME_RANGE_MINUTES", "5"))
    poll_interval = prompt("Poll interval seconds", os.getenv("POLL_INTERVAL_SECONDS", "30"))
    latency_warn = prompt("Latency warn ms (optional)", os.getenv("LATENCY_WARN_MS", ""))

    tg_token = prompt("Telegram Bot Token", os.getenv("TELEGRAM_BOT_TOKEN", ""), secret=True)
    chat_id = prompt("Telegram Chat ID (optional)", os.getenv("TELEGRAM_CHAT_ID", ""))
    msg_id = prompt("Telegram Message ID (optional)", os.getenv("TELEGRAM_MESSAGE_ID", ""))

    status_title = prompt("Status title", os.getenv("STATUS_TITLE", "Network Status"))
    show_protocol = prompt("Show protocol (true/false)", os.getenv("SHOW_PROTOCOL", "true"))
    tz = prompt("Timezone (display)", os.getenv("TZ", "UTC"))

    data = {
        "INFLUX_URL": influx_url,
        "INFLUX_TOKEN": influx_token,
        "INFLUX_ORG": influx_org,
        "INFLUX_BUCKET": influx_bucket,
        "TIME_RANGE_MINUTES": time_range,
        "POLL_INTERVAL_SECONDS": poll_interval,
        "LATENCY_WARN_MS": latency_warn,
        "TELEGRAM_BOT_TOKEN": tg_token,
        "TELEGRAM_CHAT_ID": chat_id or None,
        "TELEGRAM_MESSAGE_ID": msg_id or None,
        "STATUS_TITLE": status_title,
        "SHOW_PROTOCOL": show_protocol,
        "TZ": tz,
    }

    write_env(data)

    # Offer tests
    try_test = prompt("Run connectivity tests now? (y/N)", "N").lower().startswith("y")
    if try_test:
        ok_influx = test_influx(influx_url, influx_token, influx_org)
        ok_tg = asyncio.run(test_telegram(tg_token))
        if ok_influx and ok_tg:
            print("\nAll checks passed. You can now run: make run")
        else:
            print("\nOne or more checks failed. Review your settings and try again.")
    else:
        print("\nSkipping tests. You can now run: make run or docker compose up")


if __name__ == "__main__":
    main()
