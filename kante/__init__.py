"""All public API of kante."""

from .context import Context, HttpContext, UniversalRequest, WsContext
from .errors import (
    AuthenticationError,
    KanteError,
    NotFound,
    PermissionDenied,
    ValidationError,
    camel_field,
    describe_validation_error,
    prose_errors,
)
from .schema import Schema
from .type import (
    django_field,
    django_input,
    django_interface,
    django_mutation,
    django_type,
    field,
    filter_field,
    filter_type,
    input,
    interface,
    mutation,
    pydantic_input,
    pydantic_type,
    scalar,
    subscription,
    type,
)

# NOTE: import ``Info`` from ``.types``, NOT from ``.type``. ``kante/type.py``
# imports strawberry's *unparameterized* ``Info`` for its own annotations;
# re-exporting that one made ``kante.Info`` silently different from
# ``kante.types.Info`` (``Info[Context, Any]``), so every ``from kante import Info``
# lost all typing on ``info.context``.
from .types import HttpInfo, Info, WsInfo, is_ws, require_ws
from .unions import (
    merged_input,
    parse_union_member,
    union_member,
    union_member_types,
    union_memberships,
    unionElementOf,
)

__all__ = [
    "type",
    "field",
    "interface",
    "django_mutation",
    "mutation",
    "django_type",
    "django_field",
    "django_interface",
    "pydantic_type",
    "subscription",
    "input",
    "django_input",
    "scalar",
    "filter_type",
    "filter_field",
    "pydantic_input",
    "Info",
    "WsInfo",
    "HttpInfo",
    "is_ws",
    "require_ws",
    "Context",
    "HttpContext",
    "WsContext",
    "UniversalRequest",
    "KanteError",
    "NotFound",
    "PermissionDenied",
    "ValidationError",
    "AuthenticationError",
    "camel_field",
    "describe_validation_error",
    "prose_errors",
    "merged_input",
    "parse_union_member",
    "unionElementOf",
    "union_member",
    "union_member_types",
    "union_memberships",
    "Schema",
]
