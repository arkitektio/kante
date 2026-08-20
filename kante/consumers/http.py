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


class KanteHTTPConsumer(GraphQLHTTPConsumer):
    """The HTTP consumer, building kante's :class:`~kante.context.HttpContext`."""

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
        
