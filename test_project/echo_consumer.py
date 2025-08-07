# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class EchoConsumer(AsyncWebsocketConsumer):
    """
    A simple WebSocket consumer that responds to specific messages.
    """

    async def connect(self) -> None:
        """
        Called when a WebSocket connection is established.
        """
        await self.accept()

    async def disconnect(self, close_code: int) -> None:
        """
        Called when the WebSocket connection is closed.
        """
        pass  # You can add cleanup logic here if needed.

    async def receive(self, text_data: str) -> None:
        """
        Called when a message is received from the WebSocket.
        """
        data = json.loads(text_data)
        message = data.get("message", "")

        if message == "ping":
            response = {"message": "pong"}
        elif message == "hello":
            response = {"message": "hi"}
        else:
            response = {"message": f"echo: {message}"}

        await self.send(text_data=json.dumps(response))
