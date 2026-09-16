"""Shared HTTP session, timeouts and retry policy; the mock seam for network tests.

The only module that imports requests. Callers catch UpstreamError and NotFoundError, never requests exceptions.
"""
import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ORS_BASE_URL = "https://api.openrouteservice.org"

CONNECT_TIMEOUT_S = 5
READ_TIMEOUT_S = 15
RETRY_TOTAL = 3
RETRY_BACKOFF_FACTOR = 0.5
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
RETRY_METHODS = frozenset({"GET", "POST"})


class UpstreamError(Exception):
    """An upstream call failed, timed out, or answered with something unusable. status is the HTTP code, if any."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class NotFoundError(Exception):
    """An upstream call succeeded but matched nothing: no such place, no drivable route."""


def _build_session():
    retry = Retry(
        total=RETRY_TOTAL,
        backoff_factor=RETRY_BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUSES,
        allowed_methods=RETRY_METHODS,
        raise_on_status=False,  # hand the final response back so raise_for_status reports its real code
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = _build_session()


def request_json(method, url, **kwargs):
    """Send a request through the shared session and return its parsed JSON body."""
    kwargs.setdefault("timeout", (CONNECT_TIMEOUT_S, READ_TIMEOUT_S))
    try:
        response = SESSION.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as error:
        status = error.response.status_code
        raise UpstreamError(f"{method} {url} returned HTTP {status}", status=status) from error
    except (requests.RequestException, ValueError) as error:
        raise UpstreamError(f"{method} {url} failed: {type(error).__name__}") from error


def ors_headers():
    """Auth header for OpenRouteService. The key is read at call time and sent as a header, never in a URL."""
    if not settings.ORS_API_KEY:
        raise ImproperlyConfigured("ORS_API_KEY is not set")
    return {"Authorization": settings.ORS_API_KEY}
