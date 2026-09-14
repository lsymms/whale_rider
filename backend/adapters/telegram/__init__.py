"""Telegram delivery adapter with explicit test/live delivery separation."""

from .adapter import DeliveryRejected, TelegramAdapter

__all__ = ["DeliveryRejected", "TelegramAdapter"]
