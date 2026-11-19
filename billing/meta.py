"""Meta Conversions API: server-side twins of the browser pixel's three events.

InitiateCheckout (offer form submitted), Purchase (first payment succeeded) and Subscribe (first
renewal). Sent only when Meta is configured and the parent ticked "Accept" on the cookie banner
(User.marketing_consent_at). Best-effort: send_event never raises, is called on commit so a
rollback sends nothing and a slow response never holds a database lock, and is not retried.
Nothing here logs the token, the email or the payload.
"""
import hashlib
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Subscription

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 3


def hash_email(email):
    """Meta's normalisation: trimmed, lower-cased, SHA-256 hex."""
    return hashlib.sha256((email or "").strip().lower().encode("utf-8")).hexdigest()


def is_enabled():
    return bool(settings.META_PIXEL_ID and settings.META_CAPI_TOKEN)


def user_data_for(parent):
    data = {
        "em": [hash_email(parent.email)] if parent.email else "",
        "client_ip_address": parent.meta_client_ip or "",
        "client_user_agent": parent.meta_user_agent,
        "fbp": parent.meta_fbp,
        "fbc": parent.meta_fbc,
    }
    return {key: value for key, value in data.items() if value}


def send_event(name, *, event_id, parent, value=None, currency="GBP", source_url=""):
    """POST one event. Returns True when Meta answered 2xx; False when skipped or failed."""
    if not is_enabled() or parent is None or parent.marketing_consent_at is None:
        return False
    event = {
        "event_name": name,
        "event_time": int(time.time()),
        "event_id": event_id,
        "action_source": "website",
        "user_data": user_data_for(parent),
    }
    if source_url:
        event["event_source_url"] = source_url
    if value is not None:
        event["custom_data"] = {"currency": currency.upper(), "value": value}
    body = {"data": [event]}
    if settings.META_TEST_EVENT_CODE:
        body["test_event_code"] = settings.META_TEST_EVENT_CODE
    url = (f"https://graph.facebook.com/{settings.META_GRAPH_VERSION}/{settings.META_PIXEL_ID}/events"
           f"?{urllib.parse.urlencode({'access_token': settings.META_CAPI_TOKEN})}")
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = getattr(response, "status", 200)
    except urllib.error.HTTPError as exc:
        logger.warning("meta event failed name=%s id=%s error=%s", name, event_id, exc.code)
        return False
    except Exception as exc:  # best-effort measurement: never take a payment path down
        logger.warning("meta event failed name=%s id=%s error=%s", name, event_id, type(exc).__name__)
        return False
    logger.info("meta event sent name=%s id=%s status=%s", name, event_id, status)
    return 200 <= status < 300


def amount_of(obj, total_key):
    """(value, currency) from a Stripe checkout session (amount_total) or invoice (amount_paid),
    in pounds. A missing amount gives 0.0 rather than a guess."""
    pence = obj.get(total_key)
    value = round(pence / 100, 2) if isinstance(pence, (int, float)) else 0.0
    return value, str(obj.get("currency") or "gbp").upper()


def send_on_commit(name, **kwargs):
    """Queue send_event for after the current transaction commits (immediately outside one)."""
    transaction.on_commit(lambda: send_event(name, **kwargs))


def claim_and_send(sub, name, field, *, event_id, value, currency="GBP", source_url=""):
    """Claim `field` on the subscription row and queue the event, once. Call inside the same
    atomic block as the write. Returns True when this call made the claim."""
    if sub is None or sub.payer is None or getattr(sub, field) is not None:
        return False
    if not is_enabled() or sub.payer.marketing_consent_at is None:
        return False
    now = timezone.now()
    # A conditional UPDATE, so two requests racing on one row cannot both claim it.
    if not Subscription.objects.filter(pk=sub.pk, **{f"{field}__isnull": True}).update(**{field: now}):
        return False
    setattr(sub, field, now)
    send_on_commit(name, event_id=event_id, parent=sub.payer, value=value, currency=currency,
                   source_url=source_url)
    return True


def queue_purchase(sub, session, source_url=""):
    """Purchase for a paid checkout session, once per subscription. The amount is the session's
    amount_total, so a promotion code's first-month price is what Meta sees."""
    if sub is None or not sub.stripe_subscription_id or session.get("payment_status") not in (None, "paid"):
        return False
    value, currency = amount_of(session, "amount_total")
    return claim_and_send(sub, "Purchase", "meta_purchase_sent_at", event_id=f"purchase-{sub.stripe_subscription_id}",
                          value=value, currency=currency, source_url=source_url)


def browser_purchase_event(sub, session):
    """The pixel-side twin of queue_purchase (same event id, so Meta deduplicates), or None when
    the parent did not consent. Shown once on the set-up page via the session."""
    if sub is None or sub.payer is None or sub.payer.marketing_consent_at is None or not sub.stripe_subscription_id:
        return None
    value, currency = amount_of(session, "amount_total")
    return {"name": "Purchase", "params": {"currency": currency, "value": value},
            "event_id": f"purchase-{sub.stripe_subscription_id}"}


def queue_subscribe(sub, invoice, source_url=""):
    """Subscribe for the first renewal only (billing_reason subscription_cycle); later cycles see the claim."""
    if sub is None or invoice.get("billing_reason") != "subscription_cycle":
        return False
    value, currency = amount_of(invoice, "amount_paid")
    return claim_and_send(sub, "Subscribe", "meta_subscribe_sent_at", event_id=f"subscribe-{invoice.get('id')}",
                          value=value, currency=currency, source_url=source_url)
