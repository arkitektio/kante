"""Type and field decorators: strawberry re-exports plus federation support.

.. warning::

   The plain re-exports below (``type``, ``input``, ``interface``, ``mutation``,
   ``field``, ``scalar``, ...) are module-level *aliases* of strawberry's
   overloaded decorators, and mypy does not carry an overload set across an
   alias. Decorating with ``@kante.type`` therefore resolves the class to
   ``builtins.type`` and every keyword of its constructor is reported as
   unexpected::

       @kante.type
       class Me:
           id: str

       Me(id="1")  # error: Unexpected keyword argument "id" for "Me"

   The same code type-checks correctly with ``@strawberry.type``. **Prefer
   importing these directly from strawberry / strawberry_django**; they are kept
   here only for backwards compatibility and add nothing over the originals.

   What is worth importing from kante is what is actually *implemented* here:
   :func:`django_type` (federation ``@key`` plus a batching
   ``resolve_reference``) and :func:`django_interface`.
"""

from typing import (
    Any,
    cast,
    Callable,
    List,
    Literal,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
)

import strawberry
import strawberry_django
from django.db.models import Model, QuerySet
from strawberry.dataloader import DataLoader
from strawberry.experimental import pydantic
from strawberry.federation.schema_directives import (
    Key,
)
from strawberry.types import Info
from strawberry_django.fields.field import StrawberryDjangoField
from strawberry_django.utils.typing import (
    AnnotateType,
    PrefetchType,
    TypeOrMapping,
    TypeOrSequence,
)
from strawberry_django import filters
from strawberry_django import filter_field as sfilter_field
from strawberry_django import input as sdjango_input


filter_type = filters.filter_type
filter_field = sfilter_field

django_mutation = strawberry_django.mutation
mutation = strawberry.mutation

django_input = sdjango_input
input = strawberry.input

scalar = strawberry.scalar

interface = strawberry.interface
subscription = strawberry.subscription
type = strawberry.type
field = strawberry.field
pydantic_type = pydantic.type
pydantic_input = pydantic.input
django_field = strawberry_django.field

T = TypeVar("T", bound=object)

DjangoTypeDecorator = Callable[
    [Type[T]],
    Type[T],
]


REFERENCE_QUERYSET_SETTING = "KANTE_REFERENCE_QUERYSET"
"""Django setting naming the ``(model, info) -> QuerySet`` that scopes references.

A dotted path, e.g. ``"core.scoping.for_org"``. A service that keeps its own
scoper (its own list of deliberately unscoped models, its own path depth) points
this at it, so federation resolves references under the same rule as the
service's single-object queries. Unset, it is :func:`kante.scoping.for_org`.
"""

ReferenceQueryset = Callable[[Type[Model], Info], "QuerySet[Any]"]


def _reference_queryset() -> ReferenceQueryset:
    """The callable that scopes a federated reference lookup to the request.

    Looked up whenever a loader is built (once per request and model), so a
    settings override takes effect without a restart. ``import_string`` is a
    dictionary lookup after the first call.
    """
    from django.conf import settings
    from django.utils.module_loading import import_string

    path = getattr(settings, REFERENCE_QUERYSET_SETTING, None)
    if path is None:
        # Imported here: kante.scoping is optional for a service that never
        # federates, and importing it eagerly would tie every kante type to it.
        from kante.scoping import for_org

        return for_org
    return cast(ReferenceQueryset, import_string(path))


def _build_reference_loader(
    model: Type[Model], info: Info, type_cls: Optional[Type[object]] = None
) -> DataLoader[str, Optional[Model]]:
    """Build a DataLoader that batches federation reference lookups by id.

    A federation gateway batches references into a single ``_entities`` query,
    but strawberry calls ``resolve_reference`` once per representation. Without
    batching that is one DB query per referenced entity (N+1). This loader
    collapses all ids requested within one event-loop tick into a single
    ``filter(id__in=...)`` query.

    The lookup is **scoped to the request**, exactly like any other single-object
    access: it starts from the service's reference queryset (the request's
    organization, see :data:`REFERENCE_QUERYSET_SETTING`) and then goes through
    the type's own ``get_queryset`` when it has one. ``_entities`` takes ids
    straight from the caller, so an unscoped lookup here would hand any
    authenticated client any organization's rows. A row the request may not see
    resolves to ``None``, the same as an id that does not exist.

    A model with no path to an organization raises
    :class:`kante.scoping.UnscopedModelError` rather than being served unscoped.
    Declare it on the scoper, or pass ``federated=False``.
    """

    async def load_fn(keys: List[str]) -> List[Optional[Model]]:
        queryset = _reference_queryset()(model, info)
        get_queryset = getattr(type_cls, "get_queryset", None)
        if get_queryset is not None:
            queryset = get_queryset(queryset, info)
        objects = {
            str(obj.id): obj
            async for obj in queryset.filter(id__in=list(keys))
        }
        return [objects.get(str(key)) for key in keys]

    return DataLoader(load_fn=load_fn)


def _get_reference_loader(
    info: Info, model: Type[Model], type_cls: Optional[Type[object]] = None
) -> DataLoader[str, Optional[Model]]:
    """Return a per-request reference loader, cached on the context.

    The loader must be shared across the representations of a single request for
    batching to work, so it is stashed in the context's ``_loaders`` store. If
    the context cannot hold it (no ``_loaders``), fall back to an unbatched
    loader -- still correct, just no batching.

    Caching per request is also what makes it safe for the loader to close over
    ``info``: a request has one organization, and the loader never outlives it.
    """
    store = getattr(info.context, "_loaders", None)
    if store is None:
        return _build_reference_loader(model, info, type_cls)
    # Per type, not per model: two types on one model may define different
    # ``get_queryset``s, and the loader applies the one it was built with.
    type_name = getattr(type_cls, "__name__", "")
    key = f"federation_ref:{model._meta.label}:{type_name}"
    loader: Optional[DataLoader[str, Optional[Model]]] = store.get(key)
    if loader is None:
        loader = _build_reference_loader(model, info, type_cls)
        store[key] = loader
    return loader


def django_type(
    model: Type[Model],
    name: Optional[str] = None,
    field_cls: Type[StrawberryDjangoField] = StrawberryDjangoField,
    is_input: bool = False,
    is_interface: bool = False,
    is_filter: Union[Literal["lookups"], bool] = False,
    description: Optional[str] = None,
    directives: Optional[Sequence[object]] = (),
    extend: bool = False,
    filters: Optional[Type[object]] = None,
    order: Optional[Type[object]] = None,
    ordering: Optional[Type[object]] = None,
    pagination: bool = False,
    only: Optional[TypeOrSequence[str]] = None,
    select_related: Optional[TypeOrSequence[str]] = None,
    prefetch_related: Optional[TypeOrSequence[PrefetchType]] = None,
    annotate: Optional[TypeOrMapping[AnnotateType]] = None,
    disable_optimization: bool = False,
    fields: Optional[Union[list[str], Literal["__all__"]]] = None,
    exclude: Optional[list[str]] = None,
    federated: bool = True,
) -> Callable[
    [Type[T]],
    Type[T],
]:
    """Map a Django model onto a strawberry type, with federation support.

    With ``federated=True`` (the default) the type gains an ``@key(fields: "id")``
    directive and, unless it defines one itself, a ``resolve_reference`` that
    batches entity lookups through a per-request DataLoader. That lookup is scoped
    to the request's organization and goes through the type's ``get_queryset``
    (see :func:`_build_reference_loader`); a model with no path to an organization
    must be declared unscoped on the service's scoper, or not be federated.
    """
    if federated:
        directives = list(directives or [])
        # ``Key`` is annotated as taking a ``FieldSet`` scalar; "id" is the
        # field-set literal that scalar wraps.
        directives.append(Key(fields=cast(Any, "id")))

    def wrapper(cls: Type[T]) -> Type[T]:
        """A decorator to create a Django type with federation support."""

        if federated:
            # Check if id field is defined in type annotations
            annotations = getattr(cls, "__annotations__", {})
            # Explicit raise, not ``assert``: under ``python -O`` an assert is
            # stripped, and the failure mode becomes a schema that advertises
            # ``@key(fields: "id")`` on a type with no ``id`` -- a federation
            # error at gateway composition time, far from its cause.
            if "id" not in annotations:
                raise TypeError(
                    f"{cls.__name__} is declared with federated=True but has no 'id' "
                    "field annotation. Federation keys on 'id', so the type must "
                    "declare one (or pass federated=False)."
                )

            # Check if resolve_reference method is defined in the class
            # Note: kante federation will add this if not present
            if not hasattr(cls, "resolve_reference"):
                # Add a default resolve_reference that batches lookups by id via
                # a per-request DataLoader, avoiding N+1 across federated joins.
                async def resolve_reference(
                    cls: Type[object], info: Info, id: str
                ) -> object:
                    loader = _get_reference_loader(info, model, cls)
                    return await loader.load(id)

                setattr(cls, "resolve_reference", classmethod(resolve_reference))

        return strawberry_django.type(
            model,
            name=name,
            field_cls=field_cls,
            is_input=is_input,
            is_interface=is_interface,
            is_filter=is_filter,
            description=description,
            directives=directives,
            extend=extend,
            filters=filters,
            order=order,
            ordering=ordering,
            pagination=pagination,
            only=only,
            select_related=select_related,
            prefetch_related=prefetch_related,
            annotate=annotate,
            disable_optimization=disable_optimization,
            fields=fields,
            exclude=exclude,
        )(cls)

    return wrapper


def django_interface(
    model: Type[Model],
    name: Optional[str] = None,
    field_cls: Type[StrawberryDjangoField] = StrawberryDjangoField,
    description: Optional[str] = None,
    directives: Optional[Sequence[object]] = (),
) -> Callable[[Type[T]], Type[T]]:
    """Decorator to create a Django interface type."""

    def wrapper(cls: Type[T]) -> Type[T]:
        """A decorator to create a Django interface type."""
        return strawberry_django.interface(
            model,
            name=name,
            field_cls=field_cls,
            description=description,
            directives=directives,
        )(cls)

    return wrapper
