import logging
import smtplib

from allauth.account.adapter import DefaultAccountAdapter
from allauth.core import context as allauth_context
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.shortcuts import redirect

from config.mail import MailNotConfigured

logger = logging.getLogger(__name__)


class AccountAdapter(DefaultAccountAdapter):
    """New sign-ups choose Parent or Tutor via SignupExtrasForm's
    ``account_type`` field; Parent is the default and pupils never
    self-register through this form (pupils are created by their parent,
    see accounts/views.py add_child)."""

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        account_type = getattr(form, "cleaned_data", {}).get("account_type")
        if account_type == user.Role.TUTOR:
            user.role = user.Role.TUTOR
        else:
            user.role = user.Role.PARENT
        if commit:
            user.save()
        return user

    def send_mail(self, template_prefix, email, context):
        """Every allauth email (password reset, unknown-account notice) passes through here.

        A send must never take a page down: with no SMTP configured the backend raises
        MailNotConfigured, and a real server can refuse or time out. Log the template name
        and the exception class only (never the address or the body) and tell the person."""
        try:
            super().send_mail(template_prefix, email, context)
        except (MailNotConfigured, smtplib.SMTPException, OSError) as exc:
            logger.warning("email not sent: template=%s error=%s", template_prefix, type(exc).__name__)
            request = allauth_context.request
            if request is not None:
                messages.warning(
                    request,
                    "We couldn't send that email just now. Please email revisorplus@gmail.com and we'll sort it out.",
                )


class SocialAdapter(DefaultSocialAccountAdapter):
    """Google sign-in is for parents and tutors only; pupils have no email
    and never self-register (see AccountAdapter). Two refusal cases share one
    lookup: the incoming login's own email addresses, and (if it is already
    connected) the account it is connected to."""

    def _is_pupil_login(self, sociallogin):
        from django.db.models import Q

        from accounts.models import User

        if sociallogin.is_existing and sociallogin.user.role == User.Role.STUDENT:
            return True
        emails = [e.email for e in sociallogin.email_addresses if e.email]
        if not emails:
            return False
        email_match = Q()
        for email in emails:
            email_match |= Q(email__iexact=email)
        return User.objects.filter(email_match, role=User.Role.STUDENT).exists()

    def pre_social_login(self, request, sociallogin):
        if self._is_pupil_login(sociallogin):
            messages.error(
                request, "Pupils sign in with the username their parent set up"
            )
            raise ImmediateHttpResponse(redirect("account_login"))

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        user.role = user.Role.PARENT
        if not user.full_name:
            name = data.get("name")
            if not name:
                first = data.get("first_name") or ""
                last = data.get("last_name") or ""
                name = f"{first} {last}".strip()
            if not name and user.email:
                name = user.email.split("@")[0]
            user.full_name = name
        return user

    def is_open_for_signup(self, request, sociallogin):
        return True


def user_display(user):
    """Name shown in allauth's messages and templates.

    Allauth defaults to the username, which here is derived from the email local
    part — so signing in greeted "nideesh" rather than "Nideesh". Wired up via
    ACCOUNT_USER_DISPLAY in settings.
    """
    return getattr(user, "full_name", "") or user.email
