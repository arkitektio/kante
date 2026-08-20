"""Organization (tenant) scoping for Django querysets.

Every service built on kante is multi-tenant: a row belongs to an organization,
and a request may only ever see the organization it was authenticated for. That
rule has to be applied in two different places, and both of them live here:

* **List fields** resolve through a queryset, so they are scoped by installing
  :func:`build_prescoper` as the field's ``get_queryset``.
* **Single-object access** -- mutations, single-item queries, subscription
  re-fetches -- must go through :func:`for_org`, :func:`get_for_org` or
  :func:`aget_for_org` instead of ``Model.objects``, or one organization can read
  and mutate another's rows by guessing an id.

Scoping works by walking the model's foreign keys to find a path to
``organization``. Only non-nullable FKs are followed: a nullable path would
silently hide rows whose FK is ``NULL`` rather than scope them.

A model with no path to an organization raises :class:`UnscopedModelError`
rather than quietly returning everything. Register the deliberate exceptions on
your own :class:`OrganizationScoper`::

    scoper = OrganizationScoper(unscoped_models={"SystemSetting"}, max_path_depth=5)

The module-level :func:`for_org` / :func:`get_for_org` / :func:`aget_for_org` are
bound to a default scoper (depth 3, no exceptions), which is what most services
want.
"""

import warnings
from functools import lru_cache
from typing import Any, Callable, Collection, Optional, Type, cast

from django.core.exceptions import FieldDoesNotExist
from django.db import models as django_models

from kante.types import Info

DEFAULT_MAX_PATH_DEPTH = 3
"""How many FK hops to follow looking for ``organization``.

Three covers ``pod__backend__organization``. Raise it on your own scoper if a
model sits deeper -- an exhausted walk is reported as an error, never as an
unscoped queryset.
"""


def _manager(model: Type[django_models.Model]) -> "django_models.Manager[Any]":
    """Return the model's default manager.

    ``Model.objects`` is not declared on the ``Model`` base class as far as
    django-stubs is concerned; ``_default_manager`` is, and it is what Django
    itself uses when it needs a manager for an arbitrary model.
    """
    return cast("django_models.Manager[Any]", model._default_manager)


class UnscopedModelError(LookupError):
    """A model has no path to an organization and was not declared unscoped.

    Raised instead of returning ``Model.objects.all()``, so that adding a model
    without a tenancy story fails loudly at first use rather than silently
    serving every organization's rows.
    """


def _find_org_path(
    model: Type[django_models.Model], depth: int, field_name: str
) -> Optional[str]:
    """Depth-first search for the ORM lookup path from ``model`` to its tenant."""
    try:
        field = model._meta.get_field(field_name)
        if field.is_relation:
            return field_name
    except FieldDoesNotExist:
        pass

    if depth == 0:
        return None

    # Only follow required FKs: a nullable path would silently hide rows whose
    # FK is NULL instead of scoping them.
    for field in model._meta.get_fields():
        if not isinstance(field, django_models.ForeignKey) or field.null:
            continue
        related_model = field.related_model
        if related_model is model or related_model is None:
            continue
        sub_path = _find_org_path(
            cast(Type[django_models.Model], related_model), depth - 1, field_name
        )
        if sub_path:
            return f"{field.name}__{sub_path}"

    return None


@lru_cache(maxsize=None)
def organization_path(
    model: Type[django_models.Model],
    max_depth: int = DEFAULT_MAX_PATH_DEPTH,
    field_name: str = "organization",
) -> Optional[str]:
    """Return the ORM lookup path from ``model`` to its organization, if any.

    Cached: the model graph does not change at runtime, and this walk is on the
    hot path of every scoped read.
    """
    return _find_org_path(model, max_depth, field_name)


def field_argument(info: Info, name: str) -> Any:
    """Return the resolved value of an argument on the field being resolved.

    Sees arguments written inline in the query document as well as ones passed as
    variables, because strawberry resolves both when it builds
    ``selected_fields``.

    .. note::

       ``info.selected_fields`` materializes the *whole selection subtree* under
       the current field, which is expensive on a deep query. Do not call this on
       a hot path -- :meth:`OrganizationScoper.prescope` deliberately does not.
    """
    for selected_field in info.selected_fields:
        arguments = getattr(selected_field, "arguments", None)
        if arguments and name in arguments:
            return arguments[name]
    return None


def _has_inline_scope(info: Info) -> bool:
    """Whether the field carries an inline (non-variable) ``filters.scope``.

    Reads the field's own argument nodes off the GraphQL AST rather than going
    through ``info.selected_fields``, which would walk the entire selection
    subtree -- this runs on every prescoped list field of every request.
    """
    try:
        field_nodes = info.field_nodes
    except Exception:  # pragma: no cover - defensive, older/other Info shapes
        return False

    for node in field_nodes or ():
        for argument in getattr(node, "arguments", ()) or ():
            if argument.name.value != "filters":
                continue
            fields = getattr(argument.value, "fields", None)
            if not fields:
                continue
            for object_field in fields:
                if object_field.name.value == "scope":
                    # A literal `null` is the same as not asking for a scope.
                    kind = getattr(object_field.value, "kind", "")
                    if kind != "null_value":
                        return True
    return False


class OrganizationScoper:
    """Applies organization scoping using one set of policy choices.

    Instantiate one per service if the defaults do not fit; otherwise use the
    module-level functions, which delegate to a default instance.
    """

    def __init__(
        self,
        unscoped_models: Collection[str] = (),
        max_path_depth: int = DEFAULT_MAX_PATH_DEPTH,
        organization_field: str = "organization",
    ) -> None:
        """Configure the tenancy escape hatch and how deep to search for it."""
        self.unscoped_models = frozenset(unscoped_models)
        self.max_path_depth = max_path_depth
        self.organization_field = organization_field

    def path_for(self, model: Type[django_models.Model]) -> Optional[str]:
        """Return the lookup path from ``model`` to its organization, if any."""
        return organization_path(model, self.max_path_depth, self.organization_field)

    def for_org(
        self, model: Type[django_models.Model], info: Info
    ) -> "django_models.QuerySet[Any]":
        """Return ``model``'s queryset limited to the request's organization."""
        path = self.path_for(model)
        if path is None:
            if model.__name__ not in self.unscoped_models:
                raise UnscopedModelError(
                    f"{model.__name__} has no path to "
                    f"'{self.organization_field}' within {self.max_path_depth} "
                    "relations and is not registered as an unscoped model. Add "
                    "the relation, raise max_path_depth, or declare it "
                    "explicitly on your OrganizationScoper."
                )
            return _manager(model).all()
        return _manager(model).filter(**{path: info.context.request.organization})

    def get_for_org(
        self, model: Type[django_models.Model], info: Info, **kwargs: Any
    ) -> django_models.Model:
        """``Model.objects.get`` limited to the request's organization."""
        return cast(django_models.Model, self.for_org(model, info).get(**kwargs))

    async def aget_for_org(
        self, model: Type[django_models.Model], info: Info, **kwargs: Any
    ) -> django_models.Model:
        """Async ``Model.objects.aget`` limited to the request's organization."""
        return cast(
            django_models.Model, await self.for_org(model, info).aget(**kwargs)
        )

    def prescope(
        self,
        info: Info,
        queryset: "django_models.QuerySet[Any]",
        field: Optional[str] = None,
    ) -> "django_models.QuerySet[Any]":
        """Limit an already-built queryset to the request's organization.

        This is the list-field half of scoping: install it via
        :meth:`prescoper` as a field's ``get_queryset``.

        ``field`` is the lookup path from the queryset's model to its
        organization; it defaults to this scoper's organization field. Pass it
        explicitly when the path is indirect (``memberships__organization``).
        """
        filters = info.variable_values.get("filters") or {}
        if isinstance(filters, dict) and filters.get("scope") is not None:
            # Unchanged from the implementation this replaced: a scope passed as
            # a *variable* has always been refused.
            raise NotImplementedError(
                "Custom filter scopes are not supported. Remove 'scope' from the "
                "filters argument; every query is scoped to the authenticated "
                "organization."
            )

        # A scope written inline in the document never reached the check above,
        # because `variable_values` does not contain it. That was not a leak --
        # the query fell through to the scoping branch below and was scoped
        # anyway -- but the argument was silently ignored. Warn now and keep
        # scoping; this becomes an error in kante 3.
        if _has_inline_scope(info):
            warnings.warn(
                "A 'scope' was passed inline in the filters argument. Custom "
                "scopes are not supported: it is being ignored and the query is "
                "scoped to the authenticated organization, as it always has "
                "been. Passing 'scope' will raise in kante 3.",
                DeprecationWarning,
                stacklevel=3,
            )

        return queryset.filter(
            **{field or self.organization_field: info.context.request.organization}
        )

    def prescoper(
        self, field: Optional[str] = None
    ) -> Callable[["django_models.QuerySet[Any]", Info], "django_models.QuerySet[Any]"]:
        """Build a ``get_queryset`` callable that prescopes to the organization.

        Usage on a strawberry-django type::

            @kante.django_type(models.Item)
            class Item:
                @classmethod
                def get_queryset(cls, queryset, info):
                    return scoper.prescope(info, queryset)
        """

        def prescoper(
            queryset: "django_models.QuerySet[Any]", info: Info
        ) -> "django_models.QuerySet[Any]":
            """Limit ``queryset`` to the request's organization."""
            return self.prescope(info, queryset, field=field)

        return prescoper


default_scoper = OrganizationScoper()
"""The scoper backing the module-level helpers."""


def for_org(
    model: Type[django_models.Model], info: Info
) -> "django_models.QuerySet[Any]":
    """Return ``model``'s queryset limited to the request's organization."""
    return default_scoper.for_org(model, info)


def get_for_org(
    model: Type[django_models.Model], info: Info, **kwargs: Any
) -> django_models.Model:
    """``Model.objects.get`` limited to the request's organization."""
    return default_scoper.get_for_org(model, info, **kwargs)


async def aget_for_org(
    model: Type[django_models.Model], info: Info, **kwargs: Any
) -> django_models.Model:
    """Async ``Model.objects.aget`` limited to the request's organization."""
    return await default_scoper.aget_for_org(model, info, **kwargs)


def build_prescoped_queryset(
    info: Info,
    queryset: "django_models.QuerySet[Any]",
    field: str = "organization",
) -> "django_models.QuerySet[Any]":
    """Limit ``queryset`` to the request's organization."""
    return default_scoper.prescope(info, queryset, field=field)


def build_prescoper(
    field: str = "organization",
) -> Callable[["django_models.QuerySet[Any]", Info], "django_models.QuerySet[Any]"]:
    """Build a ``get_queryset`` callable that prescopes to the organization."""
    return default_scoper.prescoper(field=field)


__all__ = [
    "DEFAULT_MAX_PATH_DEPTH",
    "OrganizationScoper",
    "UnscopedModelError",
    "aget_for_org",
    "build_prescoped_queryset",
    "build_prescoper",
    "default_scoper",
    "field_argument",
    "for_org",
    "get_for_org",
    "organization_path",
]
