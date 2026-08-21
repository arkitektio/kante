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
from kante.types import Info, require_ws
import strawberry
from strawberry import ID, scalars
from typing import cast
from kante.channel import build_channel
import kante
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
ROOM = "str_channel_room"


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
        
        str_channel.broadcast(StrChannelModel(id=str(id), name="test"), groups=[ROOM])
        return str(id)
    
    
    
@strawberry.type
class Subscription:
    
    
    @strawberry.subscription
    async def time(self, info: Info) -> AsyncGenerator[scalars.JSON, None]:
        context = require_ws(info)
        for i in range(2):
            yield context.connection_params
            await asyncio.sleep(1)
            
            
    @strawberry.subscription
    async def listen_str_channel(self, info: Info) -> AsyncGenerator[StrChannel, None]:
        """ Listen to the str_channel and yield messages."""
        async for i in str_channel.listen(info, [ROOM]):
            yield cast(StrChannel, i)

schema = kante.Schema(
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
    schema=schema,
    django_asgi_app=django_asgi_app,
    schema_path="schema",  # optional: serves the SDL as text/plain at /schema
)
```

## What kante actually adds

Most of what `kante` exports is a plain alias of a strawberry symbol. The parts
that do something are:

| Symbol | What it does |
| --- | --- |
| `kante.Schema` | federation schema with `DjangoOptimizerExtension` installed by default |
| `kante.django_type` | Django type + federation `@key(fields: "id")` + a batching `resolve_reference` |
| `kante.context` | the request seam: user, client, organization, membership, provenance |
| `kante.channel` | typed pub/sub over the channels layer |
| `kante.scoping` | organization (tenant) scoping for querysets |
| `kante.errors` | GraphQL errors carrying a machine-readable `code`, and pydantic failures as prose |
| `kante.unions` | discriminated input unions: one merged wire type, derived from its members |
| `kante.router` | ASGI wiring for HTTP + websocket GraphQL |
| `kante.testing` | ASGI test clients and request-context factories |

> **Prefer `strawberry.type` over `kante.type`.** The plain re-exports
> (`type`, `input`, `interface`, `field`, `mutation`, `scalar`, ...) are
> module-level aliases of overloaded decorators, and mypy does not carry an
> overload set across an alias -- `@kante.type` makes mypy resolve the class to
> `builtins.type`, so every constructor keyword is reported as unexpected. They
> remain for backwards compatibility. `django_type` and `django_interface` are
> real functions and are unaffected.

## Tenant scoping

Every read must be limited to the organization the request authenticated for.
Single-object access goes through `kante.scoping`:

```python
from kante.scoping import for_org, get_for_org, aget_for_org

# instead of models.File.objects.get(id=id)
file = get_for_org(models.File, info, id=id)
```

The path from a model to its organization is discovered by walking *non-nullable*
foreign keys (a nullable path would hide rows rather than scope them). A model
with no such path raises `UnscopedModelError` instead of quietly returning
everything; declare the deliberate exceptions on your own scoper:

```python
from kante.scoping import OrganizationScoper

scoper = OrganizationScoper(unscoped_models={"SystemSetting"}, max_path_depth=5)
```

List fields are scoped on the queryset instead:

```python
@kante.django_type(models.File)
class File:
    id: strawberry.ID

    @classmethod
    def get_queryset(cls, queryset, info):
        return scoper.prescope(info, queryset)
```

## Subscriptions

Relay the **id** of what changed and let the subscriber re-fetch it scoped -- that
way the room name is not the only thing standing between two tenants:

```python
from kante.channel import CRUDSignal, build_channel
from kante.scoping import aget_for_org

file_channel = build_channel(CRUDSignal, "files")

# signals.py -- broadcast after the transaction commits
@receiver(post_save, sender=models.File)
def on_file_saved(sender, instance, created, **kwargs):
    file_channel.broadcast_on_commit(
        CRUDSignal(create=instance.id) if created else CRUDSignal(update=instance.id),
        groups=[file_channel.org_group(instance.organization)],
    )

# subscriptions.py -- same helper builds the same room name
async def files(self, info: Info) -> AsyncGenerator[FileEvent, None]:
    room = file_channel.org_group(info.context.request.organization)
    async for message in file_channel.listen(info, [room]):
        if message.create:
            yield FileEvent(create=await aget_for_org(models.File, info, id=message.create))
```

`listen()` takes `info` directly and narrows to the websocket context itself, so
no `assert isinstance(info.context, WsContext)` is needed. Use
`kante.require_ws(info)` when you need the context for something else.

**Always pass `groups`.** Omitting it falls back to a single process-wide
`"default"` room shared by every channel in the deployment; that fallback now
warns and will be removed in kante 3. A channel that genuinely wants an implicit
room should declare its own: `build_channel(Model, "name", default_groups=[...])`.

## Errors

```python
from kante.errors import NotFound, PermissionDenied

raise NotFound("No dataset with that id")
# {"errors": [{"message": "No dataset with that id",
#              "extensions": {"code": "NOT_FOUND"}}]}
```

Nothing is masked -- the message is the message you wrote. The addition is a code
the client can branch on, so a deliberate error is distinguishable from an
internal one.

## Discriminated input unions

GraphQL has no input unions, so a union arriving through an argument is wired as
one *merged* input: a discriminator plus every member's fields, all optional.
Write the members; the merged type is derived from them.

```python
from kante.unions import merged_input, union_member, union_member_types, unionElementOf

class ScaleTransformModel(BaseModel):
    kind: Literal["SCALE"] = "SCALE"
    scale: list[float] = Field(description="The per-axis factors")
    model_config = ConfigDict(extra="forbid")   # required: this is the strictness

@union_member("TransformInput", key="SCALE")
@kante.pydantic_input(ScaleTransformModel, description="The fields a SCALE member reads")
class ScaleTransformInput:
    kind: TransformKind
    scale: list[float]

@merged_input(members=[ScaleTransformInput, FieldTransformInput], noun="transformation")
class TransformInput:
    """One authored edge, discriminated by `kind`."""

schema = kante.Schema(
    query=Query,
    types=union_member_types(TransformInput),   # nothing references these; omit them and
    schema_directives=[unionElementOf],         # they vanish from the SDL silently
)
```

The merged type carries every member's fields, optional, typed as the member
types them, and described as `"(SCALE, BY_DIMENSION) ..."` -- the prefix computed
from the members that read the field, so it cannot go stale. Its generated
`to_pydantic()` returns the member model the discriminator selects, and a field
that contradicts the kind is an error naming both rather than a silent drop:

```
A SCALE transformation does not read `field`: it reads `scale`.
Drop it, or pick the kind that reads it.
```

Each member is published in the SDL under `@unionElementOf`, which is how a
generated client rebuilds the tagged union -- turms emits
`Annotated[A | B, Field(discriminator="kind")]` from it. That only works on an
SDL-sourced schema: an introspected one carries no directive applications, and
codegen degrades to a plain input with no warning.

> **Descriptions live on the pydantic model.** Strawberry's pydantic integration
> takes a field's description from `Field(description=...)` and ignores any
> `strawberry.field(description=...)` in the member's class body -- silently.

## Testing

```python
from kante.testing import build_http_context

@pytest.fixture
def authenticated_context(db) -> HttpContext:
    user = User.objects.create(sub="1", username="tester")
    org = Organization.objects.create(slug="test_org")
    return build_http_context(user=user, organization=org, token="test")
```

Principals left unset raise on access, exactly as an unauthenticated request
does. For subscriptions there is `build_ws_context(consumer, ...)`.

## Building on kante

Kante is the bottom layer: it must not import anything above it. Auth and audit
live in `authentikate` and `koherent`, which build on it.
