"""Local development settings: debug on, SQLite fallback, localhost CORS."""
import dj_database_url

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, DATABASE_URL, SECRET_KEY

DEBUG = True

SECRET_KEY = SECRET_KEY or "django-insecure-dev-only"

DATABASES = {
    "default": dj_database_url.parse(DATABASE_URL or f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

CORS_ALLOWED_ORIGIN_REGEXES = [r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"]

# Serve static files without collectstatic; also stops pytest-django (which forces DEBUG off) warning about STATIC_ROOT.
WHITENOISE_AUTOREFRESH = True
