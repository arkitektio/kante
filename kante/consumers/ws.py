from strawberry.channels import GraphQLWSConsumer
from strawberry.channels import ChannelsRequest
from typing import Any
from kante.context import Context, WsContext
import logging

logger = logging.getLogger(__name__)


class KanteWsConsumer(GraphQLWSConsumer):
    pass

    async def get_context(
        self, request: ChannelsRequest, response: Any
    ) -> Context:
        return WsContext(
            _request=request,
            type="ws",
            connection_params={},
            consumer=self,
        )
