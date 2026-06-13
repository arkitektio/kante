"""Test the GraphQL WebSocket client."""

from uuid import uuid4
from unittest.mock import patch
import pytest
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

    # Spy on the manager's filter() to count how many lookups the reference
    # resolver issues. With batching, all 5 representations collapse to one.
    real_filter = TestModel.objects.filter
    with patch.object(
        TestModel.objects, "filter", wraps=real_filter
    ) as filter_spy:
        answer = await client.execute(
            query=query, variables={"representations": representations}
        )

    if "errors" in answer:
        raise Exception(answer["errors"])

    returned_ids = {e["id"] for e in answer["data"]["entities"]}
    assert returned_ids == {str(m.pk) for m in models}

    assert filter_spy.call_count == 1, (
        f"expected 1 batched filter() for 5 references, got "
        f"{filter_spy.call_count} (N+1 regression)"
    )
