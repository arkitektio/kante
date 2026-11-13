"""A request takes no channel on the layer: only a socket receives on it."""

from uuid import uuid4

import pytest
from channels.layers import InMemoryChannelLayer, get_channel_layer

from kante.consumers import KanteHTTPConsumer
from kante.consumers.http import NO_CHANNEL_LAYER
from kante.testing import GraphQLHttpTestClient
from test_project.asgi import application


def test_the_alias_of_a_request_names_no_layer() -> None:
    assert KanteHTTPConsumer.channel_layer_alias == NO_CHANNEL_LAYER
    assert get_channel_layer(NO_CHANNEL_LAYER) is None
    assert get_channel_layer() is not None, "the project still has its layer, for sockets and broadcasts"


@pytest.mark.asyncio
async def test_a_request_never_receives_on_the_layer_and_still_broadcasts(monkeypatch: pytest.MonkeyPatch) -> None:
    channels: list[str] = []
    received: list[str] = []
    sent: list[str] = []
    new_channel, receive, group_send = InMemoryChannelLayer.new_channel, InMemoryChannelLayer.receive, InMemoryChannelLayer.group_send

    async def counted_new_channel(self: InMemoryChannelLayer, prefix: str = "specific.") -> str:
        channel = await new_channel(self, prefix)
        channels.append(channel)
        return channel

    async def counted_receive(self: InMemoryChannelLayer, channel: str) -> dict:
        received.append(channel)
        return await receive(self, channel)

    async def counted_group_send(self: InMemoryChannelLayer, group: str, message: dict) -> None:
        sent.append(group)
        await group_send(self, group, message)

    monkeypatch.setattr(InMemoryChannelLayer, "new_channel", counted_new_channel)
    monkeypatch.setattr(InMemoryChannelLayer, "receive", counted_receive)
    monkeypatch.setattr(InMemoryChannelLayer, "group_send", counted_group_send)

    test_id = str(uuid4())
    answer = await GraphQLHttpTestClient(application).execute(
        query="mutation($id: ID!) { send(id: $id) }",
        variables={"id": test_id},
    )

    assert answer["data"]["send"] == test_id
    assert channels == [] and received == [], "the request took its turn at the layer's inbox"
    assert sent, "what the mutation broadcasts still goes out"
