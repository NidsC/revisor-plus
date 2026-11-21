"""Refer a friend: a paying parent's personal code, and the credit they earn when a friend subscribes.

A referral code is a Stripe promotion code on the shared referral coupon. When a friend's first
checkout carries it, the referrer's Stripe customer balance is credited one month at the standard
price, and the credit is reversed if the friend's payment is refunded. Nothing here writes
Subscription.status: apply_subscription stays the single writer of subscription state.
"""
import logging
import secrets
from datetime import timedelta

import stripe
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .emails import _send_plain
from .models import Referral, ReferralReward, Subscription
from .stripe_sync import _configure, as_dict

logger = logging.getLogger(__name__)

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
CREDIT_EMAIL_PREFIX = "billing/email/referral_credit"
CREDIT_DESCRIPTION = "Refer-a-friend credit: a friend subscribed to RevisorPlus"
REVERSAL_DESCRIPTION = "Refer-a-friend credit reversed: the referred payment was refunded"
GMAIL_DOMAINS = ("gmail.com", "googlemail.com")
MAX_CODE_ATTEMPTS = 5


def generate_code():
    return "RP-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


def is_eligible_referrer(parent):
    return bool(
        settings.REFERRAL_ENABLED
        and parent.is_parent
        and Subscription.objects.filter(payer=parent, status=Subscription.Status.ACTIVE).exists()
    )


def ensure_referral(parent):
    """The parent's Referral, creating the row and the Stripe promotion code on first use.
    None when the parent is not eligible or Stripe refused; no row is written then."""
    existing = Referral.objects.filter(referrer=parent).first()
    if existing is not None:
        return existing
    if not is_eligible_referrer(parent):
        return None

    _configure()
    for _ in range(MAX_CODE_ATTEMPTS):
        code = generate_code()
        if Referral.objects.filter(code=code).exists():
            continue
        try:
            promo = as_dict(stripe.PromotionCode.create(
                promotion={"type": "coupon", "coupon": settings.STRIPE_REFERRAL_COUPON_ID},
                code=code,
                restrictions={"first_time_transaction": True},
                metadata={"referrer_id": str(parent.id), "kind": "referral"},
                idempotency_key=f"referral-code:{parent.id}:{code}",
            ))
        except stripe.error.StripeError as exc:
            logger.warning("referral code not created: parent=%s error=%s", parent.pk, type(exc).__name__)
            return None
        try:
            with transaction.atomic():
                return Referral.objects.create(
                    referrer=parent, code=code, stripe_promotion_code_id=promo["id"],
                )
        except IntegrityError:  # a concurrent request created this parent's row first
            return Referral.objects.filter(referrer=parent).first()
    return None


def normalised_email(email):
    """Lower-cased, with a +suffix dropped from the local part (and dots too for Gmail), so
    `j.ane+rp@gmail.com` and `jane@gmail.com` compare equal."""
    email = (email or "").strip().lower()
    local, sep, domain = email.rpartition("@")
    if not sep:
        return email
    local = local.split("+", 1)[0]
    if domain in GMAIL_DOMAINS:
        local = local.replace(".", "")
    return f"{local}@{domain}"


def _promotion_code_id(session):
    from .views import _id_of  # views imports this module; keep the import local

    if not isinstance(session, dict):
        return None
    discounts = session.get("discounts") or []
    if not discounts or not isinstance(discounts[0], dict):
        return None
    return _id_of(discounts[0].get("promotion_code"))


def _is_self_referral(payer, referrer):
    if payer is None:
        return False
    if payer.pk == referrer.pk:
        return True
    payer_email = normalised_email(payer.email)
    return bool(payer_email) and payer_email == normalised_email(referrer.email)


def _decide(referral, payer):
    """The (status, reason) before any money moves. The first failing reason wins."""
    referrer = referral.referrer
    if _is_self_referral(payer, referrer):
        return ReferralReward.Status.REJECTED, "self-referral"
    if not is_eligible_referrer(referrer):
        return ReferralReward.Status.REJECTED, "referrer not subscribed"
    if not referral.active:
        return ReferralReward.Status.REJECTED, "code inactive"
    if not referrer.stripe_customer_id:
        return ReferralReward.Status.REJECTED, "referrer has no Stripe customer"
    granted = referral.rewards.filter(
        status=ReferralReward.Status.GRANTED,
        created_at__gte=timezone.now() - timedelta(days=365),
    ).count()
    if granted >= settings.REFERRAL_CAP_PER_YEAR:
        return ReferralReward.Status.CAPPED, f"{settings.REFERRAL_CAP_PER_YEAR} in 12 months"
    return ReferralReward.Status.GRANTED, ""


def _resolve(referral, payer, sub_id):
    """Decide, and for a grant post the credit. Returns (status, reason, amount_pence, txn_id).
    A Stripe error becomes FAILED (class name only) so the webhook still answers 200."""
    status, reason = _decide(referral, payer)
    if status != ReferralReward.Status.GRANTED:
        return status, reason, 0, ""
    referrer = referral.referrer
    amount = int(settings.STRIPE_PRICE_GBP)
    _configure()
    try:
        txn = as_dict(stripe.Customer.create_balance_transaction(
            referrer.stripe_customer_id,
            amount=-amount,
            currency="gbp",
            description=CREDIT_DESCRIPTION,
            metadata={"kind": "referral_credit", "referred_subscription": sub_id,
                      "referrer_id": str(referrer.pk)},
            idempotency_key=f"referral-credit:{sub_id}",
        ))
    except stripe.error.StripeError as exc:
        logger.warning("referral credit failed: sub=%s error=%s", sub_id, type(exc).__name__)
        return ReferralReward.Status.FAILED, type(exc).__name__[:120], 0, ""
    return ReferralReward.Status.GRANTED, "", amount, txn["id"]


def _send_credit_email(referral, amount_pence):
    from .views import format_price_gbp  # views imports this module; keep the import local

    if not referral.referrer.email:
        return False
    return _send_plain(CREDIT_EMAIL_PREFIX, referral.referrer.email, {
        "amount": format_price_gbp(amount_pence),
        "code": referral.code,
        "link": f"{settings.SITE_URL.rstrip('/')}/offer/{referral.code}/",
    })


def grant_for_session(sub_row, session):
    """Decide and record the reward for a paid checkout session. Called inside the caller's
    atomic block, directly after meta.queue_purchase; the Referral row lock serialises the
    webhook and the success page. Returns the ReferralReward row or None."""
    if not settings.REFERRAL_ENABLED or sub_row is None:
        return None
    if sub_row.status != Subscription.Status.ACTIVE or not sub_row.stripe_subscription_id:
        return None
    payer = sub_row.payer
    if payer is None:
        return None
    promo_id = _promotion_code_id(session)
    if not promo_id:
        return None

    referral = (
        Referral.objects.select_for_update().select_related("referrer")
        .filter(stripe_promotion_code_id=promo_id).first()
    )
    if referral is None:  # FIRSTMONTH499 or an unknown code
        return None
    sub_id = sub_row.stripe_subscription_id
    existing = ReferralReward.objects.filter(stripe_subscription_id=sub_id).first()
    if existing is not None:
        return existing

    status, reason, amount, txn_id = _resolve(referral, payer, sub_id)
    reward = ReferralReward.objects.create(
        referral=referral, referred_parent=payer, stripe_subscription_id=sub_id,
        status=status, reason=reason, amount_pence=amount, stripe_balance_txn_id=txn_id,
    )
    if status == ReferralReward.Status.GRANTED:
        _send_credit_email(referral, amount)
    return reward


def retry_failed(reward):
    """Admin: re-run the decision and the credit for a FAILED row, in place. The idempotency key
    is the same, so a credit that did land cannot land twice."""
    with transaction.atomic():
        locked = Referral.objects.select_for_update().select_related("referrer").get(pk=reward.referral_id)
        reward = ReferralReward.objects.get(pk=reward.pk)
        if reward.status != ReferralReward.Status.FAILED:
            return reward
        status, reason, amount, txn_id = _resolve(locked, reward.referred_parent, reward.stripe_subscription_id)
        reward.status = status
        reward.reason = reason
        reward.amount_pence = amount
        reward.stripe_balance_txn_id = txn_id
        reward.save(update_fields=["status", "reason", "amount_pence", "stripe_balance_txn_id"])
        if status == ReferralReward.Status.GRANTED:
            _send_credit_email(locked, amount)
    return reward


def reverse_reward(reward):
    """Take back a GRANTED credit (a positive balance transaction). Must run inside an atomic
    block. Returns the reward when reversed, else None; a Stripe error leaves it GRANTED."""
    reward = (
        ReferralReward.objects.select_for_update().select_related("referral__referrer")
        .filter(pk=reward.pk, status=ReferralReward.Status.GRANTED).first()
    )
    if reward is None:
        return None
    referrer = reward.referral.referrer
    sub_id = reward.stripe_subscription_id
    _configure()
    try:
        txn = as_dict(stripe.Customer.create_balance_transaction(
            referrer.stripe_customer_id,
            amount=reward.amount_pence,
            currency="gbp",
            description=REVERSAL_DESCRIPTION,
            metadata={"kind": "referral_credit_reversal", "referred_subscription": sub_id,
                      "referrer_id": str(referrer.pk)},
            idempotency_key=f"referral-reversal:{sub_id}",
        ))
    except stripe.error.StripeError as exc:
        logger.warning("referral reversal failed: sub=%s error=%s", sub_id, type(exc).__name__)
        return None
    reward.status = ReferralReward.Status.REVERSED
    reward.reversed_at = timezone.now()
    reward.stripe_reversal_txn_id = txn["id"]
    reward.save(update_fields=["status", "reversed_at", "stripe_reversal_txn_id"])
    return reward


def reverse_for_subscription(sub_row):
    """Called from the webhook on charge.refunded, after apply_subscription."""
    if sub_row is None or not sub_row.stripe_subscription_id:
        return None
    reward = ReferralReward.objects.filter(
        stripe_subscription_id=sub_row.stripe_subscription_id,
        status=ReferralReward.Status.GRANTED,
    ).first()
    return reverse_reward(reward) if reward is not None else None
