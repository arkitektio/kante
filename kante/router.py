






"""
ASGI config for mikro_server project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""



from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import URLPattern
from kante.consumers import KanteHTTPConsumer, KanteWsConsumer
from kante.middleware.cors import CorsMiddleware
from django.core.handlers.asgi import ASGIHandler
from strawberry import Schema
from .path import re_dynamicpath


def router(
    django_asgi_app: ASGIHandler, 
    schema: Schema, 
    additional_websocket_urlpatterns: list[URLPattern] | None = None) -> ProtocolTypeRouter:
    """
    ASGI router for the Kante framework.
    
    This function sets up the ASGI application to handle both HTTP and WebSocket
    requests. It uses the KanteHTTPConsumer for HTTP requests and the KanteWsConsumer
    for WebSocket requests. The router also applies CORS middleware to the HTTP
    consumer and the WebSocket consumer.
    
    Args:
        django_asgi_app (ASGIHandler): The Django ASGI application (with urls)
        schema (Schema): The Strawberry GraphQL schema.
        additional_websocket_urlpatterns (list[URLPattern], optional): Additional
            WebSocket URL patterns to include. Defaults to None.
            
    Returns:
        ProtocolTypeRouter: The ASGI application router.
        
    
    
    """
    
    
    gql_http_consumer = CorsMiddleware(
        AuthMiddlewareStack(KanteHTTPConsumer.as_asgi(schema=schema))
    )
    gql_ws_consumer = KanteWsConsumer.as_asgi(schema=schema)
    
    websocket_urlpatterns = [
        re_dynamicpath(r"graphql", gql_ws_consumer),
        re_dynamicpath(r"graphql/", gql_ws_consumer),
    ]
    
    
    if additional_websocket_urlpatterns:
        websocket_urlpatterns.extend(additional_websocket_urlpatterns)

    
    
    return ProtocolTypeRouter(
        {
            "http": URLRouter(
                [
                    re_dynamicpath("graphql", gql_http_consumer),
                    re_dynamicpath(
                        "", django_asgi_app
                    ),  # This might be another endpoint in your app
                ]
            ),
            "websocket": CorsMiddleware(
                AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
            ),
        }
)



