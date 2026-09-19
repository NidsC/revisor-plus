import logging
from datetime import datetime, timezone as dt_timezone

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import User
from accounts.views import _owned_child, _require_parent

from .models import StripeEvent, Subscription
from .status import plan_status, stripe_ready
from .stripe_sync import _configure, apply_subscription, as_dict, ensure_customer

logger = logging.getLogger(__name__)


def format_price_gbp(pence):
    """Render a price in pence as "£29" or "£29.99".

    STRIPE_PRICE_GBP is pence, and dividing it by 100 for the template put
    "£29.0" on the page — Django renders a float, not money. Whole pounds drop
    the decimals; anything with pence keeps both digits.
    """
    pounds, remainder = divmod(int(pence), 100)
    return f"£{pounds}" if remainder == 0 else f"£{pounds}.{remainder:02d}"


@login_required
def pricing(request):
    """The parent-facing plan page: per-child subscribe buttons for a
    parent, price and features (no buttons) for a pupil or tutor. Does NOT
    create a Subscription row for whoever is looking — every pupil already
    gets one at creation (accounts.views.add_child, seed_demo); a pupil or
    tutor viewing this page owns no Subscription of their own.
    """
    from pages.views import landing_stats

    children = []
    if request.user.is_parent:
        children = [
            {"pupil": pupil, "status": plan_status(getattr(pupil, "subscription", None))}
            for pupil in User.objects.filter(role=User.Role.STUDENT, parent=request.user)
            .select_related("subscription")
            .order_by("full_name", "username")
        ]

    return render(request, "billing/pricing.html", {
        "price_gbp": format_price_gbp(settings.STRIPE_PRICE_GBP),
        "children": children,
        "stripe_ready": stripe_ready(),
        # Counted, never typed: this list once advertised a question bank many
        # times larger than reality. It used to be shared with the landing page
        # so the two could not disagree; the landing redesign dropped its stats
        # card, so this is the only page showing these now.
        "stats": landing_stats(),
    })


@login_required
@require_POST
def checkout(request):
    # _owned_child enforces parent-only and same-parent ownership in one call.
    pupil = _owned_child(request, request.POST.get("pupil_id"))

    sub = Subscription.objects.filter(user=pupil).first()
    if sub and sub.status in (Subscription.Status.ACTIVE, Subscription.Status.PAST_DUE):
        messages.info(request, f"{pupil.full_name or pupil.username} already has Premium.")
        return redirect("family:child", pupil_id=pupil.id)

    if not stripe_ready():
        messages.error(request, "Payments are not configured.")
        return redirect("family:child", pupil_id=pupil.id)

    _configure()
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=ensure_customer(request.user),
        line_items=[{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
        client_reference_id=str(pupil.id),
        subscription_data={
            "metadata": {"pupil_id": str(pupil.id), "parent_id": str(request.user.id)},
        },
        success_url=request.build_absolute_uri(reverse("billing:success")) + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=request.build_absolute_uri(reverse("family:child", args=[pupil.id])),
    )
    return redirect(session.url)


@login_required
def success(request):
    """No status write of its own — apply_subscription (the single writer)
    does that. Authoritative because this reads the session live from Stripe
    with the secret key, not from anything the client supplied; the webhook
    remains the source for every later change.
    """
    _require_parent(request)

    session_id = request.GET.get("session_id")
    if not session_id:
        messages.info(request, "No checkout session to confirm.")
        return redirect("family:home")

    _configure()
    session = as_dict(stripe.checkout.Session.retrieve(session_id, expand=["subscription"]))
    if session.get("customer") != request.user.stripe_customer_id:
        raise PermissionDenied("This checkout session does not belong to you.")

    sub_row = None
    stripe_sub = session.get("subscription")
    if stripe_sub:
        sub_row = apply_subscription(stripe_sub, None)

    pupil = sub_row.user if sub_row else None
    if pupil is None:
        client_reference_id = session.get("client_reference_id")
        if client_reference_id:
            pupil = User.objects.filter(pk=client_reference_id, role=User.Role.STUDENT).first()

    return render(request, "billing/success.html", {
        "pupil": pupil,
        "pupil_name": (pupil.full_name or pupil.username) if pupil else None,
    })


@login_required
def cancel(request):
    messages.warning(request, "Checkout cancelled.")
    return redirect("family:home")


def _resolve_event_subscription(event):
    """The one Stripe object to apply for this event, retrieving it from the
    API when the event only carries an id — shared by checkout.session.
    completed and the invoice events so the retrieve-then-apply sequence
    exists in exactly one place. Returns None for an event type with nothing
    to apply (unknown types, or an invoice/session with no subscription)."""
    etype = event["type"]
    obj = event["data"]["object"]

    if etype == "checkout.session.completed":
        subscription_id = obj.get("subscription")
    elif etype.startswith("customer.subscription."):
        return obj
    elif etype in ("invoice.paid", "invoice.payment_failed"):
        subscription_id = obj.get("subscription")
    else:
        return None

    if not subscription_id:
        return None
    _configure()
    return as_dict(stripe.Subscription.retrieve(subscription_id))


@csrf_exempt
@require_POST
def webhook(request):
    try:
        event = as_dict(stripe.Webhook.construct_event(
            request.body,
            request.headers.get("Stripe-Signature", ""),
            settings.STRIPE_WEBHOOK_SECRET,
        ))
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)

    try:
        with transaction.atomic():
            already_processed = StripeEvent.objects.select_for_update().filter(
                event_id=event["id"], processed_at__isnull=False,
            ).exists()
            if already_processed:
                return HttpResponse(status=200)

            stripe_sub = _resolve_event_subscription(event)
            if stripe_sub is not None:
                event_created = datetime.fromtimestamp(event["created"], tz=dt_timezone.utc)
                apply_subscription(stripe_sub, event_created)

            StripeEvent.objects.update_or_create(
                event_id=event["id"],
                defaults={"type": event["type"], "processed_at": timezone.now()},
            )
    except Exception:
        logger.exception("webhook: failed applying event %s (%s)", event.get("id"), event.get("type"))
        return HttpResponse(status=500)

    return HttpResponse(status=200)


@login_required
@require_POST
def portal(request):
    _require_parent(request)
    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, "Payments are not configured.")
        return redirect("family:home")

    _configure()
    session = stripe.billing_portal.Session.create(
        customer=ensure_customer(request.user),
        return_url=request.build_absolute_uri(reverse("family:home")),
    )
    return redirect(session.url)
