"""Typed aliases and structural types shared across kante."""

from strawberry.types import Info as _Info
from kante.context import Context, HttpContext, WsContext
from typing import Any, Literal, Protocol, TypeGuard


Info = _Info[Context, Any]
"""``Info`` with kante's context attached.

This is the annotation resolvers should use. Note that ``Info.context`` is the
``HttpContext | WsContext`` union -- narrow it with :func:`require_ws` (or
:func:`is_ws`) before touching websocket-only attributes.
"""

WsInfo = _Info[WsContext, Any]
"""``Info`` for a resolver that only ever runs over a websocket.

Subscriptions can annotate with this instead of :data:`Info` to get
``info.context.consumer`` and ``info.context.connection_params`` without a cast.
"""

HttpInfo = _Info[HttpContext, Any]
""" ``Info`` for a resolver that only ever runs over HTTP. """


def is_ws(info: Info) -> TypeGuard[WsInfo]:
    """Narrow an ``Info`` to a websocket ``Info``.

    Useful in a branch where an HTTP request is a legitimate case::

        if is_ws(info):
            reveal_type(info.context.consumer)  # WsContext
    """
    return isinstance(info.context, WsContext)


def require_ws(info: Info) -> WsContext:
    """Return the request's :class:`~kante.context.WsContext`, or raise.

    Subscriptions receive an ``Info`` whose context is the
    ``HttpContext | WsContext`` union, but only the websocket half carries a
    consumer to subscribe on. This is the one place that narrowing happens, so
    call sites do not each need an ``assert isinstance(...)`` (which ``python -O``
    strips) or a ``cast`` (which lies if the assumption is ever wrong).
    """
    context = info.context
    if not isinstance(context, WsContext):
        raise TypeError(
            "This resolver requires a websocket connection, but the request "
            f"arrived over {getattr(context, 'type', type(context).__name__)}. "
            "Subscriptions must be executed over the GraphQL websocket transport."
        )
    return context


class ChannelsLayer(Protocol):  # pragma: no cover
    """Channels layer spec.

    Based on: https://channels.readthedocs.io/en/stable/channel_layer_spec.html
    """

    # Default channels API

    extensions: list[Literal["groups", "flush"]]

    async def send(self, channel: str, message: dict[str, Any]) -> None:
        """Send a message to a single channel."""
        ...

    async def receive(self, channel: str) -> dict[str, Any]:
        """Receive the next message on a channel."""
        ...

    async def new_channel(self, prefix: str = ...) -> str:
        """Allocate a new channel name."""
        ...

    # If groups extension is supported

    group_expiry: int

    async def group_add(self, group: str, channel: str) -> None:
        """Add a channel to a group."""
        ...

    async def group_discard(self, group: str, channel: str) -> None:
        """Remove a channel from a group."""
        ...

    async def group_send(self, group: str, message: dict[str, Any]) -> None:
        """Send a message to every channel in a group."""
        ...

    # If flush extension is supported

    async def flush(self) -> None:
        """Discard all channels and groups."""
        ...
