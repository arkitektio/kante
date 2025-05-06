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
    pass

    async def get_context(
        self, request: ChannelsRequest, response: TemporalResponse
    ) -> Context:
        
        return HttpContext(
            request=UniversalRequest(_extensions={}),
            headers=request.headers,
            type="http"
        )
        
