"""One-step delivery worker; scheduling and process supervision live above this layer."""
from __future__ import annotations

from datetime import datetime

from backend.adapters.telegram import DeliveryRejected, TelegramAdapter
from backend.domain.notifications import DurableOutbox, Notification


class DeliveryWorker:
    def __init__(self, outbox: DurableOutbox, telegram: TelegramAdapter) -> None:
        self._outbox = outbox
        self._telegram = telegram

    def deliver_one(self, now: datetime) -> Notification | None:
        item = self._outbox.lease_next(now)
        if item is None:
            return None
        try:
            message_id = self._telegram.deliver(item)
        except DeliveryRejected as error:
            return self._outbox.mark_failure(item.notification_id, "permanent", str(error), now)
        except TimeoutError as error:
            return self._outbox.mark_failure(item.notification_id, "timeout_after_send", str(error), now)
        except OSError as error:
            return self._outbox.mark_failure(item.notification_id, "transient", str(error), now)
        return self._outbox.mark_sent(item.notification_id, message_id)
