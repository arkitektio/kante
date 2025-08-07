from strawberry.channels import GraphQLWSConsumer
from strawberry.channels import ChannelsRequest
from kante.context import Context, WsContext, UniversalRequest
from strawberry.http.temporal_response import TemporalResponse
import logging

logger = logging.getLogger(__name__)


class KanteWsConsumer(GraphQLWSConsumer):
    pass

    async def get_context(
        self, request: ChannelsRequest, response: TemporalResponse
    ) -> Context:
        return WsContext(
            request=UniversalRequest(_extensions={}),
            type="ws",
            connection_params={},
            consumer=self,
        )
