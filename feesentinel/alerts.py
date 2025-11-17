"""Alert and webhook functionality for fee bucket monitoring."""

import json
from datetime import datetime, timedelta
from http.client import HTTPSConnection, HTTPConnection
from urllib.parse import urlparse
from typing import Dict
from .logging import get_logger
from .buckets import FeeBucket
from .constants import DEFAULT_HTTP_TIMEOUT_SECS

logger = get_logger(__name__)


class AlertManager:
    """Manages fee bucket alerts and webhook posting."""
    
    def __init__(self, webhook_url: str, min_change_secs: int):
        """
        Initialize alert manager.
        
        Args:
            webhook_url: Webhook URL for alerts (empty string to disable)
            min_change_secs: Minimum seconds between alerts for same bucket severity
        """
        self.webhook_url = webhook_url
        self.min_change_secs = min_change_secs
        self._last_alert = {"bucket_name": None, "severity": None, "ts": datetime.min}
    
    def post_webhook(self, payload: Dict) -> None:
        """
        Post payload to webhook URL.
        
        Args:
            payload: Dictionary to send as JSON
        """
        if not self.webhook_url:
            logger.debug(f"No webhook configured, payload: {json.dumps(payload)}")
            return
        
        url = urlparse(self.webhook_url)
        conn_cls = HTTPSConnection if url.scheme == "https" else HTTPConnection
        port = url.port or (443 if url.scheme == "https" else 80)
        
        conn = conn_cls(url.hostname, port, timeout=DEFAULT_HTTP_TIMEOUT_SECS)
        body = json.dumps(payload)
        path = url.path or "/"
        if url.query:
            path += "?" + url.query
        
        headers = {"Content-Type": "application/json"}
        try:
            conn.request("POST", path, body=body, headers=headers)
            resp = conn.getresponse()
            _ = resp.read()  # Consume response
            if resp.status >= 400:
                logger.warning(f"Webhook returned status {resp.status}: {resp.reason}")
            else:
                logger.debug(f"Webhook posted successfully: {json.dumps(payload)}")
        except Exception as e:
            logger.error(f"Failed to post webhook: {e}", exc_info=True)
        finally:
            conn.close()
    
    def maybe_alert(self, bucket: FeeBucket, snapshot: Dict) -> None:
        """
        Send alert if fee bucket changed (by severity) and quiet period elapsed.
        
        Args:
            bucket: Current fee bucket
            snapshot: Current fee snapshot dictionary
        """
        now = datetime.utcnow()
        changed = (self._last_alert["severity"] != bucket.severity)
        quieted = (now - self._last_alert["ts"]).total_seconds() >= self.min_change_secs
        
        if changed and quieted:
            payload = {
                "type": "fee_bucket_change",
                "bucket": {
                    "name": bucket.name,
                    "label": bucket.label,
                    "severity": bucket.severity,
                    "range_satvb": [bucket.min_satvb, bucket.max_satvb],
                },
                "observed": snapshot,
                "ts": now.isoformat() + "Z",
            }
            logger.info(f"Fee bucket changed to {bucket.name} ({bucket.label}), sending alert")
            self.post_webhook(payload)
            self._last_alert = {
                "bucket_name": bucket.name,
                "severity": bucket.severity,
                "ts": now,
            }

