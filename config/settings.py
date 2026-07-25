"""
Django settings for Med-revisor (demo build).

Lean demo runtime: SQLite + runserver, no external services required.
App structure mirrors the production architecture doc so it ports directly
onto cookiecutter-django + PostgreSQL for the real build.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Core -----------------------------------------------------------------
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "demo-insecure-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
RENDER_HOST = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)

# Needed for POST/login to work behind Render's HTTPS proxy
CSRF_TRUSTED_ORIGINS = [f"https://{RENDER_HOST}"] if RENDER_HOST else []
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- Applications ---------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # third-party
    "allauth",
    "allauth.account",
    # local
    "accounts",
    "catalog",
    "practice",
    "tutoring",
    "assignments",
    "billing",
    "pages",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "billing.context_processors.subscription_flags",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Database (local: SQLite; Render: Postgres via DATABASE_URL) ----------
import dj_database_url  # noqa: E402

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}

# --- Auth -----------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

SITE_ID = 1

# allauth (modern 65.x API)
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"  # demo: instant login, no mail server
ACCOUNT_USER_MODEL_USERNAME_FIELD = "username"
ACCOUNT_ADAPTER = "accounts.adapter.AccountAdapter"

LOGIN_REDIRECT_URL = "/after-login/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login/"

from django.contrib.messages import constants as message_constants  # noqa: E402

MESSAGE_TAGS = {message_constants.ERROR: "danger"}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 6}},
]

# --- I18N / TZ ------------------------------------------------------------
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Europe/London"
USE_I18N = True
USE_TZ = True

# --- Static ---------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Stripe (test mode) ---------------------------------------------------
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PRICE_GBP = os.environ.get("STRIPE_PRICE_GBP", "2900")  # pence, display only
