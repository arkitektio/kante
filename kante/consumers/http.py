"""The HTTP GraphQL consumer, building kante's request context."""

from strawberry.channels import GraphQLHTTPConsumer
from strawberry.channels.handlers.http_handler import ChannelsRequest
from strawberry.http.temporal_response import TemporalResponse
from kante.context import (
    Context,
    HttpContext,
    UniversalRequest,
)
import logging

logger = logging.getLogger(__name__)


NO_CHANNEL_LAYER = "kante.http.no-channel-layer"
"""A channel layer alias no project configures: ``get_channel_layer`` answers ``None`` for it."""


class KanteHTTPConsumer(GraphQLHTTPConsumer):
    """The HTTP consumer, building kante's :class:`~kante.context.HttpContext`.

    It takes no channel of its own. A channels consumer with a channel layer receives on
    that layer for as long as it lives, and every consumer of a process takes its turn
    popping the process's one inbox off redis. A request lives for milliseconds: its turn
    is cancelled when it answers, and a message redis handed over at that moment is gone
    (``channels_redis`` pops and backs up in two steps). The messages a mutation causes are
    sent right as its request ends, so those were the ones a subscription never saw.

    Nothing reaches a request over the layer, and a request never listens on it; what a
    resolver broadcasts goes through :func:`kante.channel.get_real_channel_layer`, not the
    consumer's.
    """

    channel_layer_alias = NO_CHANNEL_LAYER

    # NOTE: strawberry annotates ``get_context`` as returning ``None`` on the
    # base view, but calls it for the context object. Overriding with the real
    # return type is the point of this class.
    async def get_context(  # type: ignore[override]
        self, request: ChannelsRequest, response: TemporalResponse
    ) -> Context:
        """Build the HTTP request context."""
        return HttpContext(
            request=UniversalRequest(_extensions={}),
            response=response,
            headers=request.headers,
            type="http"
        )
