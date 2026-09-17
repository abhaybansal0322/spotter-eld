"""Persistent geocode results behind geocode.py's lru_cache (spec §28). May import Django; hos/ never sees it.

The cache is an optimisation, never a dependency: a table that cannot be read or written sends the lookup to the
network, exactly as if the entry were absent.
"""
import logging

from django.db import DatabaseError, transaction

from ..models import GeocodeCache

FORWARD = GeocodeCache.FORWARD
REVERSE = GeocodeCache.REVERSE

logger = logging.getLogger(__name__)


def reverse_key(lat, lng, radius_km):
    """lat and lng arrive already rounded to three decimals; formatting fixes their spelling as well."""
    return f"{lat:.3f},{lng:.3f},{radius_km}"


def lookup(kind, key):
    """The stored GeocodeCache row, or None when there is none or the table cannot be read."""
    try:
        return GeocodeCache.objects.filter(kind=kind, key=key).first()
    except DatabaseError:
        logger.warning("geocode cache read failed for %s %r", kind, key, exc_info=True)
        return None


def store(kind, key, label, lat=None, lng=None):
    """Record an answer; label None records a miss. A failed write is logged and otherwise ignored."""
    try:
        with transaction.atomic():  # a savepoint, so a failure cannot poison a surrounding transaction
            GeocodeCache.objects.update_or_create(kind=kind, key=key, defaults={"label": label, "lat": lat, "lng": lng})
    except DatabaseError:
        logger.warning("geocode cache write failed for %s %r", kind, key, exc_info=True)
