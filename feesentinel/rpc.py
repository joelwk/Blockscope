"""Bitcoin RPC client for Blockscope."""

import json
import requests
from typing import Any


class PrunedBlockError(Exception):
    """Raised when attempting to access a block that has been pruned."""
    def __init__(self, block_hash: str = None, height: int = None, message: str = None):
        self.block_hash = block_hash
        self.height = height
        self.message = message or "Block not available (pruned data)"
        super().__init__(self.message)


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
            PrunedBlockError: If attempting to access a pruned block
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
            error = result["error"]
            # Check if this is a pruned block error
            if isinstance(error, dict):
                error_message = error.get("message", "")
                if "pruned" in error_message.lower() or "not available" in error_message.lower():
                    # Try to extract block hash from params if available
                    block_hash = params[0] if params and isinstance(params[0], str) else None
                    raise PrunedBlockError(block_hash=block_hash, message=str(error))
            raise RuntimeError(error)
        
        return result["result"]

