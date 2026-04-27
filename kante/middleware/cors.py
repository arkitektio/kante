from asgiref.typing import (
    ASGI3Application,
    Scope,
    ASGIReceiveCallable,
    ASGISendCallable,
    ASGISendEvent,
    HTTPResponseBodyEvent,
    HTTPResponseStartEvent,
)

class CorsMiddleware:
    def __init__(self, app: ASGI3Application) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        # 1. Handle Preflight (OPTIONS) requests
        if scope["type"] == "http" and scope["method"] == "OPTIONS":
            headers = [
                (b"access-control-allow-origin", b"*"),
                (b"access-control-allow-headers", b"Authorization, Content-Type"),
                (b"access-control-allow-methods", b"GET, POST, PUT, DELETE, OPTIONS"),
                (b"access-control-max-age", b"86400"),
            ]
            response_start: HTTPResponseStartEvent = {
                "type": "http.response.start",
                "status": 200,
                "headers": headers,
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
                # Extract original headers
                original_headers = list(event.get("headers", []))
                
                # Define the CORS headers to inject
                cors_headers = [
                    (b"access-control-allow-origin", b"*"),
                    (b"access-control-allow-headers", b"Authorization, Content-Type"),
                    (b"access-control-allow-methods", b"GET, POST, PUT, DELETE, OPTIONS"),
                ]

                # Filter out any existing CORS headers to avoid duplicates
                filtered_headers = [
                    (k, v) for k, v in original_headers 
                    if k.lower() not in (
                        b"access-control-allow-origin",
                        b"access-control-allow-headers",
                        b"access-control-allow-methods"
                    )
                ]

                # Update the event with combined headers
                event["headers"] = filtered_headers + cors_headers

            await send(event)

        await self.app(scope, receive, wrapped_send)