"""API exception handler: maps service-layer errors to HTTP statuses and flattens validation errors."""
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .services.http import NotFoundError, UpstreamError

UPSTREAM_UNAVAILABLE = "The routing service is unavailable right now. Please try again in a minute."


def api_exception_handler(exc, context):
    """NotFoundError -> 422 with the upstream message, UpstreamError -> 502, ValueError -> 400.

    Validation errors keep DRF's per-field detail under "errors" and add a flat, readable "detail".
    """
    if isinstance(exc, NotFoundError):
        return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    if isinstance(exc, UpstreamError):
        return Response({"detail": UPSTREAM_UNAVAILABLE}, status=status.HTTP_502_BAD_GATEWAY)
    if isinstance(exc, ValueError):
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    response = exception_handler(exc, context)
    if response is not None and isinstance(exc, ValidationError):
        response.data = {"detail": _flatten(exc.detail), "errors": response.data}
    return response


def _flatten(detail):
    if isinstance(detail, dict):
        return " ".join(
            messages if field == "non_field_errors" else f"{field.replace('_', ' ').capitalize()}: {messages}"
            for field, messages in ((field, _flatten(value)) for field, value in detail.items())
        )
    if isinstance(detail, list):
        return " ".join(_flatten(item) for item in detail)
    return str(detail)
