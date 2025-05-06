import json
from typing import Any, Dict, Optional
from channels.testing import ApplicationCommunicator


class GraphQLHttpTestClient:
    """
    A simple test client for executing GraphQL queries via HTTP using Django Channels' ApplicationCommunicator.
    
    Example:
        client = GraphQLHttpTestClient(application)
        result = await client.execute("{ __typename }")
    """

    def __init__(
        self,
        application: Any,
        path: str = "/graphql",
        headers: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Initialize the test client.

        Args:
            application: The ASGI application to test.
            path: The HTTP path to send the GraphQL request to (default is "/graphql").
            headers: Optional dictionary of additional HTTP headers.
        """
        self.application = application
        self.path = path
        self.headers = headers or {}

    async def execute(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        timeout: int = 5
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query or mutation via HTTP.

        Args:
            query: The GraphQL query string.
            variables: Optional dictionary of GraphQL variables.
            operation_name: Optional name of the operation (if query contains multiple).
            timeout: Maximum time to wait for a response in seconds.

        Returns:
            A dictionary containing the JSON-decoded GraphQL response.

        Raises:
            AssertionError: If the HTTP response is not 200 OK or malformed.
        """
        body: Dict[str, Any] = {"query": query}
        if variables is not None:
            body["variables"] = variables
        if operation_name is not None:
            body["operationName"] = operation_name

        encoded_body = json.dumps(body).encode()

        # Prepare headers for ASGI
        header_list = [(b"content-type", b"application/json")]
        for key, value in self.headers.items():
            header_list.append((key.encode(), value.encode()))

        communicator = ApplicationCommunicator(self.application, {
            "type": "http",
            "method": "POST",
            "path": self.path,
            "headers": header_list,
            "body": encoded_body,
        })

        await communicator.send_input({
            "type": "http.request",
            "body": encoded_body,
        })

        response_start = await communicator.receive_output(timeout=timeout)
        assert response_start["type"] == "http.response.start", f"Unexpected type: {response_start}"
        assert response_start["status"] == 200, f"Unexpected status: {response_start['status']}"

        response_body = await communicator.receive_output(timeout=timeout)
        assert response_body["type"] == "http.response.body", f"Unexpected type: {response_body}"

        return json.loads(response_body["body"])
