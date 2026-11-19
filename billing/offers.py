"""The introductory offer: a Stripe promotion code looked up by its text and cached."""
import logging

import stripe
from django.conf import settings
from django.core.cache import cache

from .stripe_sync import _configure, as_dict

logger = logging.getLogger(__name__)
CACHE_SECONDS = 600


def lookup_promotion_code(code):
    """{id, code, amount_off_pence, first_month_price_pence, redeem_by, first_time_only} for an
    active 'once' GBP amount-off promotion code, else None (logged). Cached 10 minutes."""
    key = f"offer:{code.upper()}"
    cached = cache.get(key)
    if cached is not None:
        return cached or None
    found = _fetch(code)
    cache.set(key, found or False, CACHE_SECONDS)
    return found


def _coupon_of(promo):
    """The coupon dict of a promotion code, or None. The pinned API version nests it at
    promotion.coupon (expanded, or an id to retrieve); older versions put it at top-level coupon."""
    nested = as_dict(promo.get("promotion") or {})
    coupon = nested.get("coupon") if isinstance(nested, dict) else None
    if isinstance(coupon, str):
        coupon = stripe.Coupon.retrieve(coupon)
    coupon = as_dict(coupon) if coupon else None
    if not isinstance(coupon, dict):
        coupon = as_dict(promo.get("coupon"))
    return coupon if isinstance(coupon, dict) else None


def _fetch(code):
    _configure()
    try:
        result = as_dict(
            stripe.PromotionCode.list(code=code, active=True, limit=1, expand=["data.promotion.coupon"])
        )
        data = result.get("data") or []
        promo = as_dict(data[0]) if data else None
        coupon = _coupon_of(promo) if promo else None
    except stripe.error.StripeError as exc:
        logger.warning("offer lookup failed: code=%s error=%s", code, type(exc).__name__)
        return None
    if not data:
        logger.info("offer code unknown or inactive: %s", code)
        return None
    if not coupon:
        logger.warning("offer code %s has no coupon; ignored", code)
        return None
    if coupon.get("duration") != "once" or coupon.get("currency") != "gbp" or not coupon.get("amount_off"):
        logger.warning("offer code %s is not a one-off GBP amount-off coupon; ignored", code)
        return None
    amount_off = int(coupon["amount_off"])
    restrictions = as_dict(promo.get("restrictions") or {})
    return {
        "id": promo["id"],
        "code": promo.get("code") or code,
        "amount_off_pence": amount_off,
        "first_month_price_pence": max(int(settings.STRIPE_PRICE_GBP) - amount_off, 0),
        "redeem_by": coupon.get("redeem_by"),
        "first_time_only": bool(restrictions.get("first_time_transaction")),
    }
