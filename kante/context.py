from strawberry.channels import ChannelsConsumer, ChannelsRequest
from dataclasses import dataclass
from typing import Any, Dict, Literal, Mapping, Optional, Protocol



class User(Protocol):
    id: int 
    sub: str
    
    def is_anonymous(self) -> bool:
        """Check if the user is anonymous."""
        return self.id is None
    
    
class Client(Protocol):
    client_id: str
    

@dataclass
class UniversalRequest:
    _extensions: Dict[str, Any]
    _client: Optional[Client] = None
    _user: Optional[User] = None
    
    @property
    def user(self) -> User:
        """Get the user associated with the request."""
        if self._user is None:
            raise ValueError("User is not set in the request. Do you have a strawberry extension setting this?")
        
        return self._user
    
    
    @property
    def client(self) -> Client:
        if self._client is None:
            raise ValueError("Client is not set in the request.  Do you have a strawberry extension setting this?")
        
        return self._client
    
    
    
    def set_user(self, user: User) -> None:
        """Set an extension value in the request."""
        self._user = user
        
    def set_client(self, client: Client) -> None:
        """Set an extension value in the request."""
        self._client = client
        
        
    def get_extension(self, name: str) -> Any:
        """Get an extension value from the request."""
        
        if name not in self._extensions:
            raise ValueError(f"Extension {name} is not set in the request.")
        return self._extensions.get(name)
    
    def set_extension(self, name: str, value: Any) -> None:
        """Set an extension value in the request."""
        if name in self._extensions:
            raise ValueError(f"Extension {name} is already set in the request.")
        
        self._extensions[name] = value




@dataclass
class WsContext:
    request: UniversalRequest
    connection_params: Dict[str, Any]
    consumer: ChannelsConsumer
    extensions: Optional[Dict[str, Any]] = None
    type: Literal["ws"] = "ws"
    
    
               


@dataclass
class HttpContext:
    request: UniversalRequest
    headers: Mapping[str, str]
    type: Literal["http"] = "http"
    
    
        
        
        
Context = HttpContext | WsContext
        
        
    
    
    
    
    