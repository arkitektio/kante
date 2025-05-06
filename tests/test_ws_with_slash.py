""" Test the GraphQL WebSocket client."""

import pytest
from kante.testing.ws import GraphQLWebSocketTestClient
from test_project.asgi import application

@pytest.mark.asyncio
async def test_graphql_subscription_with_connection_params()-> None:
    """ Test that the GraphQL subscription works with connection parameters."""
    payload = {
        "authToken": "test",
        "clientName": "pytest-client"
    }

    
    
    client = GraphQLWebSocketTestClient(
        application,
        connection_params=payload,
        path="/graphql/"  # Ensure the path is set correctly
        )
    
   
    async with client:

        async for msg in client.subscribe("subscription { time }"):
            assert "data" in msg["payload"]
            assert "time" in msg["payload"]["data"]
            payload = msg["payload"]["data"]["time"]
            assert payload == {"authToken": "test", "clientName": "pytest-client"}
            break  # Stop after first message

