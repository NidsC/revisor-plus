"""The offer funnel: an advert links to /offer/<code>/, the parent enters an email and ticks the
Terms, pays on Stripe with the promotion code applied and comes back logged in, with a
placeholder pupil to finish setting up. No password, no sign-up form; later sign-ins use
allauth's login-by-code.

The account exists (pending, unusable password) before payment so Stripe has a parent and a
pupil to attach the subscription to; offer_success clears the pending mark when the paid
session returns, and purge_pending_signups removes accounts that never got that far.
This module never writes a Subscription status: apply_subscription is the single writer.
"""
import calendar
import logging
import re
import uuid
from datetime import date, datetime, timezone as dt_timezone

import stripe
from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.consent import record_acceptance
from accounts.forms import AcceptTermsForm
from accounts.models import User
from accounts.views import create_placeholder_pupil
from pages.consent import consent_choice

from . import meta
from .checkout import create_checkout_session
from .emails import maybe_send_purchase_confirmation, send_welcome
from .entitlements import FREE_QUESTIONS_PER_PAPER
from .offers import lookup_promotion_code
from .status import stripe_ready
from .stripe_sync import _configure, apply_subscription, as_dict
from .views import format_price_gbp

logger = logging.getLogger(__name__)

START_LIMIT = 10
START_WINDOW_SECONDS = 60


def _one_month_on(day):
    """The same day next month, clamped to that month's last day."""
    year, month = (day.year, day.month + 1) if day.month < 12 else (day.year + 1, 1)
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _offer_ends(promo):
    """The coupon's redeem_by (Unix seconds) as a UK-time date, or None when it has no deadline."""
    redeem_by = promo["redeem_by"]
    if redeem_by is None:
        return None
    return timezone.localtime(datetime.fromtimestamp(redeem_by, tz=dt_timezone.utc)).strftime("%-d %B %Y")


def _countdown(ts):
    """Whole days, hours and minutes from now to a Unix timestamp (floored at 0), or None without one."""
    if ts is None:
        return None
    left = max(0, int(ts - timezone.now().timestamp()))
    return {"days": left // 86400, "hours": left // 3600 % 24, "mins": left // 60 % 60}


def _offer_context(code, promo, *, form_errors=(), email="", cancelled=False, login_url=None, meta_eid=""):
    return {
        "track_pixel": True,
        "meta_eid": meta_eid,
        "meta_offer": {"value": promo["first_month_price_pence"] / 100, "event_id": meta_eid},
        "code": code,
        "promo": promo,
        "first_month_price": format_price_gbp(promo["first_month_price_pence"]),
        "standard_price": format_price_gbp(settings.STRIPE_PRICE_GBP),
        "offer_ends": _offer_ends(promo),
        "offer_ends_ts": promo["redeem_by"],
        "offer_countdown": _countdown(promo["redeem_by"]),
        "standard_from": _one_month_on(timezone.localdate()).strftime("%-d %B %Y"),
        "form": AcceptTermsForm(),
        "form_errors": list(form_errors),
        "login_url": login_url,
        "email": email,
        "cancelled": cancelled,
    }


def _expired(request, code):
    return render(request, "billing/offer_expired.html", {
        "track_pixel": True,
        "code": code,
        "standard_price": format_price_gbp(settings.STRIPE_PRICE_GBP),
        "free_questions_per_paper": FREE_QUESTIONS_PER_PAPER,
    })


def _client_ip(request):
    """The funnel limit and allauth's login limit key on the same address."""
    return get_adapter().get_client_ip(request)


def _rate_limited(request):
    key = f"offer_start:{_client_ip(request)}"
    cache.add(key, 0, START_WINDOW_SECONDS)
    return cache.incr(key) > START_LIMIT


def _active_offer(code):
    """The promotion code's details, or None when payments are off or the code is not live."""
    return lookup_promotion_code(code) if stripe_ready() else None


def _already_signed_in(request):
    messages.info(request, "You're signed in already. Enter the offer code on the payment page.")
    return redirect("billing:pricing")


@require_GET
def offer_landing(request, code):
    if request.user.is_authenticated:
        return _already_signed_in(request)
    promo = _active_offer(code)
    if promo is None:
        return _expired(request, code)
    return render(request, "billing/offer.html",
                  _offer_context(code, promo, cancelled=request.GET.get("cancelled") == "1",
                                 meta_eid=uuid.uuid4().hex))


@require_POST
def offer_start(request, code):
    if _rate_limited(request):
        return render(request, "billing/offer_rate_limited.html", status=429)
    if request.user.is_authenticated:
        return _already_signed_in(request)
    promo = _active_offer(code)
    if promo is None:
        return _expired(request, code)

    # The browser's InitiateCheckout event id, kept across re-renders so the pixel and the server agree.
    meta_eid = request.POST.get("meta_eid", "")
    if not re.fullmatch(r"[0-9a-f]{32}", meta_eid):
        meta_eid = uuid.uuid4().hex

    def again(*errors, **extra):
        return render(request, "billing/offer.html",
                      _offer_context(code, promo, form_errors=errors, email=email, meta_eid=meta_eid, **extra))

    email = (request.POST.get("email") or "").strip().lower()
    errors = []
    try:
        forms.EmailField().clean(email)
    except ValidationError:
        errors.append("Enter a valid email address.")
    terms = AcceptTermsForm(request.POST)
    if not terms.is_valid():
        errors.extend(terms.errors["accept_terms"])
    if errors:
        return again(*errors)

    if User.objects.filter(email__iexact=email).exists() or EmailAddress.objects.filter(email__iexact=email).exists():
        return again("You already have an account. Log in and enter the code on the payment page.",
                     login_url=reverse("account_login"))

    with transaction.atomic():
        parent = User(username=get_adapter().generate_unique_username([email.split("@")[0], "parent"]),
                      email=email, full_name="", role=User.Role.PARENT,
                      offer_pending_since=timezone.now(), offer_code=code[:40])
        parent.set_unusable_password()
        if consent_choice(request) == "yes":
            parent.marketing_consent_at = timezone.now()
            parent.meta_fbp = request.COOKIES.get("_fbp", "")[:255]
            parent.meta_fbc = request.COOKIES.get("_fbc", "")[:255]
            parent.meta_client_ip = _client_ip(request)
            parent.meta_user_agent = request.META.get("HTTP_USER_AGENT", "")[:512]
            parent.meta_checkout_event_id = meta_eid
        record_acceptance(parent, commit=False)
        parent.save()
        EmailAddress.objects.create(user=parent, email=email, primary=True, verified=False)
        pupil = create_placeholder_pupil(parent)
        if parent.marketing_consent_at:
            meta.send_on_commit("InitiateCheckout", event_id=meta_eid, parent=parent,
                                value=promo["first_month_price_pence"] / 100,
                                source_url=request.build_absolute_uri(reverse("offer_landing", args=[code])))

    try:
        session = create_checkout_session(
            request, parent, pupil,
            success_url=request.build_absolute_uri(reverse("offer_success")) + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.build_absolute_uri(reverse("offer_landing", args=[code])) + "?cancelled=1",
            promotion_code_id=promo["id"],
            create_customer=False,
        )
        url = as_dict(session)["url"]
    except stripe.error.StripeError as exc:
        parent.delete()  # cascades the pupil, its Subscription and the EmailAddress
        logger.warning("offer_start: Stripe refused the session: %s", type(exc).__name__)
        return again("We couldn't start the payment just now. Please try again in a minute.")
    return redirect(url)


@require_GET
def offer_success(request):
    session_id = request.GET.get("session_id")
    if not session_id:
        raise Http404
    _configure()
    session = as_dict(stripe.checkout.Session.retrieve(session_id, expand=["subscription", "customer_details"]))

    reference = str(session.get("client_reference_id") or "")
    pupil = (User.objects.filter(pk=reference, role=User.Role.STUDENT).select_related("parent").first()
             if reference.isdigit() else None)
    parent = pupil.parent if pupil else None
    if parent is None:
        raise Http404
    if parent.offer_pending_since is None:  # a replay of a session that already logged someone in
        return redirect("family:home" if request.user.is_authenticated else "account_login")
    if session.get("payment_status") != "paid":
        raise Http404

    purchase_event = None
    with transaction.atomic():
        if session.get("subscription"):
            row = apply_subscription(as_dict(session["subscription"]), None)
            if row:
                maybe_send_purchase_confirmation(row)
                meta.queue_purchase(row, session, settings.SITE_URL)
                purchase_event = meta.browser_purchase_event(row, session)

        stripe_email = (as_dict(session.get("customer_details") or {}).get("email") or "").strip().lower()
        if stripe_email and stripe_email != (parent.email or "").lower():
            taken = (User.objects.exclude(pk=parent.pk).filter(email__iexact=stripe_email).exists()
                     or EmailAddress.objects.exclude(user=parent).filter(email__iexact=stripe_email).exists())
            if taken:
                logger.info("offer_success: Stripe email differs from the account email and is already taken; "
                            "kept the account email (parent %s)", parent.pk)
            else:
                parent.email = stripe_email
                EmailAddress.objects.filter(user=parent, primary=True).update(email=stripe_email)

        EmailAddress.objects.filter(user=parent, primary=True).update(verified=True)

        customer_id = session.get("customer")
        if isinstance(customer_id, str) and not parent.stripe_customer_id:
            parent.stripe_customer_id = customer_id

        parent.offer_pending_since = None
        parent.save()

    login(request, parent, backend="django.contrib.auth.backends.ModelBackend")
    if purchase_event:
        request.session["meta_events"] = [purchase_event]
    send_welcome(parent)
    messages.success(request, "Payment received. Your receipt is on its way by email.")
    return redirect("family:setup_child", pupil_id=pupil.id)
