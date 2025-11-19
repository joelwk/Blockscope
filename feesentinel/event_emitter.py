"""Event emission for event monitoring with retry logic and reliability."""

import json
import time
from datetime import datetime
from http.client import HTTPSConnection, HTTPConnection
from urllib.parse import urlparse
from typing import Dict, List, Optional
from .logging import get_logger
from .constants import DEFAULT_HTTP_TIMEOUT_SECS
from .structured_output import StructuredOutputWriter

logger = get_logger(__name__)


class EventEmitter:
    """Emits events to webhook endpoints with retry logic."""

    def __init__(
        self,
        webhook_urls: List[str] = None,
        retry_attempts: int = 3,
        retry_backoff_secs: int = 5,
        structured_writer: Optional[StructuredOutputWriter] = None,
    ):
        """
        Initialize event emitter.

        Args:
            webhook_urls: List of webhook URLs (can be empty to disable)
            retry_attempts: Number of retry attempts per event
            retry_backoff_secs: Base backoff time in seconds (exponential)
        """
        self.webhook_urls = webhook_urls or []
        self.retry_attempts = retry_attempts
        self.retry_backoff_secs = retry_backoff_secs
        self._structured_writer = structured_writer
        
        logger.info(f"Initialized event emitter: {len(self.webhook_urls)} endpoints")

    def _post_webhook(self, url: str, payload: Dict) -> bool:
        """
        Post payload to a single webhook URL.

        Args:
            url: Webhook URL
            payload: Payload dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            parsed = urlparse(url)
            conn_cls = HTTPSConnection if parsed.scheme == "https" else HTTPConnection
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            
            conn = conn_cls(parsed.hostname, port, timeout=DEFAULT_HTTP_TIMEOUT_SECS)
            body = json.dumps(payload)
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
            
            headers = {"Content-Type": "application/json"}
            conn.request("POST", path, body=body, headers=headers)
            resp = conn.getresponse()
            _ = resp.read()  # Consume response
            conn.close()
            
            if resp.status >= 400:
                logger.warning(f"Webhook returned status {resp.status}: {resp.reason}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to post webhook to {url}: {e}", exc_info=True)
            return False

    def emit(self, event_type: str, data: Dict, txid: str = None, block_height: int = None) -> bool:
        """
        Emit an event to all configured webhook URLs.

        Args:
            event_type: Type of event (e.g., "treasury_utxo_spent", "ordinal_inscription")
            data: Event data dictionary
            txid: Transaction ID (optional)
            block_height: Block height (optional)

        Returns:
            True if at least one endpoint succeeded, False otherwise
        """
        payload = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        if txid:
            payload["txid"] = txid
        if block_height is not None:
            payload["block_height"] = block_height

        # Record structured event payload even if no webhooks are configured
        if self._structured_writer is not None:
            self._structured_writer.record_event(payload)

        if not self.webhook_urls:
            logger.debug(f"No webhook URLs configured, skipping event: {event_type}")
            return True  # Not an error if no endpoints configured

        success_count = 0
        
        for url in self.webhook_urls:
            for attempt in range(self.retry_attempts):
                if self._post_webhook(url, payload):
                    success_count += 1
                    logger.debug(f"Emitted event {event_type} to {url}")
                    break
                
                if attempt < self.retry_attempts - 1:
                    backoff = self.retry_backoff_secs * (2 ** attempt)
                    logger.debug(f"Retrying event emission in {backoff}s (attempt {attempt + 1}/{self.retry_attempts})")
                    time.sleep(backoff)
                else:
                    logger.error(f"Failed to emit event {event_type} to {url} after {self.retry_attempts} attempts")
        
        return success_count > 0

    def emit_treasury_event(self, filter_result: Dict, txid: str, block_height: int) -> bool:
        """
        Emit treasury UTXO event with enriched metadata.

        Args:
            filter_result: Result from TransactionFilter.check_treasury_utxo (enriched)
            txid: Transaction ID
            block_height: Block height

        Returns:
            True if emitted successfully
        """
        event_type_map = {
            "spend": "treasury_utxo_spent",
            "receive": "treasury_utxo_received",
            "both": "treasury_utxo_both"
        }
        
        event_type = event_type_map.get(filter_result["type"])
        if not event_type:
            return False
        
        # Build enriched data payload
        data = {
            # Legacy fields for backward compatibility
            "addresses": filter_result.get("addresses", []),
            "inputs": filter_result.get("inputs", []),
            "outputs": filter_result.get("outputs", []),
            # New enriched fields
            "enriched_addresses": filter_result.get("enriched_addresses", []),
            "entities": filter_result.get("entities", []),
            "summary": filter_result.get("summary", {})
        }
        
        return self.emit(event_type, data, txid=txid, block_height=block_height)

    def emit_ordinal_event(self, filter_result: Dict, txid: str, block_height: int) -> bool:
        """
        Emit ordinal inscription event with hotspot information.

        Args:
            filter_result: Result from TransactionFilter.check_ordinal (with hotspots)
            txid: Transaction ID
            block_height: Block height

        Returns:
            True if emitted successfully
        """
        data = {
            "inscriptions": filter_result.get("inscriptions", []),
            "hotspots": filter_result.get("hotspots", [])
        }
        
        return self.emit("ordinal_inscription", data, txid=txid, block_height=block_height)

    def emit_covenant_event(self, filter_result: Dict, txid: str, block_height: int) -> bool:
        """
        Emit covenant flow event.

        Args:
            filter_result: Result from TransactionFilter.check_covenant
            txid: Transaction ID
            block_height: Block height

        Returns:
            True if emitted successfully
        """
        data = {
            "patterns": filter_result["patterns"]
        }
        
        return self.emit("covenant_flow", data, txid=txid, block_height=block_height)

    def emit_block_event(self, block_height: int, block_hash: str, tx_count: int, reorg: bool = False) -> bool:
        """
        Emit block confirmation event.

        Args:
            block_height: Block height
            block_hash: Block hash
            tx_count: Number of transactions in block
            reorg: Whether this is a reorg recovery

        Returns:
            True if emitted successfully
        """
        event_type = "reorg_detected" if reorg else "block_confirmed"
        
        data = {
            "block_hash": block_hash,
            "tx_count": tx_count,
            "reorg": reorg
        }
        
        return self.emit(event_type, data, block_height=block_height)

