from datetime import datetime, timezone, timedelta

from src.influx import NodePoint
from src.reducer import reduce_status, format_markdown_v2


def make_dt(minutes_ago: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)


def test_reduce_status_basic():
    data = {
        "NodeA": NodePoint(alive=True, latency_ms=80, alive_time=make_dt(1), latency_time=make_dt(1), protocol="Shadowsocks"),
        "NodeB": NodePoint(alive=False, latency_ms=None, alive_time=make_dt(2), latency_time=None, protocol=None),
        "NodeC": NodePoint(alive=None, latency_ms=None, alive_time=None, latency_time=None, protocol=None),
    }

    statuses = reduce_status(data, minutes=5, latency_warn_ms=100)

    assert statuses["NodeA"].up is True
    assert statuses["NodeA"].degraded is False
    assert statuses["NodeA"].latency_ms == 80

    assert statuses["NodeB"].up is False
    assert statuses["NodeB"].reason is None  # explicit false

    assert statuses["NodeC"].up is False
    assert statuses["NodeC"].reason == "no recent heartbeat"


def test_reduce_status_degraded():
    data = {
        "NodeX": NodePoint(alive=True, latency_ms=300, alive_time=make_dt(1), latency_time=make_dt(1), protocol=None),
    }
    statuses = reduce_status(data, minutes=5, latency_warn_ms=200)
    assert statuses["NodeX"].up is True
    assert statuses["NodeX"].degraded is True


def test_format_markdown_v2_ordering():
    data = {
        "B": NodePoint(alive=True, latency_ms=50, alive_time=make_dt(1), latency_time=make_dt(1), protocol=None),
        "A": NodePoint(alive=False, latency_ms=None, alive_time=make_dt(1), latency_time=None, protocol=None),
        "C": NodePoint(alive=True, latency_ms=500, alive_time=make_dt(1), latency_time=make_dt(1), protocol=None),
    }
    statuses = reduce_status(data, minutes=5, latency_warn_ms=200)
    text = format_markdown_v2("Network Status", statuses, minutes=5, show_protocol=True)
    # Ensure emojis appear in expected order: ✅ (B), ⚠️ (C), ❌ (A)
    bpos = text.find("✅ B")
    cpos = text.find("⚠️ C")
    apos = text.find("❌ A")
    assert -1 not in {bpos, cpos, apos}
    assert bpos < cpos < apos

