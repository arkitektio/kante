"""Tests for organization scoping."""

import warnings
from typing import Any

import pytest

from kante.scoping import (
    OrganizationScoper,
    UnscopedModelError,
    for_org,
    get_for_org,
    organization_path,
)
from kante.testing import build_http_context
from test_app import models


class _FakeInfo:
    """The slice of ``Info`` that scoping actually reads."""

    def __init__(self, context: Any, selected_fields: Any = ()) -> None:
        self.context = context
        self.selected_fields = list(selected_fields)
        self.variable_values: Any = {}
        self.field_nodes: Any = []


def _info_for(org: Any, selected_fields: Any = ()) -> Any:
    return _FakeInfo(build_http_context(organization=org), selected_fields)


def test_direct_organization_path() -> None:
    """A model owning `organization` scopes on it directly."""
    assert organization_path(models.ScopedThing) == "organization"


def test_path_walks_required_foreign_keys() -> None:
    """A model reaches its organization through a required FK."""
    assert organization_path(models.NestedThing) == "thing__organization"


def test_nullable_path_is_refused() -> None:
    """A nullable FK is never followed: it would hide rows, not scope them."""
    assert organization_path(models.NullableThing) is None


def test_model_without_organization_has_no_path() -> None:
    """A model with no route to an organization yields no path."""
    assert organization_path(models.OrphanThing) is None


def test_depth_limit_is_honoured() -> None:
    """A path deeper than the limit is reported as absent, never guessed."""
    assert organization_path(models.NestedThing, 0) is None


@pytest.mark.django_db
def test_for_org_filters_to_the_request_organization() -> None:
    """Rows of another organization are invisible."""
    mine = models.Organization.objects.create(slug="mine")
    theirs = models.Organization.objects.create(slug="theirs")
    models.ScopedThing.objects.create(name="mine", organization=mine)
    models.ScopedThing.objects.create(name="theirs", organization=theirs)

    visible = for_org(models.ScopedThing, _info_for(mine))

    assert [t.name for t in visible] == ["mine"]


@pytest.mark.django_db
def test_for_org_traverses_a_nested_path() -> None:
    """Scoping follows the FK chain to the organization."""
    mine = models.Organization.objects.create(slug="mine")
    theirs = models.Organization.objects.create(slug="theirs")
    my_thing = models.ScopedThing.objects.create(name="a", organization=mine)
    their_thing = models.ScopedThing.objects.create(name="b", organization=theirs)
    models.NestedThing.objects.create(name="mine", thing=my_thing)
    models.NestedThing.objects.create(name="theirs", thing=their_thing)

    visible = for_org(models.NestedThing, _info_for(mine))

    assert [t.name for t in visible] == ["mine"]


@pytest.mark.django_db
def test_get_for_org_refuses_another_organizations_row() -> None:
    """Fetching by id cannot cross a tenant boundary."""
    mine = models.Organization.objects.create(slug="mine")
    theirs = models.Organization.objects.create(slug="theirs")
    other_row = models.ScopedThing.objects.create(name="theirs", organization=theirs)

    with pytest.raises(models.ScopedThing.DoesNotExist):
        get_for_org(models.ScopedThing, _info_for(mine), id=other_row.id)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_aget_for_org_refuses_another_organizations_row() -> None:
    """The async fetch enforces the same boundary."""
    mine = await models.Organization.objects.acreate(slug="mine")
    theirs = await models.Organization.objects.acreate(slug="theirs")
    other_row = await models.ScopedThing.objects.acreate(
        name="theirs", organization=theirs
    )

    scoper = OrganizationScoper()
    with pytest.raises(models.ScopedThing.DoesNotExist):
        await scoper.aget_for_org(
            models.ScopedThing, _info_for(mine), id=other_row.id
        )


@pytest.mark.django_db
def test_unscoped_model_raises_rather_than_leaking() -> None:
    """An un-scopeable model fails loudly instead of serving every tenant."""
    org = models.Organization.objects.create(slug="mine")

    with pytest.raises(UnscopedModelError):
        for_org(models.OrphanThing, _info_for(org))


@pytest.mark.django_db
def test_unscoped_model_can_be_declared() -> None:
    """The escape hatch is explicit and per-scoper."""
    org = models.Organization.objects.create(slug="mine")
    models.OrphanThing.objects.create(name="global")
    scoper = OrganizationScoper(unscoped_models={"OrphanThing"})

    assert [t.name for t in scoper.for_org(models.OrphanThing, _info_for(org))] == [
        "global"
    ]


@pytest.mark.django_db
def test_prescope_limits_a_queryset() -> None:
    """The list-field half of scoping filters an existing queryset."""
    mine = models.Organization.objects.create(slug="mine")
    theirs = models.Organization.objects.create(slug="theirs")
    models.ScopedThing.objects.create(name="mine", organization=mine)
    models.ScopedThing.objects.create(name="theirs", organization=theirs)

    scoper = OrganizationScoper()
    scoped = scoper.prescope(_info_for(mine), models.ScopedThing.objects.all())

    assert [t.name for t in scoped] == ["mine"]


class _Arg:
    """A GraphQL argument AST node, cut down to what the scan reads."""

    def __init__(self, name: str, fields: Any = ()) -> None:
        self.name = type("N", (), {"value": name})()
        self.value = type("V", (), {"fields": list(fields), "kind": "object_value"})()


def _object_field(name: str, kind: str = "enum_value") -> Any:
    return type(
        "F",
        (),
        {
            "name": type("N", (), {"value": name})(),
            "value": type("V", (), {"kind": kind})(),
        },
    )()


def _node(*arguments: Any) -> Any:
    return type("Node", (), {"arguments": list(arguments)})()


@pytest.mark.django_db
def test_prescope_refuses_a_scope_passed_as_a_variable() -> None:
    """A scope passed as a variable has always been refused; it still is."""
    org = models.Organization.objects.create(slug="mine")
    info = _info_for(org)
    info.variable_values = {"filters": {"scope": "ALL"}}

    with pytest.raises(NotImplementedError):
        OrganizationScoper().prescope(info, models.ScopedThing.objects.all())


@pytest.mark.django_db
def test_prescope_tolerates_a_null_filters_variable() -> None:
    """`filters: null` used to raise AttributeError inside the scope check."""
    org = models.Organization.objects.create(slug="mine")
    models.ScopedThing.objects.create(name="mine", organization=org)
    info = _info_for(org)
    info.variable_values = {"filters": None}

    scoped = OrganizationScoper().prescope(info, models.ScopedThing.objects.all())

    assert [t.name for t in scoped] == ["mine"]


@pytest.mark.django_db
def test_prescope_warns_about_an_inline_scope_but_still_scopes() -> None:
    """An inline scope was silently ignored, not leaked -- so it stays ignored.

    `variable_values` never contained an inline argument, so the old check fell
    through to the scoping branch and returned org-filtered rows. Raising here
    would break a query that works today, so kante warns and keeps scoping.
    """
    mine = models.Organization.objects.create(slug="mine")
    theirs = models.Organization.objects.create(slug="theirs")
    models.ScopedThing.objects.create(name="mine", organization=mine)
    models.ScopedThing.objects.create(name="theirs", organization=theirs)

    info = _info_for(mine)
    info.field_nodes = [_node(_Arg("filters", [_object_field("scope")]))]

    with pytest.warns(DeprecationWarning, match="scope"):
        scoped = OrganizationScoper().prescope(info, models.ScopedThing.objects.all())

    assert [t.name for t in scoped] == ["mine"]


@pytest.mark.django_db
def test_prescope_does_not_warn_without_a_scope() -> None:
    """The ordinary path stays quiet and does not walk the selection set."""
    org = models.Organization.objects.create(slug="mine")
    info = _info_for(org)
    info.field_nodes = [_node(_Arg("filters", [_object_field("name", "string_value")]))]

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        OrganizationScoper().prescope(info, models.ScopedThing.objects.all())


class _RawInfo:
    """An ``Info`` shaped like strawberry 0.324's: field nodes only on the raw info.

    ``Info.field_nodes`` was removed in 0.324. The shim above still sets it, so every
    inline-scope test kept passing while the real thing silently stopped working --
    the check sat behind a blanket ``except Exception: return False``. This is the
    shape scoping actually meets in production.
    """

    def __init__(self, context: Any, field_nodes: Any) -> None:
        self.context = context
        self.selected_fields: Any = []
        self.variable_values: Any = {}
        self._raw_info = type("Raw", (), {"field_nodes": list(field_nodes)})()


@pytest.mark.django_db
def test_inline_scope_is_read_off_the_raw_graphql_info() -> None:
    """The warning must fire on an Info that only carries nodes on `_raw_info`."""
    mine = models.Organization.objects.create(slug="mine")
    models.ScopedThing.objects.create(name="mine", organization=mine)

    info = _RawInfo(
        build_http_context(organization=mine),
        [_node(_Arg("filters", [_object_field("scope")]))],
    )

    with pytest.warns(DeprecationWarning, match="scope"):
        scoped = OrganizationScoper().prescope(info, models.ScopedThing.objects.all())

    assert [t.name for t in scoped] == ["mine"]


def test_the_graphql_info_still_carries_field_nodes() -> None:
    """Fail loudly if graphql-core drops the attribute scoping actually depends on.

    Asserting on strawberry's `Info` would not do: `_raw_info` stays declared as a
    dataclass field whether or not the object behind it still has `field_nodes`, so
    that check would pass while `_has_inline_scope` silently returned False again --
    the exact failure this pair of tests exists to catch.
    """
    from graphql import GraphQLResolveInfo

    assert "field_nodes" in GraphQLResolveInfo._fields


def _only(name: str) -> Any:
    """A narrowing step that keeps the rows called ``name``."""

    def narrow(queryset: Any, info: Any) -> Any:
        return queryset.filter(name=name)

    return narrow


@pytest.mark.django_db
def test_narrow_applies_after_the_organization_filter() -> None:
    """A scoper's narrowing step sees only the organization's rows, and can only take more away."""
    mine = models.Organization.objects.create(slug="mine")
    theirs = models.Organization.objects.create(slug="theirs")
    models.ScopedThing.objects.create(name="shared", organization=mine)
    models.ScopedThing.objects.create(name="private", organization=mine)
    models.ScopedThing.objects.create(name="shared", organization=theirs)
    scoper = OrganizationScoper(narrow=_only("shared"))
    info = _info_for(mine)

    assert [t.organization.slug for t in scoper.for_org(models.ScopedThing, info)] == ["mine"]
    assert [t.name for t in scoper.prescope(info, models.ScopedThing.objects.all())] == ["shared"]
    assert scoper.get_for_org(models.ScopedThing, info, name="shared").organization == mine
    with pytest.raises(models.ScopedThing.DoesNotExist):
        scoper.get_for_org(models.ScopedThing, info, name="private")


@pytest.mark.django_db
def test_narrow_applies_to_a_declared_unscoped_model() -> None:
    """Rows of no organization are narrowed too: the step decides, not the escape hatch."""
    org = models.Organization.objects.create(slug="mine")
    models.OrphanThing.objects.create(name="global")
    scoper = OrganizationScoper(unscoped_models={"OrphanThing"}, narrow=lambda qs, info: qs.none())

    assert list(scoper.for_org(models.OrphanThing, _info_for(org))) == []


@pytest.mark.django_db
def test_object_scope_setting_narrows_every_scoper(settings: Any) -> None:
    """``KANTE_OBJECT_SCOPE`` narrows the module helpers and any scoper without its own step."""
    org = models.Organization.objects.create(slug="mine")
    models.ScopedThing.objects.create(name="shared", organization=org)
    models.ScopedThing.objects.create(name="private", organization=org)
    settings.KANTE_OBJECT_SCOPE = "tests.test_scoping._keep_shared"

    assert [t.name for t in for_org(models.ScopedThing, _info_for(org))] == ["shared"]
    assert [t.name for t in OrganizationScoper().for_org(models.ScopedThing, _info_for(org))] == ["shared"]
    own = OrganizationScoper(narrow=_only("private"))
    assert [t.name for t in own.for_org(models.ScopedThing, _info_for(org))] == ["private"]


@pytest.mark.django_db
def test_without_a_narrowing_step_nothing_is_narrowed() -> None:
    """Unset, the scoped queryset is exactly the organization filter."""
    org = models.Organization.objects.create(slug="mine")
    queryset = for_org(models.ScopedThing, _info_for(org))

    assert str(queryset.query) == str(models.ScopedThing.objects.filter(organization=org).query)


_keep_shared = _only("shared")
