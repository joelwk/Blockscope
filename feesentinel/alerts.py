"""Alert and webhook functionality for fee bucket monitoring."""

import json
from datetime import datetime, timedelta
from http.client import HTTPSConnection, HTTPConnection
from urllib.parse import urlparse
from typing import Dict, Optional
from .logging import get_logger
from .buckets import FeeBucket
from .constants import DEFAULT_HTTP_TIMEOUT_SECS
from .structured_output import StructuredOutputWriter

logger = get_logger(__name__)


class AlertManager:
    """Manages fee bucket alerts and webhook posting."""
    
    def __init__(
        self,
        webhook_url: str,
        min_change_secs: int,
        structured_writer: Optional[StructuredOutputWriter] = None,
    ):
        """
        Initialize alert manager.
        
        Args:
            webhook_url: Webhook URL for alerts (empty string to disable)
            min_change_secs: Minimum seconds between alerts for same bucket severity
            structured_writer: Optional structured output writer for recording
                fee alerts in a JSONL-friendly format.
        """
        self.webhook_url = webhook_url
        self.min_change_secs = min_change_secs
        self._structured_writer = structured_writer
        self._last_bucket_alert = {"bucket_name": None, "severity": None, "ts": datetime.min}
        self._last_spike_alert_ts = datetime.min
    
    def post_webhook(self, payload: Dict) -> None:
        """
        Post payload to webhook URL.
        
        Args:
            payload: Dictionary to send as JSON
        """
        if not self.webhook_url:
            logger.debug(f"No webhook configured, payload: {json.dumps(payload)}")
            # Even if no webhook is configured, we may still want structured output
            if self._structured_writer is not None:
                self._structured_writer.record_fee_alert(payload)
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

        # Record to structured output if configured
        if self._structured_writer is not None:
            self._structured_writer.record_fee_alert(payload)
    
    def maybe_alert_bucket_change(self, bucket: FeeBucket, snapshot: Dict) -> None:
        """
        Send alert if fee bucket changed (by severity) and quiet period elapsed.
        
        Args:
            bucket: Current fee bucket
            snapshot: Current fee snapshot dictionary
        """
        now = datetime.utcnow()
        changed = (self._last_bucket_alert["severity"] != bucket.severity)
        quieted = (now - self._last_bucket_alert["ts"]).total_seconds() >= self.min_change_secs
        
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
            self._last_bucket_alert = {
                "bucket_name": bucket.name,
                "severity": bucket.severity,
                "ts": now,
            }

    def maybe_alert_spike(self, payload: Dict, cooldown_secs: int) -> None:
        """
        Send alert if fee spike detected and cooldown elapsed.
        
        Args:
            payload: Alert payload
            cooldown_secs: Cooldown period in seconds
        """
        now = datetime.utcnow()
        if (now - self._last_spike_alert_ts).total_seconds() >= cooldown_secs:
            logger.info(f"Fee spike detected: {payload.get('spike_pct', 0)}% jump, sending alert")
            self.post_webhook(payload)
            self._last_spike_alert_ts = now

    # Backward compatibility alias
    maybe_alert = maybe_alert_bucket_change

