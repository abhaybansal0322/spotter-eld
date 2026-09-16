"""API exception handling: service errors to HTTP statuses, flat validation messages, and JSON 404/500 pages."""
from django.http import JsonResponse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

from .services.errors import InputError, NotFoundError, UpstreamError

UPSTREAM_UNAVAILABLE = "The routing service is unavailable right now. Please try again in a minute."


def api_exception_handler(exc, context):
    """NotFoundError -> 422 with its message, UpstreamError -> 502, InputError -> 400.

    A bare ValueError is not handled here, so it surfaces as a 500: it is a bug, not bad input.

    Validation errors keep DRF's per-field detail under "errors" and add a flat, readable "detail".
    """
    if isinstance(exc, NotFoundError):
        return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    if isinstance(exc, UpstreamError):
        return Response({"detail": UPSTREAM_UNAVAILABLE}, status=status.HTTP_502_BAD_GATEWAY)
    if isinstance(exc, InputError):
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    response = exception_handler(exc, context)
    if response is not None and isinstance(exc, ValidationError):
        response.data = {"detail": _flatten(exc.detail), "errors": response.data}
    return response


def json_not_found(request, exception=None):
    """handler404: unmatched URLs, such as a malformed trip id, answer in JSON like the rest of the API."""
    return JsonResponse({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)


def json_server_error(request):
    """handler500: an unhandled exception answers in JSON without leaking internals."""
    return JsonResponse({"detail": "Something went wrong on our side. Please try again."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _flatten(detail):
    if isinstance(detail, dict):
        return " ".join(
            messages if field == "non_field_errors" else f"{field.replace('_', ' ').capitalize()}: {messages}"
            for field, messages in ((field, _flatten(value)) for field, value in detail.items())
        )
    if isinstance(detail, list):
        return " ".join(_flatten(item) for item in detail)
    return str(detail)
