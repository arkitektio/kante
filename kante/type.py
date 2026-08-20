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
from django.db.models import Model
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


def _build_reference_loader(model: Type[Model]) -> DataLoader[str, Optional[Model]]:
    """Build a DataLoader that batches federation reference lookups by id.

    A federation gateway batches references into a single ``_entities`` query,
    but strawberry calls ``resolve_reference`` once per representation. Without
    batching that is one DB query per referenced entity (N+1). This loader
    collapses all ids requested within one event-loop tick into a single
    ``filter(id__in=...)`` query.
    """

    async def load_fn(keys: List[str]) -> List[Optional[Model]]:
        manager = cast("Any", model._default_manager)
        objects = {
            str(obj.id): obj
            async for obj in manager.filter(id__in=list(keys))
        }
        return [objects.get(str(key)) for key in keys]

    return DataLoader(load_fn=load_fn)


def _get_reference_loader(
    context: Any, model: Type[Model]
) -> DataLoader[str, Optional[Model]]:
    """Return a per-request reference loader, cached on the context.

    The loader must be shared across the representations of a single request for
    batching to work, so it is stashed in the context's ``_loaders`` store. If
    the context cannot hold it (no ``_loaders``), fall back to an unbatched
    loader -- still correct, just no batching.
    """
    store = getattr(context, "_loaders", None)
    if store is None:
        return _build_reference_loader(model)
    key = f"federation_ref:{model._meta.label}"
    loader: Optional[DataLoader[str, Optional[Model]]] = store.get(key)
    if loader is None:
        loader = _build_reference_loader(model)
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
    batches entity lookups through a per-request DataLoader.
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
                    loader = _get_reference_loader(info.context, model)
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
