"""Razorpay adapter: subscriptions and webhook signature checks.

Rule 1: the ONLY file that talks to Razorpay. Keys come from settings
(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET, RAZORPAY_WEBHOOK_SECRET).

`verify_webhook_signature` is real, pure Python (no network): Razorpay signs the raw
webhook body with HMAC-SHA256 using the webhook secret, and we recompute and compare.
Webhook signature checking is on the must-pass list in docs/TESTING.md.

Only the interface and a Fake live here; no real network calls.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Protocol


def verify_webhook_signature(body: bytes, signature: str, secret: str) -> bool:
    """True only if `signature` is the HMAC-SHA256 hex digest of `body` under `secret`."""
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)  # constant-time compare


@dataclass(frozen=True)
class Subscription:
    subscription_id: str
    plan: str
    status: str


class PaymentGateway(Protocol):
    async def create_subscription(self, plan: str, user_ref: str) -> Subscription: ...
    async def cancel_subscription(self, subscription_id: str) -> Subscription: ...


class FakeRazorpay:
    def __init__(self) -> None:
        self.subscriptions: dict[str, Subscription] = {}

    async def create_subscription(self, plan: str, user_ref: str) -> Subscription:
        sub = Subscription(f"sub_fake_{len(self.subscriptions) + 1}", plan, "active")
        self.subscriptions[sub.subscription_id] = sub
        return sub

    async def cancel_subscription(self, subscription_id: str) -> Subscription:
        old = self.subscriptions[subscription_id]
        sub = Subscription(old.subscription_id, old.plan, "cancelled")
        self.subscriptions[subscription_id] = sub
        return sub
