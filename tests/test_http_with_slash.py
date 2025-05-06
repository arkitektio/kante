""" Test the GraphQL WebSocket client."""

from uuid import uuid4
import pytest
from kante.testing import GraphQLHttpTestClient
from test_project.asgi import application

@pytest.mark.asyncio
async def test_graphql_http_with_slash()-> None:
    """ Test that the GraphQL subscription works with connection parameters."""
    payload = {
        "authToken": "test",
        "clientName": "pytest-client"
    }

    
    
    client = GraphQLHttpTestClient(
        application,
        path="/graphql/"  # Ensure the path is set correctly
        )
    
    test_id = str(uuid4())
    
   
    # Send the mutation via HTTP
    answer = await client.execute(
        query="""
        mutation($id: ID!) {
            send(id: $id)
        }
        """,
        variables={"id": test_id}
    )
    
    # Validate that the broadcast was received correctly
    assert answer["data"]["send"] == test_id

