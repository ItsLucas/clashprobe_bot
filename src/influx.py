from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from influxdb_client import InfluxDBClient


logger = logging.getLogger(__name__)


@dataclass
class NodePoint:
    alive: Optional[bool]
    latency_ms: Optional[int]
    alive_time: Optional[datetime]
    latency_time: Optional[datetime]
    protocol: Optional[str]

    @property
    def updated_at(self) -> Optional[datetime]:
        times = [t for t in [self.alive_time, self.latency_time] if t is not None]
        return max(times) if times else None


def fetch_probe_window(
    *,
    url: str,
    token: str,
    org: str,
    bucket: str,
    minutes: int,
    probe_node: Optional[str] = None,
) -> Dict[str, NodePoint]:
    """
    Query InfluxDB for the last N minutes of probe data and reduce by `name`.

    Returns a mapping: name -> NodePoint (latest alive/delay_ms and their timestamps).
    """

    node_filter = (
        f'  |> filter(fn: (r) => r["node"] == "{probe_node}")\n' if probe_node else ""
    )

    flux = f"""
from(bucket: "{bucket}")
  |> range(start: -{minutes}m)
  |> filter(fn: (r) => r["_measurement"] == "probe")
{node_filter}
  |> filter(fn: (r) =>
    r["_field"] == "alive" or r["_field"] == "delay_ms"
  )
  |> keep(columns: ["_time", "_value", "_field", "name", "protocol"])
"""

    result: Dict[str, NodePoint] = {}
    now = datetime.now(timezone.utc)

    client = InfluxDBClient(url=url, token=token, org=org)
    try:
        query_api = client.query_api()
        # Stream to avoid loading entire result into memory
        for record in query_api.query_stream(query=flux, org=org):
            try:
                name = record.values.get("name")
                if not name:
                    continue
                field = record.get_field()
                value = record.get_value()
                t: datetime = record.get_time()
                protocol = record.values.get("protocol")

                node = result.get(name)
                if node is None:
                    node = NodePoint(alive=None, latency_ms=None, alive_time=None, latency_time=None, protocol=protocol)
                    result[name] = node

                if field == "alive":
                    # pick the most recent alive value
                    if node.alive_time is None or (t and node.alive_time and t > node.alive_time):
                        node.alive = bool(value)
                        node.alive_time = t
                        # update protocol if present
                        if protocol:
                            node.protocol = protocol
                elif field == "delay_ms":
                    # pick the most recent latency value
                    if node.latency_time is None or (t and node.latency_time and t > node.latency_time):
                        try:
                            node.latency_ms = int(value)
                        except Exception:
                            # ignore non-int values
                            node.latency_ms = None
                        node.latency_time = t
                        if protocol:
                            node.protocol = protocol
            except Exception as e:  # per-record robustness
                logger.warning("Skipping malformed record: %s", e)
    finally:
        client.close()

    logger.info(
        "Fetched %d nodes from Influx window=%dm at %s",
        len(result),
        minutes,
        now.isoformat(),
    )
    return result
