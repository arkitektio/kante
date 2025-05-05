# Kante

Kante is a simple lightweight strawberry utily library, that
merges the efforts aims to provide common utilities for
strawberry and strawberry-django projects.


## Installation

```bash
pip install kante
```

## Usage


Here is a simple example of how to use kante with strawberry and strawberry-django.
It can be used with any ASGI application, but this example uses Django.

```python "schema.py"
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
```

To wrap the schema with the ASGI application, you can use the `router` function from `kante.router`.

```python "asgi.py"
import os
from django.core.asgi import get_asgi_application
from kante.router import router

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test_project.settings")
# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()


from .schema import schema  # noqa



application = router(
    django_asgi_app,
    schema=schema,
)
```

## Usage

Kante is aimed to be a simple utility library for strawberry and strawberry-django, to build upon
to see some extensions look at "authentikate" and "koherent" which are built on top of kante.



