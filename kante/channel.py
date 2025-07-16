from typing import AsyncGenerator, Optional, List, Type, TypeVar, Generic
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from pydantic import BaseModel, ValidationError
from kante.context import WsContext
from strawberry.channels.handlers.base import ChannelsLayer
import logging
import uuid

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def get_real_channel_layer() -> ChannelsLayer:
    """Get the real channel layer, not the mock one."""
    channel_layer = get_channel_layer() # as
    if not channel_layer:
        raise RuntimeError("Channel layer is not available in the context")
    return channel_layer


class Channel(Generic[T]):
    """A typed GraphQL channel using Pydantic for serialization."""

    def __init__(self, model: Type[T], name: Optional[str] = None) -> None:
        self.model = model
        self.name = name or model.__name__
        self.id = str(uuid.uuid4())

    def broadcast(self, message: T, groups: Optional[List[str]] = None) -> None:
        """Broadcast a validated model instance to groups."""
        groups = groups or ["default"]
        channel_layer = get_real_channel_layer()
        message_data = message.model_dump()

        for group in groups:
            logger.debug(f"[{self.name}] Broadcasting to group '{group}': {message_data}")
            async_to_sync(channel_layer.group_send)(
                group,
                {
                    "type": f"channel.{self.name}",
                    "message": message_data,
                },
            )

    async def listen(self, context: WsContext, groups: Optional[List[str]] = None) -> AsyncGenerator[T, None]:
        """Async generator that yields deserialized model messages."""
        assert isinstance(context, WsContext), "Context must be a WsContext instance"
        groups = groups or ["default"]
        channel_layer = context.consumer.channel_layer
        channel_name = context.consumer.channel_name
        if not channel_layer:
            raise RuntimeError("Channel layer is not available in the context")

        for group in groups:
            logger.debug(f"[{self.name}] Subscribing '{channel_name}' to group '{group}'")
            await channel_layer.group_add(group, channel_name)

        async with context.consumer.listen_to_channel(f"channel.{self.name}", groups=groups) as cm:
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