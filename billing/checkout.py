"""One place that builds a Stripe Checkout Session, for the family-page checkout and the
offer funnel alike, so the two can never drift on mode, metadata or the idempotency key."""
import time

import stripe
from django.conf import settings

from .stripe_sync import _configure, ensure_customer


def create_checkout_session(request, parent, pupil, *, success_url, cancel_url,
                            promotion_code_id=None, create_customer=True):
    """`create_customer=True` (the family-page checkout) creates the Stripe Customer up
    front through ensure_customer, as before. The funnel passes False: Stripe creates the
    customer at payment time from `customer_email`, and offer_success saves the id."""
    _configure()
    params = dict(
        idempotency_key=f"checkout:{parent.id}:{pupil.id}:{int(time.time() // 600)}",
        mode="subscription",
        line_items=[{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
        client_reference_id=str(pupil.id),
        subscription_data={"metadata": {"pupil_id": str(pupil.id), "parent_id": str(parent.id)}},
        allow_promotion_codes=True,
        success_url=success_url,
        cancel_url=cancel_url,
    )
    if parent.stripe_customer_id or create_customer:
        params["customer"] = ensure_customer(parent)
    else:
        params["customer_email"] = parent.email
    if promotion_code_id:
        params["discounts"] = [{"promotion_code": promotion_code_id}]
        params.pop("allow_promotion_codes")  # Stripe rejects both together
    return stripe.checkout.Session.create(**params)
