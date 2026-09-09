from datetime import timedelta

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import Subscription


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
    from pages.views import landing_stats

    sub, _ = Subscription.objects.get_or_create(user=request.user)
    return render(request, "billing/pricing.html", {
        "price_gbp": format_price_gbp(settings.STRIPE_PRICE_GBP),
        "sub": sub,
        "stripe_ready": bool(settings.STRIPE_SECRET_KEY),
        # Counted, never typed: this list once advertised a question bank many
        # times larger than reality. It used to be shared with the landing page
        # so the two could not disagree; the landing redesign dropped its stats
        # card, so this is the only page showing these now.
        "stats": landing_stats(),
    })


@login_required
def checkout(request):
    # Demo fallback: if no Stripe keys are set, simulate a successful test payment.
    if not settings.STRIPE_SECRET_KEY:
        messages.info(request, "Stripe test keys not configured — simulating a successful payment.")
        return redirect("billing:success")

    stripe.api_key = settings.STRIPE_SECRET_KEY
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "gbp",
                "product_data": {"name": "RevisorPlus Premium (monthly)"},
                "unit_amount": int(settings.STRIPE_PRICE_GBP),
            },
            "quantity": 1,
        }],
        customer_email=request.user.email,
        success_url=request.build_absolute_uri("/billing/success/"),
        cancel_url=request.build_absolute_uri("/billing/cancel/"),
    )
    return redirect(session.url)


@login_required
def success(request):
    # Demo: mark active on return. Production would confirm via Stripe webhook.
    sub, _ = Subscription.objects.get_or_create(user=request.user)
    sub.status = Subscription.Status.ACTIVE
    sub.current_period_end = (timezone.now() + timedelta(days=30)).date()
    sub.save()
    messages.success(request, "Payment successful — Premium unlocked.")
    return render(request, "billing/success.html")


@login_required
def cancel(request):
    messages.warning(request, "Checkout cancelled.")
    return redirect("billing:pricing")
