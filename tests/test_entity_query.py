"""Test the GraphQL WebSocket client."""

from contextlib import contextmanager
from typing import Iterator
from uuid import uuid4
from unittest.mock import patch
import pytest
from django.db.models import QuerySet
from test_app.models import TestModel
from kante.testing import GraphQLHttpTestClient
from test_project.asgi import application


@pytest.mark.asyncio
async def test_graphql_entitiy_query(db) -> None:
    """Test that the GraphQL subscription works with connection parameters."""

    client = GraphQLHttpTestClient(
        application,
        path="/graphql/",  # Ensure the path is set correctly
    )

    str(uuid4())

    model = await TestModel.objects.acreate(name="Test Entity")
    print(model.pk)

    # Send the mutation via HTTP
    answer = await client.execute(
        query="""
            query Entities($representations: [_Any!]!) {
                entities: _entities(representations: $representations) {
                    ... on TestModel {
                        id
                        name
                    }
                }
            }
            """,
        variables={"representations": [{"__typename": "TestModel", "id": str(model.pk)}]},
    )

    # Validate that the broadcast was received correctly
    if "errors" in answer:
        raise Exception(answer["errors"])

    assert answer["data"]["entities"][0]["id"] == str(model.pk), answer["errors"]


@pytest.mark.asyncio
async def test_entities_query_batches_reference_resolution(db) -> None:
    """Multiple representations must resolve in a single batched DB query."""

    client = GraphQLHttpTestClient(application, path="/graphql/")

    models = [
        await TestModel.objects.acreate(name=f"Entity {i}") for i in range(5)
    ]

    query = """
        query Entities($representations: [_Any!]!) {
            entities: _entities(representations: $representations) {
                ... on TestModel {
                    id
                    name
                }
            }
        }
        """
    representations = [
        {"__typename": "TestModel", "id": str(m.pk)} for m in models
    ]

    # Count the id lookups the reference resolver issues. With batching, all 5
    # representations collapse to one. (Spied on the queryset: the lookup starts
    # from the scoper's queryset, not from the manager.)
    with _count_id_lookups() as lookups:
        answer = await client.execute(
            query=query, variables={"representations": representations}
        )

    if "errors" in answer:
        raise Exception(answer["errors"])

    returned_ids = {e["id"] for e in answer["data"]["entities"]}
    assert returned_ids == {str(m.pk) for m in models}

    assert len(lookups) == 1, (
        f"expected 1 batched lookup for 5 references, got "
        f"{len(lookups)} (N+1 regression)"
    )


@contextmanager
def _count_id_lookups() -> Iterator[list]:
    real_filter = QuerySet.filter
    lookups: list = []

    def spy(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        if "id__in" in kwargs:
            lookups.append(kwargs["id__in"])
        return real_filter(self, *args, **kwargs)

    with patch.object(QuerySet, "filter", spy):
        yield lookups


# --------------------------------------------------------------------------- #
# References are scoped to the request
# --------------------------------------------------------------------------- #

from django.test import override_settings  # noqa: E402

from test_app.models import Organization, OrphanThing, ScopedThing  # noqa: E402

THINGS = """
    query Entities($representations: [_Any!]!) {
        entities: _entities(representations: $representations) {
            ... on ScopedThing { id name }
            ... on OrphanThing { id name }
            ... on TestModel { id name }
        }
    }
    """


# These tests use `transactional_db`: rows written through the async ORM are not
# inside the `db` fixture's transaction, so only a flush takes them away again.


async def _org(name: str) -> Organization:
    """A fresh organization, whatever other tests left behind."""
    return await Organization.objects.acreate(slug=f"{name}-{uuid4().hex}")


async def _entities(typename: str, ids: list, organization: str | None) -> dict:
    headers = {"x-test-organization": organization} if organization else {}
    client = GraphQLHttpTestClient(application, path="/graphql/", headers=headers)
    return await client.execute(
        query=THINGS,
        variables={
            "representations": [{"__typename": typename, "id": str(id)} for id in ids]
        },
    )


@pytest.mark.asyncio
async def test_a_reference_into_another_organization_resolves_to_nothing(transactional_db) -> None:
    """`_entities` takes ids from the caller, so guessing one must not be enough."""
    mine = await _org("mine")
    theirs = await _org("theirs")
    own = await ScopedThing.objects.acreate(name="own", organization=mine)
    foreign = await ScopedThing.objects.acreate(name="foreign", organization=theirs)

    answer = await _entities("ScopedThing", [own.pk, foreign.pk], organization=mine.slug)

    assert "errors" not in answer, answer
    assert answer["data"]["entities"] == [{"id": str(own.pk), "name": "own"}, None]


@pytest.mark.asyncio
async def test_the_other_organization_sees_the_other_half(transactional_db) -> None:
    mine = await _org("mine")
    theirs = await _org("theirs")
    own = await ScopedThing.objects.acreate(name="own", organization=mine)
    foreign = await ScopedThing.objects.acreate(name="foreign", organization=theirs)

    answer = await _entities("ScopedThing", [own.pk, foreign.pk], organization=theirs.slug)

    assert answer["data"]["entities"] == [None, {"id": str(foreign.pk), "name": "foreign"}]


@pytest.mark.asyncio
async def test_a_reference_goes_through_the_types_own_queryset(transactional_db) -> None:
    """What the type hides from its list and detail queries stays hidden here."""
    mine = await _org("mine")
    shown = await ScopedThing.objects.acreate(name="shown", organization=mine)
    hidden = await ScopedThing.objects.acreate(name="hidden", organization=mine)

    answer = await _entities("ScopedThing", [shown.pk, hidden.pk], organization=mine.slug)

    assert answer["data"]["entities"] == [{"id": str(shown.pk), "name": "shown"}, None]


@pytest.mark.asyncio
async def test_a_scoped_reference_without_an_organization_fails(transactional_db) -> None:
    mine = await _org("mine")
    thing = await ScopedThing.objects.acreate(name="own", organization=mine)

    answer = await _entities("ScopedThing", [thing.pk], organization=None)

    assert answer["data"] is None or answer["data"]["entities"] == [None]
    assert "Organization is not set" in str(answer["errors"])


@pytest.mark.asyncio
async def test_a_model_with_no_tenancy_story_is_refused_not_served(transactional_db) -> None:
    orphan = await OrphanThing.objects.acreate(name="orphan")

    answer = await _entities("OrphanThing", [orphan.pk], organization=None)

    assert "OrphanThing has no path to 'organization'" in str(answer["errors"])
    assert not (answer["data"] or {}).get("entities") or answer["data"]["entities"] == [None]


@pytest.mark.asyncio
async def test_without_the_setting_kantes_own_scoper_answers(transactional_db) -> None:
    """Which has no exceptions, so the test project's unscoped model is refused too."""
    model = await TestModel.objects.acreate(name="Test Entity")

    with override_settings(KANTE_REFERENCE_QUERYSET=None):
        answer = await _entities("TestModel", [model.pk], organization=None)

    assert "TestModel has no path to 'organization'" in str(answer["errors"])


@pytest.mark.asyncio
async def test_scoped_references_are_still_one_query(transactional_db) -> None:
    mine = await _org("mine")
    things = [
        await ScopedThing.objects.acreate(name=f"thing {i}", organization=mine)
        for i in range(5)
    ]

    with _count_id_lookups() as lookups:
        answer = await _entities("ScopedThing", [t.pk for t in things], organization=mine.slug)

    assert [e["name"] for e in answer["data"]["entities"]] == [t.name for t in things]
    assert len(lookups) == 1, f"expected one batched lookup, got {len(lookups)}"
