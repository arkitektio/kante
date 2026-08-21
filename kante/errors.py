"""Typed errors that reach the client with a machine-readable code.

Strawberry surfaces an uncaught exception's ``str()`` as the GraphQL error
message and nothing else. That makes an internal invariant failure and a
deliberate, user-facing validation message indistinguishable on the wire -- both
arrive as an untyped error with no code for the client to branch on.

Raising one of these instead attaches ``extensions.code``::

    raise NotFound("No dataset with that id")
    # {"errors": [{"message": "No dataset with that id",
    #              "extensions": {"code": "NOT_FOUND"}}]}

Nothing here masks anything: the message you pass is the message the client sees,
exactly as before. The addition is the code.

The second half of this module is about the *text* of a message rather than its
code. A pydantic ``ValidationError`` raised inside a resolver renders as a
multi-line report carrying the model's class name, pydantic's ``[type=...]``
annotation and a docs URL -- machinery, where the rest of the API speaks in
sentences. :func:`describe_validation_error` and the :func:`prose_errors`
decorator keep the sentence a validator wrote and drop everything around it.
"""

from collections.abc import Callable
from typing import Any, Dict, Optional

from graphql import GraphQLError
from pydantic import ValidationError as PydanticValidationError

#: pydantic prefixes the message of a ``ValueError`` raised inside a validator with this.
#: Stripped on the way out: the validator already wrote a full sentence, and the prefix
#: names pydantic's error machinery rather than anything the caller did.
_VALUE_ERROR_PREFIX = "Value error, "


class KanteError(GraphQLError):
    """Base for errors that intentionally travel to the client.

    Subclass it to add a domain error, setting ``code`` on the subclass::

        class QuotaExceeded(KanteError):
            code = "QUOTA_EXCEEDED"

    Anything *not* raised as a ``KanteError`` is an internal error: it still
    reaches the client (kante installs no masking extension), but without a code,
    which is the signal that it was never meant to be part of the API.
    """

    code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Build the error, merging ``code`` into the GraphQL ``extensions``."""
        merged: Dict[str, Any] = dict(extensions or {})
        merged.setdefault("code", code or type(self).code)
        super().__init__(message, extensions=merged, **kwargs)


class NotFound(KanteError):
    """The requested object does not exist, or is not visible to this request.

    Deliberately does not distinguish the two: telling a caller that a row exists
    but belongs to another organization is itself a tenancy leak.
    """

    code = "NOT_FOUND"


class PermissionDenied(KanteError):
    """The request is authenticated but not allowed to do this."""

    code = "PERMISSION_DENIED"


class ValidationError(KanteError):
    """The input is well-formed GraphQL but invalid for this operation."""

    code = "VALIDATION_ERROR"


class AuthenticationError(KanteError):
    """The request carries no valid credentials."""

    code = "UNAUTHENTICATED"


def camel_field(name: str) -> str:
    """A pydantic field name as the SDL spells it.

    Error messages name fields the way the client wrote them, so a caller can act
    on the message without translating ``input_axes`` back into ``inputAxes``.
    """
    head, *tail = name.split("_")
    return head + "".join(part.title() for part in tail)


def describe_validation_error(err: PydanticValidationError) -> str:
    """The first error of a pydantic ``ValidationError``, as one sentence of prose.

    A resolver's exception reaches the client as ``errors[0].message`` verbatim, so
    the message *is* part of the API contract. This keeps the sentence a validator
    wrote and drops pydantic's report around it.

    Only the first error is reported: a caller fixes one at a time, and the second is
    often a consequence of the first.
    """
    detail = err.errors()[0]
    message = str(detail["msg"])
    if message.startswith(_VALUE_ERROR_PREFIX):
        # A validator's own sentence, which already names its field where that matters.
        return message[len(_VALUE_ERROR_PREFIX) :]

    # Anything else is pydantic's own text for a constraint or a coercion. Name the field
    # by its full path, so an error on a nested input says which one -- `policy.nchildren`,
    # not `policy`. List indices stay bare, as they read better than `.0.`.
    parts = [
        str(part) if isinstance(part, int) else camel_field(str(part))
        for part in detail["loc"]
    ]
    if not parts:
        return message
    path = parts[0] + "".join(
        f"[{part}]" if part.isdigit() else f".{part}" for part in parts[1:]
    )
    return f"`{path}`: {message}"


def prose_errors[T](cls: type[T]) -> type[T]:
    """Make a strawberry input's ``to_pydantic`` raise prose instead of a pydantic report.

    Applied *above* ``@kante.pydantic_input`` on the inputs whose models carry
    validators, so the sentence the validator wrote is the sentence the client reads::

        @prose_errors
        @kante.pydantic_input(ScaleModel)
        class ScaleInput:
            scale: list[float]

    Only those inputs are worth wrapping: a model with no validators can only fail on a
    type coercion GraphQL has already done, so wrapping it costs a try/except to catch
    nothing.
    """
    original: Callable[..., Any] = cls.to_pydantic  # type: ignore[attr-defined]

    def to_pydantic(self: Any, **kwargs: Any) -> Any:
        """Convert to the pydantic model, restating any failure as one sentence."""
        try:
            return original(self, **kwargs)
        except PydanticValidationError as err:
            raise ValueError(describe_validation_error(err)) from err

    cls.to_pydantic = to_pydantic  # type: ignore[attr-defined]
    return cls


__all__ = [
    "KanteError",
    "NotFound",
    "PermissionDenied",
    "ValidationError",
    "AuthenticationError",
    "camel_field",
    "describe_validation_error",
    "prose_errors",
]
