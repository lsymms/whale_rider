"""Read-only, injectable Webull market-feed contracts."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping, Protocol, Sequence

from backend.domain.market import Journal, Provenance, SourceMode, normalize_execution


class StreamDisconnected(ConnectionError):
    pass


class StockStreamSession(Protocol):
    def receive(self, timeout_seconds: float) -> Mapping[str, Any] | None: ...
    def heartbeat(self) -> bool: ...
    def close(self) -> None: ...


class StockStreamFactory(Protocol):
    def __call__(self, symbols: Sequence[str]) -> StockStreamSession: ...


def _hash(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def normalize_webull_tick(payload: Mapping[str, Any], *, asset_type: str, received_at: datetime, source_mode: SourceMode, instrument_id: str | None = None, underlying: str | None = None) -> object:
    """Normalize only explicit tick fields; no quote is ever converted into a trade."""
    event_type = str(payload.get("event_type", payload.get("type", "execution"))).lower()
    if event_type not in {"execution", "trade"}:
        raise ValueError("Webull market payload is not an execution")
    event_id = payload.get("execution_id") or payload.get("event_id") or payload.get("id")
    provider_time = payload.get("event_time") or payload.get("timestamp") or payload.get("time")
    if isinstance(provider_time, (int, float)):
        provider_time = datetime.fromtimestamp(provider_time / (1000 if provider_time > 10_000_000_000 else 1), UTC).isoformat()
    canonical = {
        "instrument_id": instrument_id or payload.get("instrument_id") or payload.get("symbol"),
        "underlying": underlying or payload.get("underlying") or payload.get("symbol"),
        "asset_type": asset_type,
        "event_time": provider_time,
        "quantity": payload.get("quantity", payload.get("size", payload.get("volume"))),
        "price": payload.get("price"),
        "price_multiplier": payload.get("price_multiplier", payload.get("multiplier")),
    }
    identity_reliable = bool(payload.get("identity_reliable", False) and event_id)
    provenance = Provenance("webull", source_mode, received_at, received_at, _hash(payload), str(event_id) if event_id else None, identity_reliable)
    return normalize_execution(canonical, provenance)


@dataclass(frozen=True, slots=True)
class StreamRunReport:
    received_messages: int
    appended_events: int
    heartbeat_sent: bool
    reconnect_required: bool
    gaps_recorded: int


class StockTickStream:
    """Consumes finite batches so supervision owns reconnect timing and cancellation."""

    def __init__(self, factory: StockStreamFactory, journal: Journal, now: callable) -> None:
        self._factory, self._journal, self._now = factory, journal, now

    def consume(self, symbols: Sequence[str], *, max_messages: int, heartbeat_after_seconds: float = 15) -> StreamRunReport:
        if not symbols or max_messages < 1:
            raise ValueError("symbols and max_messages are required")
        session = self._factory(tuple(symbols))
        start = self._now()
        last_activity = start
        received = appended = gaps = 0
        heartbeat = False
        try:
            for _ in range(max_messages):
                try:
                    batch = session.receive(heartbeat_after_seconds)
                except StreamDisconnected:
                    end = self._now()
                    for symbol in symbols:
                        self._journal.record_gap(instrument_id=symbol, underlying=symbol, asset_type="stock", start=last_activity, end=end, reason="stream_disconnected", provenance=Provenance("webull", SourceMode.LIVE, None, end, "stream-disconnect"))
                        gaps += 1
                    return StreamRunReport(received, appended, heartbeat, True, gaps)
                if batch is None:
                    if (self._now() - last_activity).total_seconds() >= heartbeat_after_seconds:
                        heartbeat = True
                        if not session.heartbeat():
                            raise StreamDisconnected("heartbeat failed")
                    continue
                last_activity = self._now()
                received += 1
                events = batch.get("events", [batch])
                if not isinstance(events, list):
                    raise ValueError("stream batch events must be a list")
                for item in events:
                    if not isinstance(item, Mapping):
                        continue
                    try:
                        event = normalize_webull_tick(item, asset_type="stock", received_at=last_activity, source_mode=SourceMode.LIVE)
                    except ValueError:
                        continue
                    if self._journal.append(event)[0].value == "appended":
                        appended += 1
        except StreamDisconnected:
            end = self._now()
            for symbol in symbols:
                self._journal.record_gap(instrument_id=symbol, underlying=symbol, asset_type="stock", start=last_activity, end=end, reason="stream_heartbeat_failed", provenance=Provenance("webull", SourceMode.LIVE, None, end, "stream-heartbeat"))
                gaps += 1
            return StreamRunReport(received, appended, heartbeat, True, gaps)
        finally:
            session.close()
        return StreamRunReport(received, appended, heartbeat, False, gaps)
