"""Which email backend this process uses, and the production fallback when SMTP is unset.

config/settings.py calls backend_for() so the three branches live in one place and can be
tested without re-importing settings:

  EMAIL_HOST set        -> Django's SMTP backend (a dedicated Google sending account with an
                           App Password; the values live in the Render dashboard, never here).
  unset, DEBUG on       -> the console backend: a local run prints the email, reset link
                           included, to the runserver terminal.
  unset, DEBUG off      -> UnconfiguredEmailBackend below. A send then raises
                           MailNotConfigured, which accounts.adapter.AccountAdapter.send_mail
                           turns into a logged warning and a polite message. Not the dummy
                           backend (it would tell a parent "email sent" when nothing was) and
                           not the console backend (it would print reset links into the Render
                           log).
"""
from django.core.mail.backends.base import BaseEmailBackend

SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
CONSOLE_BACKEND = "django.core.mail.backends.console.EmailBackend"
UNCONFIGURED_BACKEND = "config.mail.UnconfiguredEmailBackend"


class MailNotConfigured(RuntimeError):
    """A send was attempted but EMAIL_HOST is not set."""


def backend_for(email_host, debug):
    """The EMAIL_BACKEND dotted path for this environment."""
    if email_host:
        return SMTP_BACKEND
    if debug:
        return CONSOLE_BACKEND
    return UNCONFIGURED_BACKEND


class UnconfiguredEmailBackend(BaseEmailBackend):
    """Production backend while EMAIL_HOST is unset: a send is a loud, catchable failure.

    fail_silently is honoured the way Django's own backends honour it, so callers that ask
    for it (Django's AdminEmailHandler, send_mail(fail_silently=True)) get 0 sent rather
    than an exception inside a logging handler."""

    def send_messages(self, email_messages):
        if self.fail_silently:
            return 0
        raise MailNotConfigured("EMAIL_HOST is not set, so no email can be sent")
