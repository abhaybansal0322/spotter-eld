"""Service-layer errors. The API maps them to HTTP statuses; nothing else in the service layer defines its own."""


class UpstreamError(Exception):
    """An upstream call failed, timed out, or answered with something unusable.

    status is the HTTP code and body the parsed JSON error body, when the upstream sent them.
    """

    def __init__(self, message, status=None, body=None):
        super().__init__(message)
        self.status = status
        self.body = body


class NotFoundError(Exception):
    """A lookup succeeded but matched nothing: no such place, no drivable route, or inputs that collapse to one place."""


class InputError(ValueError):
    """Input a caller can fix. The only ValueError the API reports as 400; any other ValueError is a bug."""
