"""Production settings: debug off, hosts and CORS from env, refuses to boot without SECRET_KEY or DATABASE_URL."""
import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import DATABASE_URL, REST_FRAMEWORK, SECRET_KEY

if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY must be set in production.")

if not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL must be set in production.")

DEBUG = False


def _csv(name):
    return [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]


ALLOWED_HOSTS = _csv("ALLOWED_HOSTS")
CORS_ALLOWED_ORIGINS = _csv("CORS_ALLOWED_ORIGINS")

DATABASES = {
    "default": dj_database_url.parse(DATABASE_URL, conn_max_age=600),
}

# Render's proxy appends the client address to X-Forwarded-For. Trust exactly one hop, so the anonymous throttle
# keys on the real client and a client-supplied X-Forwarded-For cannot mint a fresh identity per request.
REST_FRAMEWORK = {**REST_FRAMEWORK, "NUM_PROXIES": 1}

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Render terminates TLS at its proxy and forwards plain HTTP with X-Forwarded-Proto.
# Without this header mapping, SECURE_SSL_REDIRECT would loop forever.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# HSTS preload needs a registrable domain we own; a *.onrender.com host cannot be submitted.
SILENCED_SYSTEM_CHECKS = ["security.W021"]
