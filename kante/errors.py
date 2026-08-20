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
"""

from typing import Any, Dict, Optional

from graphql import GraphQLError


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


__all__ = [
    "KanteError",
    "NotFound",
    "PermissionDenied",
    "ValidationError",
    "AuthenticationError",
]
