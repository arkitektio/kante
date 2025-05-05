""" Test that a WebSocket subscription receives a broadcast from an HTTP mutation."""

import pytest
import asyncio
from uuid import uuid4

from test_project.asgi import application
from kante.testing import GraphQLHttpTestClient, GraphQLWebSocketTestClient


@pytest.mark.asyncio
async def test_str_channel_subscription_receives_broadcast_from_http_mutation() -> None:
    """ Test that a WebSocket subscription receives a broadcast from an HTTP mutation."""
    # Initialize both clients
    http_client = GraphQLHttpTestClient(application=application)
    ws_client = GraphQLWebSocketTestClient(application=application)

    # Connect the WebSocket client
    await ws_client.connect()

    # Prepare a unique ID
    test_id = str(uuid4())

    # Set up the subscription to listen for messages
    subscription = ws_client.subscribe(
        query="""
        subscription {
            listenStrChannel {
                id
                name
            }
        }
        """,
        max_messages=1
    )

    # Start listening in the background
    result = {}

    async def listen() -> None:
        """ Listen for messages from the subscription."""
        async for msg in subscription:
            result.update(msg["payload"]["data"]["listenStrChannel"])
            break

    listener_task = asyncio.create_task(listen())

    # Send the mutation via HTTP
    await http_client.execute(
        query="""
        mutation($id: ID!) {
            send(id: $id)
        }
        """,
        variables={"id": test_id}
    )

    # Wait for the subscription to receive the broadcast
    await listener_task
    await ws_client.disconnect()

    # Validate that the broadcast was received correctly
    assert result["id"] == test_id
    assert result["name"] == "test"
