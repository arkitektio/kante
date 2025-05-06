






"""
ASGI config for mikro_server project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import URLPattern, URLResolver, re_path
from strawberry.channels.handlers.http_handler import GraphQLHTTPConsumer
from strawberry.channels.handlers.ws_handler import GraphQLWSConsumer
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import URLPattern
from kante.consumers import KanteHTTPConsumer, KanteWsConsumer
from kante.middleware.cors import CorsMiddleware
from django.core.handlers.asgi import ASGIHandler
from strawberry import Schema
from .path import re_dynamicpath


def router(
    schema: Schema, 
    django_asgi_app: ASGIHandler | None = None, 
    additional_websocket_urlpatterns: list[URLPattern] | None = None,  graphql_url_patterns: list[str] | None  = None) -> ProtocolTypeRouter:
   
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
    
    graphql_url_patterns = graphql_url_patterns or [r"^graphql", r"^graphql/"]
    
    
    gql_http_consumer = KanteHTTPConsumer.as_asgi(schema=schema)
    gql_ws_consumer = KanteWsConsumer.as_asgi(schema=schema)
    
    
    http_urlpatterns = [
        re_dynamicpath(graphql_url_pattern, gql_http_consumer) for graphql_url_pattern in graphql_url_patterns
    ]
    
    if django_asgi_app:
        http_urlpatterns.extend([re_dynamicpath(r"^", django_asgi_app)])
    
    
    
    websocket_urlpatterns = [
        re_dynamicpath(graphql_url_pattern, gql_ws_consumer) for graphql_url_pattern in graphql_url_patterns
    ]
    
    
    if additional_websocket_urlpatterns:
        websocket_urlpatterns.extend(additional_websocket_urlpatterns)

    
    
    return ProtocolTypeRouter(
        {
            "http": URLRouter(
                http_urlpatterns
            ),
            "websocket": URLRouter(websocket_urlpatterns)
        }
)



