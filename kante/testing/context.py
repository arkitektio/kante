"""Factories for building a request context in tests.

Resolvers reach the caller through ``info.context.request``, so any test that
calls a resolver directly has to build a :class:`~kante.context.HttpContext` by
hand. Doing that inline means repeating the same six lines in every conftest --
and, until kante's protocols were fixed, decorating each field with a
``# type: ignore``.

These factories take already-built objects rather than creating them, so they
stay independent of whichever models a service uses for users and organizations::

    @pytest.fixture
    def authenticated_context(db) -> HttpContext:
        user = User.objects.create(sub="1", username="tester")
        org = Organization.objects.create(slug="test_org")
        return build_http_context(user=user, organization=org, token="test")
"""

from typing import Any
from collections.abc import Mapping

from strawberry.channels import ChannelsConsumer
from strawberry.http.temporal_response import TemporalResponse

from kante.context import (
    Client,
    HttpContext,
    Membership,
    Organization,
    Provenance,
    UniversalRequest,
    User,
    WsContext,
)


def build_request(
    user: User | None = None,
    organization: Organization | None = None,
    client: Client | None = None,
    membership: Membership | None = None,
    provenance: Provenance | None = None,
    token: str | None = None,
    extensions: dict[str, Any] | None = None,
) -> UniversalRequest:
    """Build a :class:`~kante.context.UniversalRequest` with the given principals.

    Anything left as ``None`` stays unset, so accessing it raises the same error
    a real request would -- which is what you want when asserting that a resolver
    rejects an unauthenticated caller.

    ``token`` is stored in the request's extensions under ``"token"``, matching
    what the authenticating strawberry extension puts there.
    """
    resolved_extensions: dict[str, Any] = dict(extensions or {})
    if token is not None:
        resolved_extensions.setdefault("token", token)

    return UniversalRequest(
        _extensions=resolved_extensions,
        _client=client,
        _user=user,
        _provenance=provenance,
        _organization=organization,
        _membership=membership,
    )


def build_http_context(
    user: User | None = None,
    organization: Organization | None = None,
    client: Client | None = None,
    membership: Membership | None = None,
    provenance: Provenance | None = None,
    token: str | None = None,
    extensions: dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    response: TemporalResponse | None = None,
) -> HttpContext:
    """Build an :class:`~kante.context.HttpContext` for calling resolvers in tests.

    If ``token`` is given and ``headers`` does not already carry an
    ``Authorization`` header, one is added as ``Bearer <token>`` -- so a context
    built here works both for direct resolver calls and for tests that go through
    an extension which re-reads the header.
    """
    resolved_headers: dict[str, str] = dict(headers or {})
    if token is not None:
        resolved_headers.setdefault("Authorization", f"Bearer {token}")

    return HttpContext(
        request=build_request(
            user=user,
            organization=organization,
            client=client,
            membership=membership,
            provenance=provenance,
            token=token,
            extensions=extensions,
        ),
        response=response or TemporalResponse(),
        headers=resolved_headers,
        type="http",
    )


def build_ws_context(
    consumer: ChannelsConsumer,
    user: User | None = None,
    organization: Organization | None = None,
    client: Client | None = None,
    membership: Membership | None = None,
    provenance: Provenance | None = None,
    token: str | None = None,
    extensions: dict[str, Any] | None = None,
    connection_params: dict[str, Any] | None = None,
    response: TemporalResponse | None = None,
) -> WsContext:
    """Build a :class:`~kante.context.WsContext` for testing subscriptions.

    ``consumer`` has no default because there is nothing sensible to invent: it
    is what a subscription actually subscribes on. Get one from a running
    consumer, or pass a stub exposing ``channel_layer`` and ``listen_to_channel``.
    """
    return WsContext(
        request=build_request(
            user=user,
            organization=organization,
            client=client,
            membership=membership,
            provenance=provenance,
            token=token,
            extensions=extensions,
        ),
        response=response or TemporalResponse(),
        connection_params=dict(connection_params or {}),
        consumer=consumer,
        type="ws",
    )


__all__ = ["build_http_context", "build_request", "build_ws_context"]
