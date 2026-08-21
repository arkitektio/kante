"""Discriminated input unions: one flat wire type, derived from its members.

GraphQL has no input unions. A union that must arrive through an argument is
therefore wired as one *merged* input: a discriminator field, plus the union of
every member's fields, all of them optional. That type is honest on the wire but
silent about its structure -- nothing in it says that ``scale`` belongs to
``SCALE`` and ``reason`` to ``UNMAPPABLE``.

So each member is *also* published as a real input type that no field references,
annotated with :class:`unionElementOf`: which union it belongs to, which field
discriminates, and which discriminator value selects it. A generated client
rebuilds the tagged union from those annotations -- turms does exactly this, and
emits ``Annotated[A | B, Field(discriminator="kind")]``.

The members are the only place real information lives, so they are what you write::

    @union_member("TransformInput", key="SCALE")
    @kante.pydantic_input(ScaleTransformInputModel, description="The fields a SCALE member reads")
    class ScaleTransformInput:
        kind: TransformKind = strawberry.field(description="Which member of TransformInput this is")
        scale: list[float] = strawberry.field(description="The per-axis scale factors")

    @merged_input(
        members=[IdentityTransformInput, ScaleTransformInput, FieldTransformInput],
        noun="transformation",
        description="One edge of the coordinate graph, as a discriminated union",
    )
    class TransformInput:
        \"\"\"One authored edge of the coordinate graph, discriminated by `kind`.\"\"\"

    schema = kante.Schema(
        query=Query,
        types=union_member_types(TransformInput),
        schema_directives=[unionElementOf],
    )

The merged type is filled in from the members: every field optional, typed exactly
as the member types it -- so the ``ID``-versus-``str`` drift between a flat input and
its member models cannot happen -- and described as ``"(SCALE, BY_DIMENSION) ..."``,
the prefix computed from the members that actually read the field rather than
maintained by hand.

The strictness is :func:`parse_union_member`, which the generated ``to_pydantic``
calls: the member models forbid fields that are not their own, so a parameter that
contradicts the discriminator is an error naming both, never a silent drop.

.. warning::

   On a member declared with ``@kante.pydantic_input``, a field's description must be
   written on the **pydantic model** (``Field(description=...)``). Strawberry's pydantic
   integration takes the field's description from the model and ignores any
   ``strawberry.field(description=...)`` in the class body -- silently, so prose written
   there reaches neither the member's SDL nor the merged type derived from it.

.. warning::

   The member types are referenced by no field, so a schema that does not list them
   in ``types=[...]`` prunes them and ships an SDL with no trace of the union --
   silently. :func:`union_member_types` exists to be passed there.

.. note::

   ``@unionElementOf`` is only visible to codegen on an **SDL-sourced** schema. Under
   graphql-core 3.2 an introspected schema carries no ``ast_node``, and a client
   generator degrades to a plain input with no warning. Generate clients from printed
   SDL, not from an introspection endpoint.
"""

import dataclasses
import enum
import types
import typing
from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypeVar, cast

import strawberry
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from strawberry import UNSET
from strawberry.schema_directive import Location
from strawberry.types.base import StrawberryOptional

from kante.errors import camel_field, describe_validation_error

T = TypeVar("T")

#: Where :func:`union_member` stashes what it was told, for :func:`merged_input` to read.
_MEMBERSHIP_ATTR = "_kante_union_membership"

#: Where :func:`merged_input` stashes the member list, for :func:`union_member_types`.
_MEMBER_TYPES_ATTR = "_kante_union_member_types"


@strawberry.schema_directive(locations=[Location.INPUT_OBJECT], repeatable=True)
class unionElementOf:  # the lowercase class name IS the SDL directive name
    """Marks an input type as one member of a merged discriminated union input."""

    union: str = strawberry.field(
        description="The name of the merged input type this member belongs to"
    )
    discriminator: str = strawberry.field(
        description="The field of the merged input whose value selects a member"
    )
    key: str = strawberry.field(description="The discriminator value that selects this member")


@dataclasses.dataclass(frozen=True)
class _Membership:
    """One member's declared place in one or more unions."""

    unions: tuple[str, ...]
    key: str
    discriminator: str


def union_memberships(
    *unions: str, key: str, discriminator: str = "kind"
) -> list[unionElementOf]:
    """The directive instances declaring one member input's place in each named union.

    For passing to ``directives=`` by hand. :func:`union_member` is the shorter way,
    and the one :func:`merged_input` can read back.
    """
    return [
        unionElementOf(union=union, discriminator=discriminator, key=key) for union in unions
    ]


def union_member(
    *unions: str, key: str, discriminator: str = "kind"
) -> Callable[[type[T]], type[T]]:
    """Declare an already-built strawberry input to be a member of ``unions``.

    Applied *above* ``@kante.pydantic_input`` / ``@strawberry.input``: it appends the
    ``@unionElementOf`` directives to the finished type and records the membership so
    :func:`merged_input` can find the key without being told it twice. Several unions
    may be named, the directive being repeatable.
    """

    def wrap(cls: type[T]) -> type[T]:
        """Attach the directives and record the membership."""
        definition = getattr(cls, "__strawberry_definition__", None)
        if definition is None:
            raise TypeError(
                f"@union_member must be applied above @strawberry.input (or "
                f"@kante.pydantic_input) -- '{cls.__name__}' is not a strawberry type yet."
            )
        definition.directives = list(definition.directives or []) + union_memberships(
            *unions, key=key, discriminator=discriminator
        )
        setattr(
            cls,
            _MEMBERSHIP_ATTR,
            _Membership(unions=unions, key=key, discriminator=discriminator),
        )
        return cls

    return wrap


def parse_union_member(
    members: Mapping[str, type[BaseModel]],
    data: dict[str, Any],
    *,
    noun: str,
    discriminator: str = "kind",
    unknown_kind_error: str | None = None,
) -> BaseModel:
    """Match a merged discriminated input's fields to its member model, strictly.

    ``data`` is the merged input's supplied fields (omitted ones absent); the member
    model carries only its own fields and forbids the rest, so this is where a field
    that contradicts the discriminator becomes an error instead of a silent drop.
    ``noun`` names the thing in messages ("transformation", "derivation");
    ``unknown_kind_error`` is a format string with ``{kind}`` and ``{noun}``
    placeholders, replacing the message for a discriminator value this union has no
    member for -- the place to say what the caller should use instead.
    """
    raw = data.get(discriminator)
    # The merged input types the discriminator as a strawberry enum, but the member
    # models tag themselves with a `Literal` of its *value*; the member keys follow the
    # models. A plain string arrives already in that form.
    kind = raw.value if isinstance(raw, enum.Enum) else raw
    data = {**data, discriminator: kind}

    member = members.get(cast(str, kind))
    if member is None:
        template = unknown_kind_error or "A {noun} cannot be a {kind}."
        raise ValueError(template.format(kind=kind, noun=noun))

    try:
        return member.model_validate(data)
    except PydanticValidationError as err:
        raise ValueError(
            _member_mismatch(
                err, member=member, kind=str(kind), noun=noun, discriminator=discriminator
            )
        ) from err


def _an(kind: str) -> str:
    """``kind`` behind the article that reads right before it."""
    return f"An {kind}" if kind[:1] in "AEIOU" else f"A {kind}"


def _member_mismatch(
    err: PydanticValidationError,
    *,
    member: type[BaseModel],
    kind: str,
    noun: str,
    discriminator: str,
) -> str:
    """Restate a member model's failure as a sentence naming the field and the kind."""
    reads = [camel_field(name) for name in member.model_fields if name != discriminator]
    reads_clause = (
        "it reads " + ", ".join(f"`{name}`" for name in reads)
        if reads
        else "it takes no parameters at all"
    )
    for detail in err.errors():
        loc = [str(part) for part in detail["loc"] if str(part) != discriminator]
        field = camel_field(loc[0]) if loc else discriminator
        if detail["type"] == "extra_forbidden":
            return (
                f"{_an(kind)} {noun} does not read `{field}`: {reads_clause}. "
                "Drop it, or pick the kind that reads it."
            )
        if detail["type"] == "missing":
            return f"{_an(kind)} {noun} requires `{field}`"
    return describe_validation_error(err)


def union_member_types(cls: type[Any]) -> list[type]:
    """The member input types of a :func:`merged_input`, for ``Schema(types=[...])``.

    Nothing references them, so a schema that omits them prunes them and publishes an
    SDL with no trace of the union.
    """
    members = getattr(cls, _MEMBER_TYPES_ATTR, None)
    if members is None:
        raise TypeError(f"'{cls.__name__}' is not a @merged_input, so it has no members.")
    return list(cast("Sequence[type]", members))


def _optional(annotation: Any) -> Any:
    """``annotation`` widened to admit ``None``, idempotently.

    The annotation comes from the member's resolved strawberry field rather than from
    its ``__annotations__``: ``@kante.pydantic_input`` rewrites those into strawberry's
    own ``StrawberryList``/``StrawberryOptional`` wrappers, which no ``| None`` accepts.
    Taking the resolved type is also what makes the merged field's GraphQL type the
    member's *by construction* -- ``ID`` stays ``ID``.
    """
    if isinstance(annotation, StrawberryOptional) or _admits_none(annotation):
        return annotation
    return StrawberryOptional(annotation)


def _admits_none(annotation: Any) -> bool:
    """Whether ``annotation`` is already a plain typing union containing ``None``."""
    if typing.get_origin(annotation) not in (typing.Union, types.UnionType):
        return False
    return type(None) in typing.get_args(annotation)


def _lower(value: Any) -> Any:
    """A supplied field value as the member models want it.

    A nested union input is corrected to its own member model *first*, so a bad
    transform inside a derivation is reported as a transform error rather than as a
    shapeless one about the derivation. Lists are lowered element by element.
    """
    if hasattr(value, "to_pydantic"):
        return value.to_pydantic()
    if isinstance(value, (list, tuple)):
        return [_lower(item) for item in value]
    return value


def _member_model(member: type[Any]) -> type[BaseModel]:
    """The pydantic model behind a member input, or a message saying how to give it one."""
    model = getattr(member, "_pydantic_type", None)
    if model is None:
        raise TypeError(
            f"Union member '{member.__name__}' has no pydantic model: declare it with "
            "@kante.pydantic_input(Model), which is what makes the member strict."
        )
    return cast("type[BaseModel]", model)


def _spec_models(spec: Any) -> set[type[BaseModel]]:
    """The member models of an ``Annotated[A | B, Field(discriminator=...)]`` alias."""
    args = typing.get_args(spec)
    union = args[0] if args else spec
    return set(typing.get_args(union))


def merged_input(
    *,
    members: Sequence[type[Any]],
    noun: str,
    description: str | None = None,
    discriminator: str = "kind",
    unknown_kind_error: str | None = None,
    descriptions: Mapping[str, str] | None = None,
    spec: Any = None,
    name: str | None = None,
) -> Callable[[type[T]], type[T]]:
    """Fill an empty class with the merge of ``members``, as the union's wire type.

    The decorated class is written with a docstring and nothing else: every field is
    derived from the members, optional, and typed exactly as the member types it. Each
    description is the member's own, under a ``"(SCALE, BY_DIMENSION) "`` prefix naming
    the members that read the field -- so the prefix cannot go stale. ``descriptions``
    replaces the body of one for the merged type only, the prefix still computed;
    pass the discriminator's name to describe the discriminator, which is never prefixed.

    Every member must name *this* union in its :func:`union_member`. The union it names
    is what the ``@unionElementOf`` directive publishes, so a member merged into a type
    it never claimed would ship an SDL pointing codegen at a different union -- the
    server would accept the field and the generated client would not have it. The name
    compared against is ``name``, or the decorated class's own if none is given.

    ``noun`` names the thing in error messages, and ``unknown_kind_error`` overrides
    the message for a discriminator value no member claims -- both are handed to
    :func:`parse_union_member` by the generated ``to_pydantic``.

    ``spec`` optionally takes the static ``Annotated[A | B, Field(discriminator=...)]``
    alias the resolvers carry, and asserts it holds exactly these members -- the one
    registry a type checker needs written out, and therefore the one that can drift.
    """
    if not members:
        raise TypeError("A merged input needs at least one member.")
    overrides = dict(descriptions or {})

    def wrap(cls: type[T]) -> type[T]:
        """Derive the merged fields, the dispatch and the member list."""
        union_name = name or cls.__name__
        models: dict[str, type[BaseModel]] = {}
        annotations: dict[str, Any] = {}
        read_by: dict[str, list[str]] = {}
        declared_in: dict[str, str] = {}
        field_descriptions: dict[str, str] = {}
        discriminator_annotation: Any = None
        discriminator_description: str | None = None

        for member in members:
            membership = cast("_Membership | None", getattr(member, _MEMBERSHIP_ATTR, None))
            if membership is None:
                raise TypeError(
                    f"Union member '{member.__name__}' is not declared with @union_member, "
                    "so it carries no key and no @unionElementOf directive."
                )
            if union_name not in membership.unions:
                claimed = ", ".join(f"'{one}'" for one in membership.unions)
                raise TypeError(
                    f"'{member.__name__}' is a member of {claimed}, not of '{union_name}': "
                    "its @unionElementOf would point a generated client at another union."
                )
            if membership.discriminator != discriminator:
                raise TypeError(
                    f"'{member.__name__}' discriminates on '{membership.discriminator}', but "
                    f"'{cls.__name__}' discriminates on '{discriminator}'."
                )
            if membership.key in models:
                raise TypeError(
                    f"Two members of '{cls.__name__}' claim the key '{membership.key}'."
                )

            model = _member_model(member)
            if model.model_config.get("extra") != "forbid":
                raise TypeError(
                    f"The model behind '{member.__name__}' must set "
                    'ConfigDict(extra="forbid"): forbidding the other members\' fields is '
                    "what makes a contradicting parameter an error rather than a silent drop."
                )
            models[membership.key] = model

            definitions = {
                field.python_name: field for field in member.__strawberry_definition__.fields
            }
            if discriminator not in definitions:
                raise TypeError(
                    f"Union member '{member.__name__}' does not declare the discriminator "
                    f"'{discriminator}', so a client cannot tell which member it is."
                )
            if discriminator_annotation is None:
                discriminator_annotation = definitions[discriminator].type
                discriminator_description = definitions[discriminator].description
            elif definitions[discriminator].type != discriminator_annotation:
                raise TypeError(
                    f"Members of '{cls.__name__}' disagree on the type of the discriminator "
                    f"'{discriminator}'."
                )

            for field_name, definition in definitions.items():
                if field_name == discriminator:
                    continue
                annotation = _optional(definition.type)
                if field_name not in annotations:
                    annotations[field_name] = annotation
                    declared_in[field_name] = member.__name__
                    field_descriptions[field_name] = definition.description or ""
                elif annotations[field_name] != annotation:
                    raise TypeError(
                        f"'{declared_in[field_name]}' and '{member.__name__}' disagree on the "
                        f"type of `{field_name}`, so '{cls.__name__}' cannot carry both."
                    )
                read_by.setdefault(field_name, []).append(membership.key)

        if spec is not None and _spec_models(spec) != set(models.values()):
            raise TypeError(
                f"The `spec` alias passed to '{cls.__name__}' does not hold exactly its "
                "members; one of the two has drifted."
            )

        # The discriminator leads, then every member's fields in the order the members
        # declare them -- so the SDL reads in the order the union was written.
        merged: dict[str, Any] = {discriminator: discriminator_annotation}
        merged.update(annotations)
        cls.__annotations__ = merged

        setattr(
            cls,
            discriminator,
            strawberry.field(
                description=overrides.get(discriminator, discriminator_description)
            ),
        )
        for field_name in annotations:
            body = overrides.get(field_name, field_descriptions[field_name])
            prefix = "(" + ", ".join(read_by[field_name]) + ") "
            setattr(
                cls,
                field_name,
                strawberry.field(default=None, description=prefix + body if body else prefix.strip()),
            )

        wire_fields = tuple(merged)

        def to_pydantic(self: Any) -> BaseModel:
            """Match the merged wire fields to the member model `kind` selects, strictly."""
            data: dict[str, Any] = {}
            for field_name in wire_fields:
                value = getattr(self, field_name)
                if value is None or value is UNSET:
                    continue
                data[field_name] = _lower(value)
            return parse_union_member(
                models,
                data,
                noun=noun,
                discriminator=discriminator,
                unknown_kind_error=unknown_kind_error,
            )

        cls.to_pydantic = to_pydantic  # type: ignore[attr-defined]
        setattr(cls, _MEMBER_TYPES_ATTR, tuple(members))
        strawberry.input(cls, description=description, name=name)
        return cls

    return wrap


__all__ = [
    "merged_input",
    "parse_union_member",
    "unionElementOf",
    "union_member",
    "union_member_types",
    "union_memberships",
]
