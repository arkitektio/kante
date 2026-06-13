""" Test that a WebSocket subscription receives a broadcast from an HTTP mutation."""

import datetime
import pytest
import asyncio
import msgpack
from uuid import UUID, uuid4
from pydantic import BaseModel
from channels.layers import get_channel_layer

from test_project.asgi import application
from kante.channel import build_channel
from kante.testing import GraphQLHttpTestClient, GraphQLWebSocketTestClient


class RichChannelModel(BaseModel):
    """A channel model with non-primitive fields (UUID/datetime/Decimal)."""

    id: UUID
    created: datetime.datetime
    name: str


@pytest.mark.asyncio
async def test_broadcast_payload_is_serializer_safe() -> None:
    """Broadcast payloads must survive the channel layer's msgpack serializer.

    The default channels-redis serializer is msgpack, which cannot pack native
    UUID/datetime objects. The in-memory test layer does not serialize, so this
    asserts msgpack-safety directly to catch a regression the test layer hides.
    """
    channel = build_channel(RichChannelModel, "rich_test_channel")
    layer = get_channel_layer()

    listener = await layer.new_channel()
    await layer.group_add("default", listener)

    message = RichChannelModel(
        id=uuid4(), created=datetime.datetime.now(), name="payload"
    )
    await channel.abroadcast(message)

    received = await asyncio.wait_for(layer.receive(listener), timeout=2)

    # Exactly what channels-redis would do before pushing to Redis; must not raise.
    msgpack.packb(received["message"], use_bin_type=True)

    # ...and the rich model round-trips back from the JSON-safe primitives.
    assert RichChannelModel.model_validate(received["message"]) == message


@pytest.mark.asyncio
async def test_abroadcast_fans_out_to_all_groups() -> None:
    """Every requested group must receive the broadcast exactly once."""
    channel = build_channel(RichChannelModel, "fanout_test_channel")
    layer = get_channel_layer()

    groups = ["g1", "g2", "g3"]
    listeners = {}
    for group in groups:
        name = await layer.new_channel()
        await layer.group_add(group, name)
        listeners[group] = name

    message = RichChannelModel(
        id=uuid4(), created=datetime.datetime.now(), name="fanout"
    )
    await channel.abroadcast(message, groups=groups)

    for group, name in listeners.items():
        received = await asyncio.wait_for(layer.receive(name), timeout=2)
        assert RichChannelModel.model_validate(received["message"]) == message, group


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
