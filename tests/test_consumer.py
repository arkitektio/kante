""" Test the basic application of the ASGI app."""


# tests/test_asgi_communicator.py
import json
import pytest
from channels.testing import ApplicationCommunicator
from test_project.asgi import application  # your ASGI app


@pytest.mark.asyncio
async def test_typename_query() -> None:
    """ Test that a simple GraphQL query returns the expected __typename."""
    communicator = ApplicationCommunicator(application, {
        "type": "http",
        "method": "POST",
        "path": "/graphql",
        "headers": [
            (b"content-type", b"application/json"),
        ],
        "body": json.dumps({"query": "{ __typename }"}).encode(),
    })

    await communicator.send_input({
        "type": "http.request",
        "body": json.dumps({"query": "{ __typename }"}).encode(),
    })

    response_start = await communicator.receive_output(timeout=5)
    assert response_start["type"] == "websockets.http.response.start"
    assert response_start["status"] == 200

    response_body = await communicator.receive_output(timeout=5)
    data = json.loads(response_body["body"])
    assert data["data"]["__typename"] == "Query"

    await communicator.wait()
