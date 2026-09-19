"""
Checks Phase D of the Stripe/entitlements plan (docs/plans/2026-09-16-stripe-
subscriptions-and-google-auth.md): the Google sign-in button only shows up
when a provider is configured, the login form stays first and largest, the
"Connect Google" link on the parent and tutor pages, and the SocialAdapter
rules — pupils are refused, an existing adult is never auto-connected by
email, a logged-in adult can connect Google themselves, and a brand-new
Google login becomes a parent.

Run:  python main.py seed_demo
      python main.py shell < test_google.py

`main.py shell` exits 0 whatever this prints; CI greps for RESULT: ALL PASSED.
"""
from types import SimpleNamespace

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import Client, RequestFactory
from django.test.utils import setup_test_environment, teardown_test_environment
from django.urls import reverse

# Not running under Django's own test runner, so the template_rendered signal
# django.test.Client relies on for response.context is never connected unless
# this is called explicitly — without it every response.context is None.
setup_test_environment()

from accounts.adapter import SocialAdapter
from accounts.models import User
from allauth.account.models import EmailAddress
from allauth.core import context as allauth_context
from allauth.socialaccount.adapter import get_adapter as get_social_adapter
from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialAccount, SocialLogin

results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + (f" -- {detail}" if detail else ""))


if "testserver" not in settings.ALLOWED_HOSTS:
    settings.ALLOWED_HOSTS.append("testserver")

parent = User.objects.get(email="parent@revisorplus.test")
tutor = User.objects.get(email="tutor@revisorplus.test")

created_users = []
created_socialaccounts = []

DUMMY_PROVIDERS = {
    "google": {
        "APPS": [{"client_id": "dummy-client-id", "secret": "dummy-secret", "key": ""}],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    },
}


def _adapter_request(user=None):
    """A request with session and messages attached, the way the adapter's
    pre_social_login (messages.error) and allauth's own flows (session-backed
    pending signup) need — RequestFactory alone gives neither. `request.allauth`
    is what AccountMiddleware would normally set; some allauth internals
    (login stages) read it directly."""
    request = RequestFactory().get("/accounts/login/")
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    MessageMiddleware(lambda r: None).process_request(request)
    request.user = user or AnonymousUser()
    request.allauth = SimpleNamespace()
    return request


def _google_login(request, uid, emails=None):
    """A SocialLogin for a fake Google account. `sociallogin.provider` (a
    live Provider instance, distinct from the plain provider id string on
    the unsaved SocialAccount) is what allauth's own lookup() needs — it is
    normally set by the provider's own OAuth2 callback view, which nothing
    here drives, so it is looked up the same way that view would."""
    provider = get_social_adapter().get_provider(request, "google")
    return SocialLogin(
        account=SocialAccount(provider="google", uid=uid),
        email_addresses=emails or [],
        provider=provider,
    )


# ---------------------------------------------------------------------------
print("== login/signup pages: the button only appears with a configured provider ==")

settings.SOCIALACCOUNT_PROVIDERS = {}

client = Client(raise_request_exception=False)
r = client.get(reverse("account_login"))
html = r.content.decode()
check("providers unset: GET /accounts/login/ -> 200", r.status_code == 200)
check("... no 'Continue with Google'", "Continue with Google" not in html)
check("... no 'Parents and tutors'", "Parents and tutors" not in html)

r = client.get(reverse("account_signup"))
html = r.content.decode()
check("providers unset: GET /accounts/signup/ -> 200", r.status_code == 200)
check("... still has the account_type choice from Phase A", 'name="account_type"' in html)

settings.SOCIALACCOUNT_PROVIDERS = DUMMY_PROVIDERS

r = client.get(reverse("account_login"))
html = r.content.decode()
check("providers configured: GET /accounts/login/ -> 200", r.status_code == 200)
check("... has 'Continue with Google'", "Continue with Google" in html)
check("... has 'Parents and tutors'", "Parents and tutors" in html)
password_pos = html.find('name="password"')
google_pos = html.find("Parents and tutors")
check("... the password field comes before the Google block",
      password_pos != -1 and google_pos != -1 and password_pos < google_pos,
      f"password at {password_pos}, google block at {google_pos}")
check("... no leaked template comment syntax ('{#')", "{#" not in html)
check("... no leaked template comment syntax ('{% comment')", "{% comment" not in html)

r = client.get(reverse("account_signup"))
html = r.content.decode()
check("providers configured: GET /accounts/signup/ still has account_type",
      'name="account_type"' in html)
check("... no leaked template comment syntax ('{#')", "{#" not in html)
check("... no leaked template comment syntax ('{% comment')", "{% comment" not in html)

# ---------------------------------------------------------------------------
print("== 'Connect Google' link (step 36) ==")

parent_client = Client(raise_request_exception=False)
parent_client.force_login(parent)
r = parent_client.get(reverse("family:home"))
check("providers configured: parent /family/ has 'Connect Google'",
      "Connect Google" in r.content.decode())

tutor_client = Client(raise_request_exception=False)
tutor_client.force_login(tutor)
r = tutor_client.get(reverse("tutoring:dashboard"))
check("providers configured: tutor dashboard has 'Connect Google'",
      "Connect Google" in r.content.decode())

probe_account = SocialAccount.objects.create(
    user=parent, provider="google", uid="probe-connect-link", extra_data={},
)
created_socialaccounts.append(probe_account)
r = parent_client.get(reverse("family:home"))
check("once connected: parent /family/ no longer has 'Connect Google'",
      "Connect Google" not in r.content.decode())

settings.SOCIALACCOUNT_PROVIDERS = {}
r = tutor_client.get(reverse("tutoring:dashboard"))
check("providers unset: tutor dashboard has no 'Connect Google'",
      "Connect Google" not in r.content.decode())
r = parent_client.get(reverse("family:home"))
check("providers unset: parent /family/ has no 'Connect Google'",
      "Connect Google" not in r.content.decode())

probe_account.delete()
created_socialaccounts.remove(probe_account)
settings.SOCIALACCOUNT_PROVIDERS = DUMMY_PROVIDERS

# ---------------------------------------------------------------------------
print("== SocialAdapter: pupils are refused ==")

pupil = User(
    username="probe_google_pupil", email="probe-google-pupil@revisorplus.test",
    full_name="Probe Pupil", role=User.Role.STUDENT, parent=parent,
)
pupil.set_password("probeword12345")
pupil.save()
created_users.append(pupil)

adapter = SocialAdapter()
request = _adapter_request()
with allauth_context.request_context(request):
    pupil_login = _google_login(
        request, "probe-pupil-uid",
        emails=[EmailAddress(email=pupil.email, verified=True, primary=True)],
    )
    response = complete_social_login(request, pupil_login)
check("pupil email: complete_social_login returns a redirect",
      response is not None and response.status_code == 302, f"got {response}")
check("... redirected to the login page",
      response is not None and response.url == reverse("account_login"),
      f"got {getattr(response, 'url', None)}")
check("... no SocialAccount was created for the pupil",
      not SocialAccount.objects.filter(uid="probe-pupil-uid").exists())

# 1b: the SocialAccount is already connected to a pupil.
connected_pupil_account = SocialAccount.objects.create(
    user=pupil, provider="google", uid="probe-pupil-connected", extra_data={},
)
created_socialaccounts.append(connected_pupil_account)
request = _adapter_request()
with allauth_context.request_context(request):
    connected_login = _google_login(request, "probe-pupil-connected")
    response = complete_social_login(request, connected_login)
check("already-connected pupil account: also refused with a redirect to login",
      response is not None and response.status_code == 302
      and response.url == reverse("account_login"), f"got {response}")

# ---------------------------------------------------------------------------
print("== SocialAdapter: an existing adult is never auto-connected by email ==")

probe_request = _adapter_request()
with allauth_context.request_context(probe_request):
    tutor_login = _google_login(
        probe_request, "probe-tutor-uid",
        emails=[EmailAddress(email=tutor.email.upper(), verified=True, primary=True)],
    )
    pre_login_result = adapter.pre_social_login(probe_request, tutor_login)
check("pre_social_login does not raise for an unconnected tutor email",
      pre_login_result is None)

with allauth_context.request_context(probe_request):
    lookup_login = _google_login(
        probe_request, "probe-tutor-uid",
        emails=[EmailAddress(email=tutor.email.upper(), verified=True, primary=True)],
    )
    # A real provider callback always populates `.user` with a candidate
    # before handing the SocialLogin off, whether or not it turns out to be
    # a signup.
    lookup_login.user = User()
    lookup_login.user = adapter.populate_user(
        probe_request, lookup_login,
        {"email": tutor.email.upper(), "name": "Probe Tutor Duplicate"},
    )
    lookup_login.lookup()
check("after lookup(): is_existing is False (SOCIALACCOUNT_EMAIL_AUTHENTICATION is off)",
      lookup_login.is_existing is False)

users_before = User.objects.filter(email__iexact=tutor.email).count()
request = _adapter_request()
with allauth_context.request_context(request):
    response = complete_social_login(request, lookup_login)
check("complete_social_login does not log the tutor in",
      "_auth_user_id" not in request.session)
check("... and creates no SocialAccount",
      not SocialAccount.objects.filter(uid="probe-tutor-uid").exists())
check("... and creates no second user with that email",
      User.objects.filter(email__iexact=tutor.email).count() == users_before)

# ---------------------------------------------------------------------------
print("== SocialAdapter: a tutor connects Google from a logged-in session ==")

connect_request = _adapter_request(user=tutor)
with allauth_context.request_context(connect_request):
    connect_login = _google_login(connect_request, "probe-tutor-connect")
    connect_login.connect(connect_request, tutor)
tutor_social = SocialAccount.objects.filter(user=tutor, uid="probe-tutor-connect").first()
created_socialaccounts.append(tutor_social) if tutor_social else None
check("connecting from a logged-in session creates the SocialAccount",
      tutor_social is not None)
tutor.refresh_from_db()
check("... and the tutor's role is untouched", tutor.role == User.Role.TUTOR)

# ---------------------------------------------------------------------------
print("== SocialAdapter: a brand-new Google login becomes a parent ==")

new_email = "probe-google-new@example.com"
request = _adapter_request()
with allauth_context.request_context(request):
    new_login = _google_login(
        request, "probe-new-uid",
        emails=[EmailAddress(email=new_email, verified=True, primary=True)],
    )
    # Mirrors what a provider's `sociallogin_from_response` does before
    # handing the SocialLogin to process_signup: populate_user builds the
    # candidate User from the provider's data (here, just email + name)
    # ahead of the save.
    new_login.user = User()
    new_login.user = adapter.populate_user(
        request, new_login, {"email": new_email, "name": "Probe New Parent"},
    )
    response = complete_social_login(request, new_login)
new_user = User.objects.filter(email=new_email).first()
if new_user:
    created_users.append(new_user)
check("a brand-new Google email creates a User", new_user is not None)
check("... with role parent", new_user is not None and new_user.role == User.Role.PARENT)
check("... and full_name from Google's name",
      new_user is not None and new_user.full_name == "Probe New Parent",
      f"got {getattr(new_user, 'full_name', None)!r}")

# ---------------------------------------------------------------------------
# Cleanup.
for sa in created_socialaccounts:
    if sa and sa.pk:
        SocialAccount.objects.filter(pk=sa.pk).delete()
for u in created_users:
    User.objects.filter(pk=u.pk).delete()

teardown_test_environment()

print()
print("RESULT: ALL PASSED" if all(results) else f"RESULT: {results.count(False)} FAILED")
