"""ASGI entry point. Loads .env, then picks settings from DJANGO_ENV, defaulting to prod."""
import os
from pathlib import Path

from django.core.asgi import get_asgi_application

try:
    from dotenv import load_dotenv
except ImportError:
    pass
else:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_env = os.environ.get("DJANGO_ENV", "prod")
if _env not in ("dev", "prod"):
    raise RuntimeError(f"DJANGO_ENV must be 'dev' or 'prod', got {_env!r}")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"config.settings.{_env}")

application = get_asgi_application()
