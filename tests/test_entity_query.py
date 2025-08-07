"""Test the GraphQL WebSocket client."""

from uuid import uuid4
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
