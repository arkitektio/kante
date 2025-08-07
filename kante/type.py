from typing import (
    Callable,
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
filter = filters.filter
filter_field = sfilter_field

django_input = sdjango_input
input = strawberry.input

scalar = strawberry.scalar  # type: ignore[assignment]

interface = strawberry.interface
subscription = strawberry.subscription
type = strawberry.type
field = strawberry.field
pydantic_type = pydantic.type
django_field = strawberry_django.field

T = TypeVar("T", bound=object)

DjangoTypeDecorator = Callable[
    [Type[T]],
    Type[T],
]


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
    federated: bool = False,
) -> Callable[
    [Type[T]],
    Type[T],
]:
    if federated:
        directives = list(directives or [])
        directives.append(Key(fields="id"))

    def wrapper(cls: Type[T]) -> Type[T]:
        """A decorator to create a Django type with federation support."""

        if federated:
            # Check if id field is defined in type annotations
            annotations = getattr(cls, "__annotations__", {})
            assert "id" in annotations, (
                "Django type must have an 'id' field annotation for federation"
            )

            # Check if resolve_reference method is defined in the class
            # Note: kante federation will add this if not present
            if not hasattr(cls, "resolve_reference"):
                # Add a default resolve_reference method that looks up by id
                def resolve_reference(cls: Type[object], info: Info, id: str) -> object:
                    return model.objects.aget(id=id)

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
