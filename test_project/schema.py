import asyncio
from typing import AsyncGenerator
from kante.types import Info, require_ws
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


str_channel = build_channel(StrChannelModel, "test_channel", default_groups=["default"])


@strawberry.type
class Me:
    id: str


@strawberry.type
class Query:
    @strawberry.field
    def me(self, info: Info, id: ID) -> Me:
        return Me(id=id)


@strawberry.type
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
        # strawberry-django resolves the Django instance through the GraphQL type.
        return cast(TestModel, models.TestModel.objects.get(pk=id))


@strawberry.type
class Subscription:
    @kante.subscription
    async def time(self, info: Info) -> AsyncGenerator[scalars.JSON, None]:
        context = require_ws(info)
        for i in range(2):
            yield cast(scalars.JSON, context.connection_params)
            await asyncio.sleep(1)

    @kante.subscription
    async def listen_str_channel(self, info: Info) -> AsyncGenerator[StrChannel, None]:
        """Listen to the str_channel and yield messages."""
        # `listen` takes `info` directly and narrows to the websocket context
        # itself -- no `assert isinstance(...)` (which `python -O` strips).
        async for i in str_channel.listen(info):
            yield cast(StrChannel, i)


schema = kante.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)
