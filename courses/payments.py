"""Online payment through a hosted checkout page.

Flow: the student presses Pay -> a pending `Payment` is created -> we redirect to the provider's
checkout (PAYMENT_CHECKOUT_URL) with our reference -> the provider calls the webhook, signed with
HMAC-SHA256 (header X-Signature) -> the request is marked paid. Marking paid is idempotent.

A provider-specific adapter (Daftar Cash, Binance Pay...) only has to change `checkout_url()`
and how `parse_webhook()` reads the provider's payload.
"""
import hashlib
import hmac
import json
import secrets
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .models import EnrollmentRequest, Payment


def enabled():
    if not settings.PAYMENTS_ENABLED:
        return False
    if settings.PAYMENT_PROVIDER == "hosted":
        return bool(settings.PAYMENT_CHECKOUT_URL and settings.PAYMENT_WEBHOOK_SECRET)
    return settings.PAYMENT_PROVIDER == "mock" and settings.DEBUG


def create_payment(req):
    price = req.price
    if not price:
        return None
    return Payment.objects.create(
        request=req, provider=settings.PAYMENT_PROVIDER, reference="PAY" + secrets.token_hex(8).upper(),
        amount=price, currency=settings.PAYMENT_CURRENCY)


def checkout_url(payment, build_absolute):
    """Where to send the student to pay."""
    if payment.provider == "mock":
        return reverse("courses:pay_mock", args=[payment.reference])
    query = urlencode({
        "reference": payment.reference, "amount": payment.amount, "currency": payment.currency,
        "return_url": build_absolute(reverse("courses:checkout", args=[payment.request_id])),
        "webhook_url": build_absolute(reverse("courses:payment_webhook")),
    })
    sep = "&" if "?" in settings.PAYMENT_CHECKOUT_URL else "?"
    return f"{settings.PAYMENT_CHECKOUT_URL}{sep}{query}"


def sign(body: bytes) -> str:
    return hmac.new(settings.PAYMENT_WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()


def valid_signature(body: bytes, header: str) -> bool:
    if not settings.PAYMENT_WEBHOOK_SECRET or not header:
        return False
    return hmac.compare_digest(sign(body), header.strip())


def parse_webhook(body: bytes):
    """Returns (reference, paid: bool, payload) or None when the payload is unusable."""
    try:
        data = json.loads(body)
        reference = str(data["reference"])
    except (ValueError, KeyError, TypeError):
        return None
    paid = str(data.get("status", "")).lower() in ("paid", "success", "succeeded", "completed")
    return reference, paid, data


def mark_paid(payment, payload=None):
    """Idempotent: a repeated webhook changes nothing."""
    if payment.status == Payment.STATUS_PAID:
        return False
    payment.status = Payment.STATUS_PAID
    payment.paid_at = timezone.now()
    if payload is not None:
        payment.raw = payload
    payment.save()
    req = payment.request
    req.payment_status = EnrollmentRequest.PAYMENT_PAID
    req.payment_method = EnrollmentRequest.PAY_ONLINE
    req.save()  # post_save signal sends the thank-you email
    return True


def mark_failed(payment, payload=None):
    if payment.status == Payment.STATUS_PENDING:
        payment.status = Payment.STATUS_FAILED
        payment.raw = payload or {}
        payment.save()
