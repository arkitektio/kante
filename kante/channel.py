from typing import AsyncGenerator, Optional, List, Type, TypeVar, Generic
from channels.layers import get_channel_layer # type: ignore
from asgiref.sync import async_to_sync
from pydantic import BaseModel, ValidationError
from kante.context import WsContext
from kante.types import ChannelsLayer
import asyncio
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def get_real_channel_layer() -> ChannelsLayer:
    """Get the real channel layer, not the mock one."""
    channel_layer = get_channel_layer() # type: ignore
    if not channel_layer:
        raise RuntimeError("Channel layer is not available in the context")
    return channel_layer # type: ignore # noqa: E501


class Channel(Generic[T]):
    """A typed GraphQL channel using Pydantic for serialization.

    Note: channels built from the same model without an explicit ``name`` share
    the same message type and will receive each other's broadcasts. Pass a
    distinct ``name`` to keep two channels of the same model isolated.
    """

    def __init__(self, model: Type[T], name: Optional[str] = None) -> None:
        self.model = model
        self.name = name or model.__name__
        # Precomputed once so broadcast/listen don't rebuild it per call and so
        # both sides share a single source of truth for the message type.
        self.message_type = f"channel.{self.name}"

    async def abroadcast(self, message: T, groups: Optional[List[str]] = None) -> None:
        """Broadcast a validated model instance to groups (async-native).

        Use this from async code (resolvers, subscriptions, any running event
        loop). ``broadcast`` is the sync wrapper around it.
        """
        groups = groups or ["default"]
        channel_layer = get_real_channel_layer()
        # mode="json" yields primitives (e.g. ISO strings for datetime, str for
        # UUID/Decimal) so the message survives the channel layer's serializer
        # (channels-redis uses msgpack, which cannot pack native datetime/UUID).
        # The receiving end's model_validate coerces them back to rich types.
        message_data = message.model_dump(mode="json")
        payload = {
            "type": self.message_type,
            "message": message_data,
        }

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "[%s] Broadcasting to groups %s: %s", self.name, groups, message_data
            )

        # Fan out concurrently; group_send treats payload as read-only (it is
        # re-serialized per group), so sharing one dict across calls is safe.
        await asyncio.gather(
            *(channel_layer.group_send(group, payload) for group in groups)
        )

    def broadcast(self, message: T, groups: Optional[List[str]] = None) -> None:
        """Broadcast a validated model instance to groups (sync wrapper).

        Performance/correctness: this bridges to the event loop exactly once via
        a single ``async_to_sync`` call rather than once per group. Note that
        ``async_to_sync`` raises if called from a thread already running an event
        loop -- call ``abroadcast`` from async code instead.
        """
        async_to_sync(self.abroadcast)(message, groups)

    async def listen(
        self,
        context: WsContext,
        groups: Optional[List[str]] = None,
        timeout: Optional[float] = None,
    ) -> AsyncGenerator[T, None]:
        """Async generator that yields deserialized model messages.

        ``timeout`` is forwarded to the underlying listener as a per-message wait
        bound (``None`` waits indefinitely).
        """
        # Explicit guard (not assert) so it still fires under ``python -O``.
        if not isinstance(context, WsContext):
            raise TypeError("Channel.listen requires a WsContext")
        groups = groups or ["default"]
        channel_layer = context.consumer.channel_layer
        if not channel_layer:
            raise RuntimeError("Channel layer is not available in the context")

        # NOTE: do NOT call ``group_add`` here -- ``listen_to_channel(groups=...)``
        # already registers (and later discards) the channel for each group.
        # Adding them manually doubled the registration round-trips per
        # subscription and skipped the matching ``group_discard`` on teardown.
        async with context.consumer.listen_to_channel(
            self.message_type, groups=groups, timeout=timeout
        ) as cm:
            async for message in cm:
                raw = message.get("message")
                try:
                    yield self.model.model_validate(raw)
                except ValidationError as e:
                    logger.warning(f"[{self.name}] Invalid message received: {e}")
                    continue  # Optionally re-raise or yield raw here



def build_channel(model: Type[T], name: Optional[str] = None) -> Channel[T]:
    """Build a channel with the given model and optional name."""
    return Channel(model, name)