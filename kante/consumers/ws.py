"""The websocket GraphQL consumer, building kante's request context."""

from strawberry.channels import GraphQLWSConsumer
from strawberry.channels import ChannelsRequest
from kante.context import Context, WsContext, UniversalRequest
from strawberry.http.temporal_response import TemporalResponse
import logging

logger = logging.getLogger(__name__)


class KanteWsConsumer(GraphQLWSConsumer):
    """The websocket consumer, building kante's :class:`~kante.context.WsContext`."""

    # NOTE: strawberry annotates ``get_context`` as returning ``None`` on the
    # base view, but calls it for the context object. Overriding with the real
    # return type is the point of this class.
    async def get_context(  # type: ignore[override]
        self, request: ChannelsRequest, response: TemporalResponse
    ) -> Context:
        """Build the websocket request context."""
        return WsContext(
            request=UniversalRequest(_extensions={}),
            response=response,
            type="ws",
            connection_params={},
            consumer=self,
        )
