"""Tests for kante's public API surface: Info, errors, context protocols."""

import warnings
from typing import Any

import pytest
from graphql import GraphQLError

import kante
import kante.types
from kante.context import HttpContext, UniversalRequest
from kante.errors import KanteError, NotFound, PermissionDenied, ValidationError
from kante.testing import build_http_context, build_request, build_ws_context


def test_kante_info_is_the_context_typed_info() -> None:
    """``kante.Info`` and ``kante.types.Info`` must be the same object.

    They used to differ: ``kante/__init__`` re-exported the *unparameterized*
    ``strawberry.types.Info`` that ``kante/type.py`` imports for its own
    annotations, so ``from kante import Info`` silently lost all typing on
    ``info.context``.
    """
    assert kante.Info is kante.types.Info


def test_kante_exports_the_ws_narrowing_helpers() -> None:
    """The websocket narrowing helpers are part of the public API."""
    assert kante.require_ws is kante.types.require_ws
    assert kante.is_ws is kante.types.is_ws


def test_require_ws_rejects_an_http_request() -> None:
    """Narrowing raises (not asserts) when the request is not a websocket."""

    class _Info:
        context = build_http_context()

    with pytest.raises(TypeError, match="websocket"):
        kante.require_ws(_Info())  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# errors
# --------------------------------------------------------------------------


def test_errors_carry_a_machine_readable_code() -> None:
    """Each error puts its code into the GraphQL error extensions."""
    assert NotFound("nope").extensions["code"] == "NOT_FOUND"
    assert PermissionDenied("no").extensions["code"] == "PERMISSION_DENIED"
    assert ValidationError("bad").extensions["code"] == "VALIDATION_ERROR"


def test_errors_are_graphql_errors() -> None:
    """They must travel as GraphQL errors, not become 'Internal Server Error'."""
    assert isinstance(NotFound("nope"), GraphQLError)


def test_error_message_is_preserved() -> None:
    """kante adds a code; it never rewrites the message."""
    assert NotFound("No dataset with that id").message == "No dataset with that id"


def test_error_code_can_be_overridden_per_raise() -> None:
    """A one-off code does not require declaring a subclass."""
    assert KanteError("x", code="TEAPOT").extensions["code"] == "TEAPOT"


def test_subclass_declares_its_own_code() -> None:
    """Domain errors are added by subclassing."""

    class QuotaExceeded(KanteError):
        code = "QUOTA_EXCEEDED"

    assert QuotaExceeded("too much").extensions["code"] == "QUOTA_EXCEEDED"


def test_extra_extensions_survive() -> None:
    """Callers can attach their own extension payload alongside the code."""
    error = NotFound("nope", extensions={"id": "7"})
    assert error.extensions == {"id": "7", "code": "NOT_FOUND"}


# --------------------------------------------------------------------------
# testing context factories
# --------------------------------------------------------------------------


class _User:
    """Shaped like a Django user: `is_anonymous` is a read-only property."""

    id = 1
    sub = "sub-1"

    @property
    def is_anonymous(self) -> bool:
        """Never anonymous."""
        return False


class _Organization:
    id = 2
    slug = "acme"


def test_build_http_context_populates_the_request() -> None:
    """The factory produces a context whose principals are readable."""
    context = build_http_context(user=_User(), organization=_Organization())

    assert isinstance(context, HttpContext)
    assert context.request.user.id == 1
    assert context.request.organization.slug == "acme"


def test_build_http_context_sets_the_bearer_header() -> None:
    """A token becomes both a request extension and an Authorization header."""
    context = build_http_context(token="test")

    assert context.headers["Authorization"] == "Bearer test"
    assert context.request.get_extension("token") == "test"


def test_build_http_context_leaves_unset_principals_unset() -> None:
    """Omitted principals raise on access, exactly as an unauthenticated request does."""
    context = build_http_context()

    with pytest.raises(ValueError):
        _ = context.request.user


def test_build_request_is_a_universal_request() -> None:
    """The request factory returns the real type, not a stub."""
    assert isinstance(build_request(), UniversalRequest)


def test_build_ws_context_carries_the_consumer() -> None:
    """The websocket factory keeps the consumer the subscription listens on."""
    consumer: Any = object()
    context = build_ws_context(consumer, connection_params={"token": "x"})

    assert context.type == "ws"
    assert context.consumer is consumer
    assert context.connection_params == {"token": "x"}


# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------


def test_enable_federation_2_false_warns_instead_of_lying() -> None:
    """The argument is a no-op, so passing False must not pass silently."""
    import strawberry

    @strawberry.type
    class Query:
        @strawberry.field
        def hello(self) -> str:
            """A field."""
            return "world"

    with pytest.warns(DeprecationWarning, match="enable_federation_2"):
        kante.Schema(query=Query, enable_federation_2=False)


def test_enable_federation_2_default_does_not_warn() -> None:
    """The default path stays quiet."""
    import strawberry

    @strawberry.type
    class Query:
        @strawberry.field
        def hello(self) -> str:
            """A field."""
            return "world"

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        kante.Schema(query=Query)


def test_federated_type_without_id_raises_not_asserts() -> None:
    """The federation guard must survive `python -O`, so it raises.

    An `assert` here is stripped under -O, and the failure mode becomes a schema
    advertising `@key(fields: "id")` on a type with no `id` -- surfacing as a
    gateway composition error far from its cause.
    """
    from test_app import models

    with pytest.raises(TypeError, match="no 'id' field annotation"):

        @kante.django_type(models.TestModel)
        class Broken:
            name: str


def test_federated_type_can_be_opted_out() -> None:
    """A non-federated type needs no id."""
    from test_app import models

    @kante.django_type(models.TestModel, federated=False)
    class Fine:
        name: str

    assert Fine is not None
