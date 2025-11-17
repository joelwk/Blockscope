"""Bitcoin RPC client for Blockscope."""

import json
import requests
from typing import Any


class RPCClient:
    """Bitcoin RPC client with persistent session."""
    
    def __init__(self, url: str, user: str, password: str):
        """
        Initialize RPC client.
        
        Args:
            url: RPC URL (e.g., "http://127.0.0.1:8332")
            user: RPC username
            password: RPC password
        """
        self.url = url
        self.session = requests.Session()
        self.session.headers["content-type"] = "application/json"
        self.session.auth = (user, password)
    
    def call(self, method: str, *params: Any) -> Any:
        """
        Make an RPC call.
        
        Args:
            method: RPC method name
            *params: RPC method parameters
        
        Returns:
            RPC result
        
        Raises:
            RuntimeError: If RPC returns an error
            requests.RequestException: If HTTP request fails
        """
        payload = {
            "jsonrpc": "2.0",
            "id": "fs",
            "method": method,
            "params": list(params)
        }
        response = self.session.post(self.url, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()
        
        if "error" in result and result["error"]:
            raise RuntimeError(result["error"])
        
        return result["result"]

