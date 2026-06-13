from asgiref.typing import (
    ASGI3Application,
    Scope,
    ASGIReceiveCallable,
    ASGISendCallable,
    ASGISendEvent,
    HTTPResponseBodyEvent,
    HTTPResponseStartEvent,
)

# Hoisted to module scope so they are built once, not rebuilt on every request.
_CORS_HEADERS = [
    (b"access-control-allow-origin", b"*"),
    (b"access-control-allow-headers", b"Authorization, Content-Type"),
    (b"access-control-allow-methods", b"GET, POST, PUT, DELETE, OPTIONS"),
]
_PREFLIGHT_HEADERS = _CORS_HEADERS + [
    (b"access-control-max-age", b"86400"),
]
# Names we strip from upstream responses before re-injecting ours.
_MANAGED_HEADER_NAMES = frozenset(name for name, _ in _CORS_HEADERS)


class CorsMiddleware:
    def __init__(self, app: ASGI3Application) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        # 1. Handle Preflight (OPTIONS) requests
        if scope["type"] == "http" and scope["method"] == "OPTIONS":
            response_start: HTTPResponseStartEvent = {
                "type": "http.response.start",
                "status": 200,
                "headers": _PREFLIGHT_HEADERS,
                "trailers": False,
            }
            await send(response_start)
            response_body: HTTPResponseBodyEvent = {
                "type": "http.response.body",
                "body": b"",
                "more_body": False,
            }
            await send(response_body)
            return

        # 2. Handle actual requests by wrapping the send callable
        async def wrapped_send(event: ASGISendEvent) -> None:
            if event["type"] == "http.response.start":
                # Drop any upstream CORS headers, then append ours once.
                filtered_headers = [
                    (k, v) for k, v in event.get("headers", [])
                    if k.lower() not in _MANAGED_HEADER_NAMES
                ]
                event["headers"] = filtered_headers + _CORS_HEADERS

            await send(event)

        await self.app(scope, receive, wrapped_send)