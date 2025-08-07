import asyncio
from typing import AsyncGenerator
from kante.context import WsContext
from kante.types import Info
import strawberry
from strawberry import ID, scalars
from typing import cast
from kante.channel import build_channel
from pydantic import BaseModel
import kante
from test_app import models


class StrChannelModel(BaseModel):
    id: str
    name: str


@kante.pydantic_type(StrChannelModel)
class StrChannel:
    id: str
    name: str


@kante.django_type(models.TestModel, federated=True)
class TestModel:
    """A simple test model for demonstration purposes."""

    id: ID
    name: str


str_channel = build_channel(StrChannelModel, "test_channel")


@kante.type
class Me:
    id: str


@kante.type
class Query:
    @strawberry.field
    def me(self, info: Info, id: ID) -> Me:
        return Me(id=id)


@kante.type
class Mutation:
    @kante.field
    def me(self, info: Info, id: ID) -> Me:
        return Me(id=id)

    @kante.django_field
    def send(self, info: Info, id: ID) -> str:
        str_channel.broadcast(StrChannelModel(id=str(id), name="test"))
        return str(id)

    @kante.django_field
    def test_model(self, info: Info, id: ID) -> TestModel:
        return models.TestModel.objects.get(pk=id)


@strawberry.type
class Subscription:
    @kante.subscription
    async def time(self, info: Info) -> AsyncGenerator[scalars.JSON, None]:
        for i in range(2):
            assert isinstance(info.context, WsContext)
            yield info.context.connection_params
            await asyncio.sleep(1)

    @kante.subscription
    async def listen_str_channel(self, info: Info) -> AsyncGenerator[StrChannel, None]:
        """Listen to the str_channel and yield messages."""
        assert isinstance(info.context, WsContext)
        async for i in str_channel.listen(info.context):
            yield cast(StrChannel, i)


schema = kante.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)
