#!/usr/bin/env python
"""Django command-line entry point. Loads .env, then picks dev or prod settings from DJANGO_ENV."""
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    pass
else:
    load_dotenv(Path(__file__).resolve().parent / ".env")


def main():
    _env = os.environ.get("DJANGO_ENV", "dev")
    if _env not in ("dev", "prod"):
        raise RuntimeError(f"DJANGO_ENV must be 'dev' or 'prod', got {_env!r}")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"config.settings.{_env}")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
