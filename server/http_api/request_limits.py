"""ASGI middleware that bounds the size of POST bodies."""

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class RequestSizeLimiter:
    """Reject POST requests before their body is read.

    Usage:
        Add with `application.add_middleware`. The HTTP server guarantees the
        body is not longer than the declared Content-Length, so requests
        without that header are refused.
    """

    def __init__(self, app: ASGIApp, max_request_bytes: int) -> None:
        """Store the wrapped application and the limit.

        Usage:
            Called by Starlette.

        Args:
            app: Next ASGI application.
            max_request_bytes: Largest accepted body in bytes.
        """
        self.app = app
        self._max_request_bytes = max_request_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle one ASGI connection.

        Usage:
            Called by the ASGI server.

        Args:
            scope: Connection metadata.
            receive: Channel of incoming events.
            send: Channel of outgoing events.
        """
        rejection = None
        if scope["type"] == "http" and scope["method"] == "POST":
            rejection = self._find_rejection(Headers(scope=scope).get("content-length"))
        if rejection is None:
            await self.app(scope, receive, send)
        else:
            await rejection(scope, receive, send)

    def _find_rejection(self, content_length: str | None) -> JSONResponse | None:
        """Decide whether a declared length is acceptable.

        Usage:
            Internal step of `__call__`.

        Args:
            content_length: Value of the header, or None.

        Returns:
            The error response, or None when the request may proceed.
        """
        if content_length is None or not content_length.isdigit():
            return JSONResponse({"detail": "Content-Length header is required"}, status_code=411)
        if int(content_length) > self._max_request_bytes:
            return JSONResponse({"detail": "Request body is too large"}, status_code=413)
        return None
