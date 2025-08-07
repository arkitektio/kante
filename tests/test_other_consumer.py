# test_consumers.py
import pytest
import json
from channels.testing import WebsocketCommunicator
from test_project.asgi import application


@pytest.mark.asyncio
async def test_echo_consumer(db) -> None:
    communicator = WebsocketCommunicator(application, "ws/echo/")
    connected, _ = await communicator.connect()
    assert connected

    # Test "ping" message
    await communicator.send_to(text_data=json.dumps({"message": "ping"}))
    response = await communicator.receive_from()
    assert json.loads(response) == {"message": "pong"}

    # Test "hello" message
    await communicator.send_to(text_data=json.dumps({"message": "hello"}))
    response = await communicator.receive_from()
    assert json.loads(response) == {"message": "hi"}

    # Test arbitrary message
    await communicator.send_to(text_data=json.dumps({"message": "test"}))
    response = await communicator.receive_from()
    assert json.loads(response) == {"message": "echo: test"}

    await communicator.disconnect()
