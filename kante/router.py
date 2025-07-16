






"""
ASGI config for mikro_server project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""
from __future__ import annotations


from django.urls import URLPattern
from channels.routing import ProtocolTypeRouter, URLRouter # type: ignore
from django.urls import URLPattern
from kante.consumers import KanteHTTPConsumer, KanteWsConsumer
from kante.middleware.cors import CorsMiddleware
from django.core.handlers.asgi import ASGIHandler
from strawberry import Schema
from .path import re_dynamicpath, dynamicpath




def router(
    schema: Schema, 
    django_asgi_app: ASGIHandler | None = None, 
    additional_websocket_urlpatterns: list[URLPattern] | None = None,  
    graphql_url_patterns: list[str] | None  = None, 
    schema_path: str | None = None
    
    
    ) -> ProtocolTypeRouter:
   
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
    
    
    gql_http_consumer = KanteHTTPConsumer.as_asgi(schema=schema) # type: ignore
    gql_ws_consumer = KanteWsConsumer.as_asgi(schema=schema) # type: ignore
    
    
    async def graphql_schema(scope, receive, send): # type: ignore
        """ASGI view to serve the GraphQL schema as plain text."""
        await receive()
        
        schema_content = schema.as_str().encode('utf-8')
        
        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': [
                [b'content-type', b'text/plain'],
                [b'content-length', str(len(schema_content)).encode()],
            ],
        })
        
        await send({
            'type': 'http.response.body',
            'body': schema_content,
        })  
        
        
    
    http_urlpatterns = [
        re_dynamicpath(graphql_url_pattern, gql_http_consumer) for graphql_url_pattern in graphql_url_patterns
    ]
    
    if schema_path:
        http_urlpatterns.append(dynamicpath(schema_path, graphql_schema))
    
    if django_asgi_app:
        http_urlpatterns.extend([re_dynamicpath(r"^", django_asgi_app)])
    
    
    
    websocket_urlpatterns = [
        re_dynamicpath(graphql_url_pattern, gql_ws_consumer) for graphql_url_pattern in graphql_url_patterns
    ]
    
    
    if additional_websocket_urlpatterns:
        websocket_urlpatterns.extend(additional_websocket_urlpatterns)

    
    
    return CorsMiddleware(ProtocolTypeRouter(
        {
            "http": URLRouter(
                http_urlpatterns
            ),
            "websocket": URLRouter(websocket_urlpatterns)
        }
    ))



