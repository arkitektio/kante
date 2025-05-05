from strawberry.channels import ChannelsConsumer, ChannelsRequest
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

@dataclass
class WsContext:
    _request: ChannelsRequest
    type: Literal["ws"]
    connection_params: Dict[str, Any]
    consumer: ChannelsConsumer
    extensions: Optional[Dict[str, Any]] = None
    
    def get_extension(self, name: str) -> Optional[Any]:
        if self.extensions is None:
            return None
        return self.extensions.get(name, None)
    
    
    def set_extension(self, name: str, value: Any) -> None:
        if self.extensions is None:
            self.extensions = {}
        self.extensions[name] = value
    
    
               


@dataclass
class HttpContext:
    _request: ChannelsRequest
    type: Literal["http", "ws"]
    headers: Optional[Dict[str, Any]] = None
    extensions: Optional[Dict[str, Any]] = None
    
    
    def get_extension(self, name: str) -> Optional[Any]:
        if self.extensions is None:
            return None
        return self.extensions.get(name, None)
    
    
    def set_extension(self, name: str, value: Any) -> None:
        if self.extensions is None:
            self.extensions = {}
        self.extensions[name] = value
        
        
        
Context = HttpContext | WsContext
        
        
    
    
    
    
    