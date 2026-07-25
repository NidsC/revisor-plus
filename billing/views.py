from datetime import timedelta

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import Subscription


@login_required
def pricing(request):
    sub, _ = Subscription.objects.get_or_create(user=request.user)
    return render(request, "billing/pricing.html", {
        "price_gbp": int(settings.STRIPE_PRICE_GBP) / 100,
        "sub": sub,
        "stripe_ready": bool(settings.STRIPE_SECRET_KEY),
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
                "product_data": {"name": "Med-revisor Premium (monthly)"},
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
