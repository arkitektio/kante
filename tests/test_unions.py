"""Tests for kante.unions: the discriminated input union builder.

The load-bearing test is `test_sdl_matches_the_codegen_contract`: turms compares the
directive name and arguments literally, so the SDL these produce is a contract with
every generated client, not an implementation detail.
"""

import enum
from typing import Literal, cast

import pytest
import strawberry
from pydantic import BaseModel, ConfigDict, Field

import kante
from kante.unions import merged_input, union_member, union_member_types, unionElementOf


@strawberry.enum
class ThingKind(enum.Enum):
    """The discriminator of the thing union."""

    SCALE = "SCALE"
    FIELD = "FIELD"
    NOTHING = "NOTHING"


class ScaleThingModel(BaseModel):
    """A thing with per-axis factors."""

    kind: Literal["SCALE"] = "SCALE"
    scale: list[float] = Field(description="The per-axis factors")
    model_config = ConfigDict(extra="forbid")


class FieldThingModel(BaseModel):
    """A thing that names another object."""

    kind: Literal["FIELD"] = "FIELD"
    field: str = Field(description="The object it names, at length")
    labels: list[str] = Field(default=[], description="Its labels")
    model_config = ConfigDict(extra="forbid")


class NothingThingModel(BaseModel):
    """A thing with no parameters at all."""

    kind: Literal["NOTHING"] = "NOTHING"
    model_config = ConfigDict(extra="forbid")


@union_member("ThingInput", key="SCALE")
@kante.pydantic_input(ScaleThingModel, description="The fields a SCALE thing reads")
class ScaleThingInput:
    """The SCALE member."""

    kind: ThingKind
    scale: list[float]


@union_member("ThingInput", key="FIELD")
@kante.pydantic_input(FieldThingModel, description="The fields a FIELD thing reads")
class FieldThingInput:
    """The FIELD member."""

    kind: ThingKind
    field: strawberry.ID
    labels: list[str]


@union_member("ThingInput", key="NOTHING")
@kante.pydantic_input(NothingThingModel, description="The fields a NOTHING thing reads")
class NothingThingInput:
    """The NOTHING member."""

    kind: ThingKind


@merged_input(
    members=[ScaleThingInput, FieldThingInput, NothingThingInput],
    noun="thing",
    description="One thing, as a discriminated union",
    unknown_kind_error="A {noun} cannot be a {kind}. Pick SCALE, FIELD or NOTHING.",
    descriptions={
        "kind": "Which member of ThingInput this is",
        "labels": "The labels, said more briefly than the member says it",
    },
)
class ThingInput:
    """One authored thing, discriminated by `kind`."""


@strawberry.type
class Query:
    """A query annotating the merged input, which is the point of generating it."""

    @strawberry.field
    def describe(self, thing: ThingInput) -> str:
        """Round-trip a thing through its member model."""
        return type(thing.to_pydantic()).__name__  # type: ignore[attr-defined]


def build_schema(with_members: bool = True) -> strawberry.Schema:
    """The test schema, optionally omitting the member types (the pruning trap)."""
    return strawberry.Schema(
        query=Query,
        types=union_member_types(ThingInput) if with_members else [],
        schema_directives=[unionElementOf],
    )


# --------------------------------------------------------------------------
# the codegen contract
# --------------------------------------------------------------------------


def test_sdl_matches_the_codegen_contract() -> None:
    """The directive and its applications must print exactly as turms parses them."""
    sdl = str(build_schema())

    assert (
        "directive @unionElementOf(union: String!, discriminator: String!, key: String!) "
        "repeatable on INPUT_OBJECT" in sdl
    )
    assert (
        'input ScaleThingInput @unionElementOf(union: "ThingInput", discriminator: "kind", '
        'key: "SCALE")' in sdl
    )
    assert (
        'input NothingThingInput @unionElementOf(union: "ThingInput", discriminator: "kind", '
        'key: "NOTHING")' in sdl
    )


def test_members_vanish_from_the_sdl_when_not_registered() -> None:
    """Nothing references the members, so a schema that omits them prunes them silently."""
    assert "input ScaleThingInput" in str(build_schema())
    assert "input ScaleThingInput" not in str(build_schema(with_members=False))


def test_union_member_types_returns_exactly_the_members() -> None:
    """The list handed to ``Schema(types=...)`` is the member list, in order."""
    assert union_member_types(ThingInput) == [
        ScaleThingInput,
        FieldThingInput,
        NothingThingInput,
    ]


def test_union_member_types_refuses_a_plain_type() -> None:
    """A type that is not a merged input has no member list to give."""
    with pytest.raises(TypeError, match="not a @merged_input"):
        union_member_types(ScaleThingInput)


# --------------------------------------------------------------------------
# the generated merged type
# --------------------------------------------------------------------------


def test_merged_type_carries_every_member_field_optionally() -> None:
    """Each member's fields appear on the merged type, all defaulted to null."""
    sdl = str(build_schema())
    merged = sdl.split("input ThingInput {")[1].split("}")[0]

    assert "kind: ThingKind!" in merged
    assert "scale: [Float!] = null" in merged
    assert "labels: [String!] = null" in merged


def test_merged_type_keeps_the_members_field_types() -> None:
    """`ID` stays `ID`: the merged field is typed by the member, not re-declared."""
    sdl = str(build_schema())
    merged = sdl.split("input ThingInput {")[1].split("}")[0]

    assert "field: ID = null" in merged
    assert "field: ID!" in sdl.split("input FieldThingInput")[1]


def test_merged_descriptions_carry_a_computed_prefix() -> None:
    """The `(KIND) ` prefix names the members that read the field, and cannot go stale."""
    sdl = str(build_schema())
    merged = sdl.split("input ThingInput {")[1].split("}")[0]

    assert '"""(SCALE) The per-axis factors"""' in merged
    assert '"""(FIELD) The object it names, at length"""' in merged
    # The discriminator is every member's, so it is never prefixed.
    assert '"""Which member of ThingInput this is"""' in merged


def test_a_description_override_keeps_the_computed_prefix() -> None:
    """An override replaces the body only -- the prefix is still derived from the members."""
    sdl = str(build_schema())
    merged = sdl.split("input ThingInput {")[1].split("}")[0]

    assert '"""(FIELD) The labels, said more briefly than the member says it"""' in merged
    # The member keeps its own, longer description.
    assert '"""Its labels"""' in sdl.split("input FieldThingInput")[1]


def test_the_merged_input_is_usable_as_an_annotation() -> None:
    """The decorated class stays a real class, so a resolver can annotate with it."""
    result = build_schema().execute_sync(
        '{ describe(thing: { kind: SCALE, scale: [1.0, 2.0] }) }'
    )
    assert result.errors is None
    assert result.data == {"describe": "ScaleThingModel"}


# --------------------------------------------------------------------------
# dispatch
# --------------------------------------------------------------------------


def _to_pydantic(**kwargs: object) -> BaseModel:
    """Build a merged input straight from kwargs and lower it."""
    supplied: dict[str, object] = {"kind": None, "scale": None, "field": None, "labels": None}
    supplied.update(kwargs)
    thing = ThingInput(**supplied)  # type: ignore[call-arg]
    return cast(BaseModel, thing.to_pydantic())  # type: ignore[attr-defined]


def test_dispatch_picks_the_member_the_discriminator_selects() -> None:
    """Each kind lowers to its own member model."""
    assert isinstance(_to_pydantic(kind=ThingKind.SCALE, scale=[1.0]), ScaleThingModel)
    assert isinstance(_to_pydantic(kind=ThingKind.FIELD, field="7"), FieldThingModel)
    assert isinstance(_to_pydantic(kind=ThingKind.NOTHING), NothingThingModel)


def test_a_field_the_kind_does_not_read_is_an_error_naming_both() -> None:
    """The whole point: a contradicting parameter is refused, never silently dropped."""
    with pytest.raises(ValueError) as err:
        _to_pydantic(kind=ThingKind.SCALE, scale=[1.0], field="7")

    message = str(err.value)
    assert "`field`" in message
    assert "SCALE" in message
    assert "it reads `scale`" in message


def test_a_member_with_no_parameters_says_so() -> None:
    """A member that reads nothing gets a sentence that reads, not an empty list."""
    with pytest.raises(ValueError, match="it takes no parameters at all"):
        _to_pydantic(kind=ThingKind.NOTHING, scale=[1.0])


def test_a_missing_required_field_names_it() -> None:
    """A kind that requires a field says which one."""
    with pytest.raises(ValueError, match=r"A SCALE thing requires `scale`"):
        _to_pydantic(kind=ThingKind.SCALE)


def test_an_unknown_kind_uses_the_supplied_message() -> None:
    """``unknown_kind_error`` is where a union says what the caller should use instead."""
    with pytest.raises(ValueError, match="Pick SCALE, FIELD or NOTHING"):
        _to_pydantic(kind="ROTATION")


def test_an_omitted_list_falls_back_to_the_models_default() -> None:
    """The merged field defaults to null, so an omitted list is the model's default, not None.

    The asymmetry is deliberate: the member declares `labels: [String!]! = []`, the merged
    field `labels: [String!] = null`. Null on the merged type means "not supplied", and the
    member model is what decides what not-supplied means.
    """
    model = _to_pydantic(kind=ThingKind.FIELD, field="7")
    assert isinstance(model, FieldThingModel)
    assert model.labels == []


def test_an_empty_list_survives_the_flattening() -> None:
    """`[]` is a supplied value, not an omitted one -- only None and UNSET are dropped."""
    model = _to_pydantic(kind=ThingKind.FIELD, field="7", labels=[])
    assert isinstance(model, FieldThingModel)
    assert model.labels == []


# --------------------------------------------------------------------------
# nested unions
# --------------------------------------------------------------------------


class OuterModel(BaseModel):
    """An outer thing carrying a nested union member."""

    kind: Literal["SCALE"] = "SCALE"
    inner: ScaleThingModel | FieldThingModel | NothingThingModel = Field(
        description="The nested thing"
    )
    model_config = ConfigDict(extra="forbid")


@union_member("OuterInput", key="SCALE")
@kante.pydantic_input(OuterModel, description="The fields an outer reads")
class OuterInput:
    """The only member of the outer union."""

    kind: ThingKind
    inner: ThingInput


def test_a_nested_union_is_corrected_before_its_parent() -> None:
    """The inner union lowers first, so a bad inner is reported as an inner error."""

    @merged_input(members=[OuterInput], noun="outer", name="OuterInput")
    class OuterInput_:
        """The outer merged input."""

    inner = ThingInput(kind=ThingKind.SCALE, scale=[1.0], field=None, labels=None)  # type: ignore[call-arg]
    outer = OuterInput_(kind=ThingKind.SCALE, inner=inner)  # type: ignore[call-arg]
    model = outer.to_pydantic()  # type: ignore[attr-defined]
    assert isinstance(model, OuterModel)
    assert isinstance(model.inner, ScaleThingModel)

    bad = ThingInput(kind=ThingKind.SCALE, scale=[1.0], field="7", labels=None)  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="A SCALE thing does not read `field`"):
        OuterInput_(kind=ThingKind.SCALE, inner=bad).to_pydantic()  # type: ignore[call-arg]


# --------------------------------------------------------------------------
# import-time validation
# --------------------------------------------------------------------------


class LooseModel(BaseModel):
    """A member model that accepts and discards strays."""

    kind: Literal["LOOSE"] = "LOOSE"


@union_member("LooseInput", key="LOOSE")
@kante.pydantic_input(LooseModel)
class LooseInput:
    """A member whose model is not strict."""

    kind: ThingKind = strawberry.field(description="Which member this is")


def test_a_lax_member_is_refused() -> None:
    """Without ``extra="forbid"`` a stray field is dropped, which is the bug this prevents."""
    with pytest.raises(TypeError, match='extra="forbid"'):

        @merged_input(members=[LooseInput], noun="loose", name="LooseInput")
        class _Merged:
            """A merged input over a lax member."""


def test_an_undeclared_member_is_refused() -> None:
    """A member without @union_member carries no key and no directive."""

    @kante.pydantic_input(ScaleThingModel)
    class Undeclared:
        """A member that was never declared."""

        kind: ThingKind = strawberry.field(description="Which member this is")
        scale: list[float] = strawberry.field(description="The factors")

    with pytest.raises(TypeError, match="not declared with @union_member"):

        @merged_input(members=[Undeclared], noun="thing")
        class _Merged:
            """A merged input over an undeclared member."""


def test_members_disagreeing_on_a_field_type_are_refused() -> None:
    """Two members cannot give one merged field two types."""

    class OtherScaleModel(BaseModel):
        """A member typing `scale` differently."""

        kind: Literal["OTHER"] = "OTHER"
        scale: list[str]
        model_config = ConfigDict(extra="forbid")

    @union_member("ClashInput", key="SCALE")
    @kante.pydantic_input(ScaleThingModel)
    class ClashScaleInput:
        """A member typing `scale` as floats."""

        kind: ThingKind
        scale: list[float]

    @union_member("ClashInput", key="OTHER")
    @kante.pydantic_input(OtherScaleModel)
    class OtherScaleInput:
        """The clashing member."""

        kind: ThingKind = strawberry.field(description="Which member this is")
        scale: list[str] = strawberry.field(description="The factors, as strings")

    with pytest.raises(TypeError, match="disagree on the type of `scale`"):

        @merged_input(
            members=[ClashScaleInput, OtherScaleInput], noun="thing", name="ClashInput"
        )
        class _Merged:
            """A merged input over clashing members."""


def test_two_members_claiming_one_key_are_refused() -> None:
    """A key selects exactly one member, or the dispatch is ambiguous."""

    @union_member("DupInput", key="SCALE")
    @kante.pydantic_input(ScaleThingModel)
    class FirstDupInput:
        """The first member claiming SCALE."""

        kind: ThingKind
        scale: list[float]

    @union_member("DupInput", key="SCALE")
    @kante.pydantic_input(ScaleThingModel)
    class DuplicateInput:
        """A second member claiming SCALE."""

        kind: ThingKind = strawberry.field(description="Which member this is")
        scale: list[float] = strawberry.field(description="The factors")

    with pytest.raises(TypeError, match="claim the key 'SCALE'"):

        @merged_input(
            members=[FirstDupInput, DuplicateInput], noun="thing", name="DupInput"
        )
        class _Merged:
            """A merged input over duplicated keys."""


def test_a_member_not_declaring_the_discriminator_is_refused() -> None:
    """A member with no `kind` field is not self-describing to a client."""

    class TaglessModel(BaseModel):
        """A model with no discriminator field."""

        scale: list[float]
        model_config = ConfigDict(extra="forbid")

    @union_member("TaglessInput", key="SCALE")
    @kante.pydantic_input(TaglessModel)
    class TaglessInput:
        """A member with no discriminator."""

        scale: list[float] = strawberry.field(description="The factors")

    with pytest.raises(TypeError, match="does not declare the discriminator"):

        @merged_input(members=[TaglessInput], noun="thing", name="TaglessInput")
        class _Merged:
            """A merged input over a tagless member."""


def test_a_drifted_spec_alias_is_refused() -> None:
    """The one registry a type checker needs written out is the one that can drift."""
    from typing import Annotated

    from pydantic import Field

    spec = Annotated[ScaleThingModel | FieldThingModel, Field(discriminator="kind")]

    with pytest.raises(TypeError, match="has drifted"):

        @merged_input(
            members=[ScaleThingInput, FieldThingInput, NothingThingInput],
            noun="thing",
            spec=spec,
            name="ThingInput",
        )
        class _Merged:
            """A merged input whose spec is missing a member."""


def test_a_matching_spec_alias_is_accepted() -> None:
    """A spec that holds exactly the members passes."""
    from typing import Annotated

    from pydantic import Field

    spec = Annotated[
        ScaleThingModel | FieldThingModel | NothingThingModel,
        Field(discriminator="kind"),
    ]

    @merged_input(
        members=[ScaleThingInput, FieldThingInput, NothingThingInput],
        noun="thing",
        spec=spec,
        name="ThingInput",
    )
    class Merged:
        """A merged input whose spec agrees."""

    assert union_member_types(Merged) == [ScaleThingInput, FieldThingInput, NothingThingInput]


def test_union_member_needs_a_strawberry_type() -> None:
    """Applied below the strawberry decorator, there is no definition to annotate."""
    with pytest.raises(TypeError, match="must be applied above"):

        @union_member("Nope", key="X")
        class Plain:
            """Not a strawberry type."""


def test_a_member_without_a_pydantic_model_is_refused() -> None:
    """The strictness lives in the model, so a member without one has none."""

    @union_member("NoModelInput", key="X")
    @strawberry.input
    class NoModelInput:
        """A plain strawberry input."""

        kind: ThingKind = strawberry.field(description="Which member this is")

    with pytest.raises(TypeError, match="has no pydantic model"):

        @merged_input(members=[NoModelInput], noun="thing", name="NoModelInput")
        class _Merged:
            """A merged input over a modelless member."""


def test_an_empty_union_is_refused() -> None:
    """A union of nothing has no wire shape to derive."""
    with pytest.raises(TypeError, match="at least one member"):
        merged_input(members=[], noun="thing")


def test_a_member_merged_into_a_union_it_never_claimed_is_refused() -> None:
    """The directive names the union, so merging elsewhere would mislead codegen."""
    with pytest.raises(TypeError, match="is a member of 'ThingInput', not of 'Elsewhere'"):

        @merged_input(members=[ScaleThingInput], noun="thing", name="Elsewhere")
        class _Merged:
            """A merged input claiming a member that is not its own."""


# --------------------------------------------------------------------------
# a member of several unions -- what `repeatable` is for
# --------------------------------------------------------------------------


@union_member("AlphaInput", "BetaInput", key="SCALE")
@kante.pydantic_input(ScaleThingModel, description="A member of two unions")
class SharedInput:
    """A member both unions read."""

    kind: ThingKind
    scale: list[float]


@merged_input(members=[SharedInput], noun="alpha")
class AlphaInput:
    """The first union that reads the shared member."""


@merged_input(members=[SharedInput], noun="beta")
class BetaInput:
    """The second union that reads the shared member."""


def test_a_member_can_belong_to_several_unions() -> None:
    """`@unionElementOf` is repeatable, so one member input serves both unions."""

    @strawberry.type
    class BothQuery:
        """A query touching both merged types."""

        @strawberry.field
        def both(self, alpha: AlphaInput, beta: BetaInput) -> str:
            """Keep both merged types reachable from the schema."""
            return "ok"

    sdl = str(
        strawberry.Schema(
            query=BothQuery,
            types=union_member_types(AlphaInput),
            schema_directives=[unionElementOf],
        )
    )

    assert 'union: "AlphaInput", discriminator: "kind", key: "SCALE"' in sdl
    assert 'union: "BetaInput", discriminator: "kind", key: "SCALE"' in sdl
    assert union_member_types(AlphaInput) == [SharedInput]
    assert union_member_types(BetaInput) == [SharedInput]
    # Both merged types carry the member's field, each having derived it independently.
    assert "input AlphaInput" in sdl
    assert "input BetaInput" in sdl


# --------------------------------------------------------------------------
# prose errors
# --------------------------------------------------------------------------


def test_prose_errors_replaces_the_pydantic_report() -> None:
    """A validator's own sentence is the sentence the client reads."""
    from pydantic import field_validator

    class CheckedModel(BaseModel):
        """A model with a validator that writes a full sentence."""

        scale: list[float]

        @field_validator("scale")
        @classmethod
        def _no_zero(cls, scale: list[float]) -> list[float]:
            if 0.0 in scale:
                raise ValueError("A scale factor of zero collapses the axis.")
            return scale

    @kante.prose_errors
    @kante.pydantic_input(CheckedModel)
    class CheckedInput:
        """An input whose model carries a validator."""

        scale: list[float] = strawberry.field(description="The factors")

    with pytest.raises(ValueError) as err:
        CheckedInput(scale=[0.0]).to_pydantic()

    assert str(err.value) == "A scale factor of zero collapses the axis."


def test_camel_field_spells_a_field_as_the_sdl_does() -> None:
    """Messages name fields the way the client wrote them."""
    assert kante.camel_field("input_axes") == "inputAxes"
    assert kante.camel_field("scale") == "scale"
