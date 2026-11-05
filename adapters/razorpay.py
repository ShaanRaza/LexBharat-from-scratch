"""Razorpay payments. The ONLY file that talks to Razorpay.

Rule: ALWAYS verify the webhook signature. verify_webhook() is real, stdlib-only
HMAC-SHA256 (Razorpay signs the raw body with the webhook secret) and is tested.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Protocol

from adapters.guard import refuse_in_production
from core.settings import Settings


class BadSignature(Exception):
    pass


@dataclass(frozen=True)
class WebhookEvent:
    event: str
    payload: dict


class Payments(Protocol):
    def verify_webhook(self, raw_body: bytes, signature: str) -> WebhookEvent: ...


def _verify(secret: str, raw_body: bytes, signature: str) -> WebhookEvent:
    if not secret:
        raise BadSignature("webhook secret not configured")
    want = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(want, signature or ""):
        raise BadSignature("signature mismatch")
    d = json.loads(raw_body)
    return WebhookEvent(d.get("event", ""), d.get("payload", {}))


class RazorpayPayments:
    def __init__(self, settings: Settings):
        self._secret = settings.RAZORPAY_WEBHOOK_SECRET.get_secret_value()

    def verify_webhook(self, raw_body: bytes, signature: str) -> WebhookEvent:
        return _verify(self._secret, raw_body, signature)


class FakePayments:
    """Same check with a test secret, so signing logic is exercised in tests."""

    def __init__(self, secret: str = "test-secret"):  # noqa: S107
        refuse_in_production()
        self.secret = secret

    def sign(self, raw_body: bytes) -> str:
        return hmac.new(self.secret.encode(), raw_body, hashlib.sha256).hexdigest()

    def verify_webhook(self, raw_body: bytes, signature: str) -> WebhookEvent:
        return _verify(self.secret, raw_body, signature)
