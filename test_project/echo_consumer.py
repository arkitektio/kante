# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer


class EchoConsumer(AsyncWebsocketConsumer):  # type: ignore[misc]
    """
    A simple WebSocket consumer that responds to specific messages.
    """

    async def connect(self) -> None:
        """
        Called when a WebSocket connection is established.
        """
        await self.accept()

    async def disconnect(self, code: int) -> None:
        """
        Called when the WebSocket connection is closed.
        """
        pass  # You can add cleanup logic here if needed.

    async def receive(self, text_data: str | None = None, bytes_data: bytes | None = None) -> None:
        """
        Called when a message is received from the WebSocket.
        """
        if bytes_data is not None:
            # Handle binary data if needed
            return

        if text_data is None:
            return

        data = json.loads(text_data)
        message = data.get("message", "")

        if message == "ping":
            response = {"message": "pong"}
        elif message == "hello":
            response = {"message": "hi"}
        else:
            response = {"message": f"echo: {message}"}

        await self.send(text_data=json.dumps(response))
