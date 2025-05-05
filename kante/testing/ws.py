import json
import asyncio
from typing import Any, AsyncGenerator, Callable, Dict, Optional
from channels.testing import ApplicationCommunicator
from types import TracebackType


class GraphQLWebSocketTestClient:
    """
    A test client for executing GraphQL subscriptions over WebSocket using the `graphql-ws` protocol.
    
    Supports connection initialization with payload, sending subscriptions, and streaming responses.
    
    Usage:
        async with GraphQLWebSocketTestClient(app, connection_params={"authToken": "abc"}) as client:
            async for msg in client.subscribe("subscription { time }", max_messages=1):
                assert "data" in msg["payload"]
    """

    def __init__(
        self,
        application: Any,
        path: str = "/graphql",
        protocol: str = "graphql-ws",
        connection_params: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize the WebSocket client.

        Args:
            application: The ASGI application instance.
            path: WebSocket endpoint path (default is "/graphql").
            protocol: The WebSocket subprotocol to use (default is "graphql-ws").
            connection_params: Optional payload for `connection_init` (e.g., auth tokens).
        """
        self.application = application
        self.path = path
        self.protocol = protocol
        self.connection_params = connection_params or {}
        self.communicator = ApplicationCommunicator(application, {
            "type": "websocket",
            "path": path,
            "headers": [(b"sec-websocket-protocol", protocol.encode())],
            "subprotocols": [protocol],
        })
        self.connected = False

    async def connect(self) -> None:
        """
        Establish the WebSocket connection and send a `connection_init` message.
        Awaits and verifies the `connection_ack` response.
        """
        await self.communicator.send_input({"type": "websocket.connect"})
        response = await self.communicator.receive_output(timeout=2)
        assert response["type"] == "websocket.accept"
        self.connected = True

        await self.communicator.send_input({
            "type": "websocket.receive",
            "text": json.dumps({
                "type": "connection_init",
                "payload": self.connection_params
            })
        })

        ack = await self.communicator.receive_output(timeout=2)
        assert ack["type"] == "websocket.send"
        ack_data = json.loads(ack["text"])
        assert ack_data["type"] == "connection_ack"

    async def subscribe(
        self,
        query: str,
        operation_id: str = "1",
        timeout: int = 5,
        max_messages: Optional[int] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Start a GraphQL subscription and yield incoming data messages.

        Args:
            query: The GraphQL subscription query string.
            operation_id: An identifier for the subscription operation.
            timeout: Timeout in seconds to wait for messages.
            max_messages: If provided, stops after receiving this number of data messages.

        Yields:
            Incoming subscription data messages as dictionaries.
        """
        await self.communicator.send_input({
            "type": "websocket.receive",
            "text": json.dumps({
                "id": operation_id,
                "type": "start",
                "payload": {"query": query}
            })
        })

        received_count = 0
        while True:
            try:
                msg = await asyncio.wait_for(self.communicator.receive_output(), timeout=timeout)
            except asyncio.TimeoutError:
                break

            if msg["type"] != "websocket.send":
                continue

            data = json.loads(msg["text"])
            msg_type = data.get("type")

            if msg_type == "data" and data.get("id") == operation_id:
                yield data
                received_count += 1
                if max_messages is not None and received_count >= max_messages:
                    break
            elif msg_type in ("complete", "error"):
                break

    async def receive(self, timeout: int = 2) -> Optional[Dict[str, Any]]:
        """
        Wait for and return a single WebSocket message.

        Args:
            timeout: Timeout in seconds.

        Returns:
            Parsed message dict or None if not of type `websocket.send`.
        """
        msg = await self.communicator.receive_output(timeout=timeout)
        if msg["type"] != "websocket.send":
            return None
        
        return json.loads(msg["text"])

    async def receive_until(
        self,
        match_fn: Callable[[Dict[str, Any]], bool],
        timeout: int = 5
    ) -> Dict[str, Any]:
        """
        Receive messages until a message matching `match_fn` is found or timeout occurs.

        Args:
            match_fn: A function that returns True for a matching message.
            timeout: Timeout in seconds.

        Returns:
            The matching message.

        Raises:
            TimeoutError: If no matching message is received.
        """
        end = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < end:
            try:
                msg = await self.receive(timeout=1)
                if msg and match_fn(msg):
                    return msg
            except asyncio.TimeoutError:
                continue
        raise TimeoutError("No matching message received within timeout.")

    async def disconnect(self) -> None:
        """
        Disconnect and clean up the communicator.
        """
        await self.communicator.wait()

    async def __aenter__(self) -> "GraphQLWebSocketTestClient":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> None:
        await self.disconnect()
