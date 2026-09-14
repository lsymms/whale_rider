"""Telegram adapter. Network transport is injected so the domain stays testable."""
from __future__ import annotations

from collections.abc import Callable

from backend.domain.notifications import DeliveryKind, Notification


class DeliveryRejected(PermissionError):
    """Raised before a transport call when delivery policy rejects a message."""


TelegramTransport = Callable[[str, str], str]


class TelegramAdapter:
    def __init__(self, transport: TelegramTransport, *, test_destination_id: str, test_delivery_enabled: bool, live_delivery_enabled: bool) -> None:
        self._transport = transport
        self._test_destination_id = test_destination_id
        self._test_delivery_enabled = test_delivery_enabled
        self._live_delivery_enabled = live_delivery_enabled

    def deliver(self, notification: Notification) -> str:
        if notification.kind is DeliveryKind.TEST:
            if not self._test_delivery_enabled or notification.destination_id != self._test_destination_id:
                raise DeliveryRejected("TEST delivery requires the configured test destination and explicit enablement")
        elif not self._live_delivery_enabled:
            raise DeliveryRejected("live Telegram alert delivery is disabled")
        return self._transport(notification.destination_id, notification.text)
