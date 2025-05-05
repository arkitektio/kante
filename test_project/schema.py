import asyncio
from typing import AsyncGenerator
from kante.context import WsContext
from kante.types import Info
import strawberry
from strawberry import ID, scalars
from typing import cast
from kante.channel import build_channel
from pydantic import BaseModel
from strawberry.experimental import pydantic
import strawberry_django

class StrChannelModel(BaseModel):
    id: str
    name: str


@pydantic.type(StrChannelModel)
class StrChannel:
    id: str
    name: str


str_channel = build_channel(StrChannelModel, "test_channel")


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
    
    
    @strawberry.field
    def me(self, info: Info, id: ID) -> Me:
        return Me(id=id)
    
    
    @strawberry_django.field
    def send(self, info: Info, id: ID) -> str:
        
        str_channel.broadcast(StrChannelModel(id=str(id), name="test"))
        return str(id)
    
    
    
@strawberry.type
class Subscription:
    
    
    @strawberry.subscription
    async def time(self, info: Info) -> AsyncGenerator[scalars.JSON, None]:
        for i in range(2):
            assert isinstance(info.context, WsContext)
            yield info.context.connection_params
            await asyncio.sleep(1)
            
            
    @strawberry.subscription
    async def listen_str_channel(self, info: Info) -> AsyncGenerator[StrChannel, None]:
        """ Listen to the str_channel and yield messages."""
        assert isinstance(info.context, WsContext)
        async for i in str_channel.listen(info.context):
            yield cast(StrChannel, i)

            
            


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)
