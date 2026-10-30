import ipaddress
import logging

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

logger = logging.getLogger(__name__)

# Every sFlow sample stands for ~sampling_interval real packets, so bytes are scaled by it.
_PIVOT = """
from(bucket: "{bucket}")
  |> range(start: {start}, stop: {stop})
  |> filter(fn: (r) => r._measurement == "{measurement}")
  |> filter(fn: (r) => {fields})
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> filter(fn: (r) => exists r.src and exists r.dst and exists r.l2_bytes and exists r.sampling_interval)
"""


def _fields(*names):
    return " or ".join(f'r._field == "{n}"' for n in names)


def _ip_literal(ip):
    # Validated before it is spliced into Flux.
    return f'"{ipaddress.ip_address(ip)}"'


class Influx:
    def __init__(self, config):
        self.config = config
        self._client = None

    def _api(self):
        if self._client is None:
            self._client = InfluxDBClient(
                url=self.config.influx_url,
                token=self.config.influx_token,
                org=self.config.influx_org,
                timeout=120_000,
            )
        return self._client

    def _base(self, start, stop, *fields):
        return _PIVOT.format(
            bucket=self.config.influx_bucket,
            measurement=self.config.netflow_measurement,
            start=start,
            stop=stop,
            fields=_fields("src", "dst", "l2_bytes", "sampling_interval", *fields),
        )

    def _query(self, flux):
        return self._api().query_api().query_stream(flux, org=self.config.influx_org)

    def scan(self, start, stop):
        """Yield (time, src, dst, src_mac, bytes) for every sFlow sample in [start, stop)."""
        flux = self._base(start.isoformat(), stop.isoformat(), "in_src_mac") + """
  |> map(fn: (r) => ({
      _time: r._time, src: r.src, dst: r.dst,
      mac: if exists r.in_src_mac then r.in_src_mac else "",
      bytes: float(v: r.l2_bytes) * float(v: r.sampling_interval)
  }))
"""
        for rec in self._query(flux):
            yield rec.get_time(), rec["src"], rec["dst"], rec["mac"], rec["bytes"]

    def traffic(self, ip, hours):
        """Bytes per hour sent and received by one IP."""
        lit = _ip_literal(ip)
        flux = self._base(f"-{int(hours)}h", "now()") + f"""
  |> filter(fn: (r) => r.src == {lit} or r.dst == {lit})
  |> map(fn: (r) => ({{
      _time: r._time,
      _value: float(v: r.l2_bytes) * float(v: r.sampling_interval),
      _field: if r.src == {lit} then "sent" else "received"
  }}))
  |> group(columns: ["_field"])
  |> aggregateWindow(every: 1h, fn: sum, createEmpty: true)
  |> fill(value: 0.0)
"""
        series = {"sent": [], "received": []}
        for rec in self._query(flux):
            series[rec.get_field()].append((rec.get_time().isoformat(), rec.get_value()))
        return series

    def peers(self, ip, hours, limit=15):
        lit = _ip_literal(ip)
        flux = self._base(f"-{int(hours)}h", "now()") + f"""
  |> filter(fn: (r) => r.src == {lit} or r.dst == {lit})
  |> map(fn: (r) => ({{
      peer: if r.src == {lit} then r.dst else r.src,
      sent: if r.src == {lit} then float(v: r.l2_bytes) * float(v: r.sampling_interval) else 0.0,
      received: if r.dst == {lit} then float(v: r.l2_bytes) * float(v: r.sampling_interval) else 0.0
  }}))
  |> group(columns: ["peer"])
  |> reduce(identity: {{sent: 0.0, received: 0.0}}, fn: (r, accumulator) => ({{
      sent: accumulator.sent + r.sent, received: accumulator.received + r.received
  }}))
  |> group()
  |> map(fn: (r) => ({{ r with total: r.sent + r.received }}))
  |> sort(columns: ["total"], desc: true)
  |> limit(n: {int(limit)})
"""
        return [
            {"peer": r["peer"], "sent": r["sent"], "received": r["received"], "total": r["total"]}
            for r in self._query(flux)
        ]

    def ports(self, ip, hours, limit=10):
        # The lower of the two ports is almost always the service; the other is an ephemeral client port.
        lit = _ip_literal(ip)
        flux = self._base(f"-{int(hours)}h", "now()", "src_port", "dst_port") + f"""
  |> filter(fn: (r) => (r.src == {lit} or r.dst == {lit}) and exists r.src_port and exists r.dst_port)
  |> map(fn: (r) => ({{
      port: if r.src_port < r.dst_port then r.src_port else r.dst_port,
      bytes: float(v: r.l2_bytes) * float(v: r.sampling_interval)
  }}))
  |> group(columns: ["port"])
  |> sum(column: "bytes")
  |> group()
  |> sort(columns: ["bytes"], desc: true)
  |> limit(n: {int(limit)})
"""
        return [{"port": r["port"], "bytes": r["bytes"]} for r in self._query(flux)]

    def write_labels(self, labels):
        """labels: iterable of dicts with ip, name, kind, source, owner, location."""
        points = [
            Point(self.config.labels_measurement)
            .tag("ip", l["ip"])
            .field("name", l["name"])
            .field("display", f'{l["name"]} ({l["ip"]})')
            .field("kind", l["kind"] or "")
            .field("source", l["source"] or "")
            .field("owner", l["owner"] or "")
            .field("location", l["location"] or "")
            .field("mac", l.get("mac") or "")
            for l in labels
        ]
        if not points:
            return 0
        with self._api().write_api(write_options=SYNCHRONOUS) as writer:
            writer.write(bucket=self.config.influx_bucket, org=self.config.influx_org, record=points)
        return len(points)
