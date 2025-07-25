"""
ASGI config for mikro_server project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""
import os
from django.core.asgi import get_asgi_application
from kante.router import router

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test_project.settings")
# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()


from .schema import schema  # noqa
from .echo_consumer import EchoConsumer  # noqa
from kante.path import re_dynamicpath

additional_websocket_urlpatterns = [
    re_dynamicpath(r"ws/echo/$", EchoConsumer.as_asgi()),
]


application = router(
    schema=schema,
    django_asgi_app=django_asgi_app,
    schema_path="schema",
    additional_websocket_urlpatterns=additional_websocket_urlpatterns,
)
