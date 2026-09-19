"""Everything that talks to the Stripe API or turns a Stripe object into a
local `Subscription` row. `apply_subscription` is the single writer of
subscription state — see the plan's Maintenance Notes: a reviewer should
reject any PR that sets `Subscription.status` from anywhere else.
"""
import logging
from datetime import datetime, timezone as dt_timezone

import stripe
from django.conf import settings

from .models import Subscription

logger = logging.getLogger(__name__)


def as_dict(stripe_obj):
    """Normalise a Stripe SDK object (or an already-plain dict fixture) to a
    plain dict, recursively. stripe==15.3.1's StripeObject supports __getitem__
    but NOT .get() — verified in this venv, contrary to the assumption that
    both accessors work on either shape. Every Stripe response is converted
    to a dict at the point it leaves the SDK (construct_event, ..Session.
    retrieve, ..Subscription.retrieve), so apply_subscription and everything
    downstream can be written once, against plain dict access, and work for
    both a live response and a test fixture.
    """
    return stripe_obj.to_dict() if hasattr(stripe_obj, "to_dict") else stripe_obj


def _configure():
    """Read the key from settings at call time, never at import — so a key
    set after the process starts (or changed between tests) is always the
    one used."""
    stripe.api_key = settings.STRIPE_SECRET_KEY


def ensure_customer(parent) -> str:
    """Return the parent's Stripe Customer id, creating it once."""
    if parent.stripe_customer_id:
        return parent.stripe_customer_id
    _configure()
    customer = stripe.Customer.create(
        email=parent.email,
        name=parent.full_name or "",
        metadata={"user_id": parent.id},
    )
    parent.stripe_customer_id = customer["id"]
    parent.save(update_fields=["stripe_customer_id"])
    return parent.stripe_customer_id


# Stripe status -> local Subscription.Status. Unknown values (a future Stripe
# status this map hasn't been taught) are handled in apply_subscription: log
# and leave the row's status unchanged rather than guess.
_STATUS_MAP = {
    "active": Subscription.Status.ACTIVE,
    "trialing": Subscription.Status.ACTIVE,
    "past_due": Subscription.Status.PAST_DUE,
    "canceled": Subscription.Status.CANCELED,
    "unpaid": Subscription.Status.UNPAID,
    "incomplete": Subscription.Status.INCOMPLETE,
    "incomplete_expired": Subscription.Status.CANCELED,
    "paused": Subscription.Status.CANCELED,
}


def _period_end(stripe_sub):
    """Unix seconds -> aware UTC datetime, or None. Stripe API 2025+ moved
    current_period_end onto the subscription item; read that first and fall
    back to the top-level field some fixtures (and older API versions) use.
    Dict fixtures and Stripe objects both support .get, so this is written
    against dict-style access only and works for either."""
    items = stripe_sub.get("items") or {}
    data = items.get("data") or []
    raw = None
    if data:
        raw = data[0].get("current_period_end")
    if raw is None:
        raw = stripe_sub.get("current_period_end")
    if raw is None:
        return None
    return datetime.fromtimestamp(raw, tz=dt_timezone.utc)


def apply_subscription(stripe_sub, event_created=None):
    """The single writer of subscription state. `stripe_sub` is a Stripe
    Subscription object or an equivalent dict (a test fixture). Returns the
    updated Subscription row, or None if no pupil could be resolved.

    `event_created`, when given, is the Stripe event's `created` timestamp
    (aware datetime); the ordering guard [C-8] uses it so an out-of-order
    webhook delivery can never overwrite a newer state with an older one.
    The success-page path passes None and always applies, because a session
    retrieved live from Stripe is current by definition.
    """
    metadata = stripe_sub.get("metadata") or {}
    pupil_id = metadata.get("pupil_id")

    from accounts.models import User

    pupil = None
    if pupil_id:
        pupil = User.objects.filter(pk=pupil_id, role=User.Role.STUDENT).first()
    if pupil is None:
        row = Subscription.objects.filter(stripe_subscription_id=stripe_sub.get("id")).first()
        if row is not None:
            pupil = row.user

    if pupil is None:
        logger.warning(
            "apply_subscription: no pupil_id metadata and no matching local "
            "row for Stripe subscription %s — hand-made in the dashboard? "
            "Leaving no row changed.", stripe_sub.get("id"),
        )
        return None

    sub, _ = Subscription.objects.get_or_create(user=pupil)

    if event_created is not None and sub.last_event_created is not None \
            and sub.last_event_created > event_created:
        logger.info(
            "apply_subscription: stale event for subscription %s (event "
            "created %s, row already at %s) — skipped.",
            stripe_sub.get("id"), event_created, sub.last_event_created,
        )
        return sub

    stripe_status = stripe_sub.get("status")
    new_status = _STATUS_MAP.get(stripe_status)
    if new_status is None:
        logger.warning(
            "apply_subscription: unrecognised Stripe status %r for "
            "subscription %s — status left unchanged.",
            stripe_status, stripe_sub.get("id"),
        )
        new_status = sub.status

    parent_id = metadata.get("parent_id")
    payer = sub.payer
    if parent_id:
        payer = User.objects.filter(pk=parent_id, role=User.Role.PARENT).first() or sub.payer

    sub.status = new_status
    sub.stripe_subscription_id = stripe_sub.get("id") or sub.stripe_subscription_id
    sub.payer = payer
    sub.cancel_at_period_end = bool(stripe_sub.get("cancel_at_period_end"))
    sub.current_period_end = _period_end(stripe_sub)
    update_fields = [
        "status", "stripe_subscription_id", "payer", "cancel_at_period_end",
        "current_period_end", "updated_at",
    ]
    if event_created is not None:
        sub.last_event_created = event_created
        update_fields.append("last_event_created")
    sub.save(update_fields=update_fields)
    return sub
