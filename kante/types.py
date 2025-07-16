from strawberry.types import Info as _Info
from kante.context import Context
from typing import Any, Literal, Protocol


Info = _Info[Context, Any] 



class ChannelsLayer(Protocol):  # pragma: no cover
    """Channels layer spec.

    Based on: https://channels.readthedocs.io/en/stable/channel_layer_spec.html
    """

    # Default channels API

    extensions: list[Literal["groups", "flush"]]

    async def send(self, channel: str, message: dict[str, Any]) -> None: ...

    async def receive(self, channel: str) -> dict[str, Any]: ...

    async def new_channel(self, prefix: str = ...) -> str: ...

    # If groups extension is supported

    group_expiry: int

    async def group_add(self, group: str, channel: str) -> None: ...

    async def group_discard(self, group: str, channel: str) -> None: ...

    async def group_send(self, group: str, message: dict[str, Any]) -> None: ...

    # If flush extension is supported

    async def flush(self) -> None: ...
