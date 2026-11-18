"""The purchase confirmation a paying parent receives once a pupil's subscription is active.

Consumer Contracts Regulations 2013, reg. 16: confirmation of the contract on a durable medium,
with the pre-contract information (price, the 14-day cancellation right, the model form) and
the acknowledgement that Premium started at once at the parent's request. Stripe's receipt
carries none of that. Sent from the two places apply_subscription is called (the webhook and
the success page); confirmation_sent_at on the row makes it one email per subscription.
"""
import logging
import smtplib

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone

from config.mail import MailNotConfigured

from .models import Subscription

logger = logging.getLogger(__name__)

TEMPLATE_PREFIX = "billing/email/purchase_confirmation"


def _context(sub):
    from .views import format_price_gbp  # views imports this module; keep the import local

    pupil = sub.user
    period_end = timezone.localtime(sub.current_period_end) if sub.current_period_end else None
    return {
        "pupil_name": pupil.full_name or pupil.username,
        "price": format_price_gbp(settings.STRIPE_PRICE_GBP),
        "started": timezone.localdate().strftime("%-d %B %Y"),
        "renewal": period_end.strftime("%-d %B %Y") if period_end else None,
        "site_url": settings.SITE_URL.rstrip("/"),
    }


def send_purchase_confirmation(sub):
    """Render and send the email to the payer. Returns True if the backend accepted it.
    Non-fatal: a mail failure is logged (template name and exception class only) and
    reported as False; it must never take the webhook down."""
    context = _context(sub)
    subject = " ".join(render_to_string(f"{TEMPLATE_PREFIX}_subject.txt", context).split())
    body = render_to_string(f"{TEMPLATE_PREFIX}_message.txt", context)
    message = EmailMessage(subject, body, settings.DEFAULT_FROM_EMAIL, [sub.payer.email])
    try:
        message.send()
    except (MailNotConfigured, smtplib.SMTPException, OSError) as exc:
        logger.warning("email not sent: template=%s error=%s", TEMPLATE_PREFIX, type(exc).__name__)
        return False
    return True


def maybe_send_purchase_confirmation(sub):
    """The one entry point. Sends only when the subscription is ACTIVE, has a payer with an
    email, carries a Stripe subscription id and has not been confirmed before. Claims the
    row first (confirmation_sent_at) so a webhook and the success page racing on the same
    purchase cannot both send; a failed send releases the claim so the next event retries.
    Never touches status: apply_subscription is the single writer of subscription state."""
    if sub is None or sub.status != Subscription.Status.ACTIVE:
        return False
    if sub.payer is None or not sub.payer.email or not sub.stripe_subscription_id:
        return False
    if sub.confirmation_sent_at is not None:
        return False
    sub.confirmation_sent_at = timezone.now()
    sub.save(update_fields=["confirmation_sent_at"])
    if send_purchase_confirmation(sub):
        return True
    sub.confirmation_sent_at = None
    sub.save(update_fields=["confirmation_sent_at"])
    logger.warning("purchase confirmation not sent for subscription %s; will retry on the next event", sub.pk)
    return False
