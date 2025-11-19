"""Main runner loop for fee monitoring."""

import os
import sys
import time
import json
from datetime import datetime, timedelta
from typing import Optional, Dict
from .config import Config
from .rpc import RPCClient
from .fees import current_fee_percentiles
from .rolling import Rolling
from .alerts import AlertManager
from .consolidation import ConsolidationManager
from .logging import get_logger
from .buckets import classify_fee_bucket, FEE_POLICIES, FeeBucket
from .constants import DEFAULT_PSBT_COOLDOWN_SECS
from .structured_output import StructuredOutputWriter
from . import policies

logger = get_logger(__name__)

# PSBT cooldown state
_last_psbt = {"ts": datetime.min}


def get_psbt_cooldown_secs(config: Optional[Config] = None) -> int:
    """
    Get PSBT cooldown seconds from config or environment variable.
    
    Args:
        config: Optional Config instance
        
    Returns:
        Cooldown seconds (default: DEFAULT_PSBT_COOLDOWN_SECS)
    """
    if config:
        return config.psbt_cooldown_secs
    return int(os.getenv("FS_PSBT_COOLDOWN_SECS", str(DEFAULT_PSBT_COOLDOWN_SECS)))


def should_prepare_consolidation(bucket: FeeBucket, cooldown_secs: int) -> bool:
    """
    Decide whether to prepare a consolidation PSBT in the current bucket.
    Uses FEE_POLICIES plus a global cooldown.
    
    Args:
        bucket: Current fee bucket
        cooldown_secs: Cooldown period in seconds
        
    Returns:
        True if consolidation should be prepared, False otherwise
    """
    global _last_psbt
    
    policy = FEE_POLICIES.get(bucket.name, {})
    if not policy.get("consolidate_ok", False):
        return False
    
    now = datetime.utcnow()
    since_last = (now - _last_psbt["ts"]).total_seconds()
    if since_last < cooldown_secs:
        return False
    
    _last_psbt["ts"] = now
    return True


class FeeSentinelRunner:
    """Main runner for fee monitoring loop."""
    
    def __init__(self, config: Config, structured_writer: Optional[StructuredOutputWriter] = None):
        """
        Initialize runner with configuration.
        
        Args:
            config: Configuration instance
        """
        self.config = config
        self._structured_writer = structured_writer
        self.rpc_client = RPCClient(
            config.rpc_url,
            config.rpc_user,
            config.rpc_password
        )
        self.rolling = Rolling(config.rolling_window_mins)
        self.alert_manager = AlertManager(
            config.alert_webhook_url,
            config.alert_min_change_secs,
            structured_writer=self._structured_writer,
        )
        self.consolidation_manager = None
        if config.consolidate_target_address:
            self.consolidation_manager = ConsolidationManager(
                self.rpc_client,
                config.consolidate_target_address,
                config.consolidate_min_utxo_sats,
                config.consolidate_max_inputs,
                config.consolidate_label
            )
    
    def run_once(self, prepare_psbt: bool = False) -> Dict:
        """
        Run one monitoring iteration.
        
        Args:
            prepare_psbt: Whether to prepare PSBT if conditions are met
        
        Returns:
            Dictionary with snapshot and optional PSBT result
        """
        snapshot = current_fee_percentiles(self.rpc_client)
        ts = datetime.utcnow()
        
        self.rolling.add(ts, snapshot["p50"])
        stats = self.rolling.stats()
        bucket = classify_fee_bucket(snapshot["p50"])
        
        result = {
            "snapshot": snapshot,
            "rolling_stats": stats,
            "bucket": {
                "name": bucket.name,
                "label": bucket.label,
                "severity": bucket.severity,
            },
            "timestamp": ts.isoformat() + "Z"
        }

        # Record structured fee snapshot for future database rollups
        if self._structured_writer is not None:
            snapshot_record = {
                "type": "fee_snapshot",
                "snapshot": snapshot,
                "rolling_stats": stats,
                "bucket": {
                    "name": bucket.name,
                    "label": bucket.label,
                    "severity": bucket.severity,
                },
                "timestamp": ts.isoformat() + "Z",
            }
            self._structured_writer.record_fee_snapshot(snapshot_record)
        
        # Optional consolidation PSBT, bucket-aware
        cooldown_secs = get_psbt_cooldown_secs(self.config)
        if prepare_psbt and self.consolidation_manager and should_prepare_consolidation(bucket, cooldown_secs):
            # Choose a conservative fee: at least 1 sat/vB, capped within the bucket range
            target_satvb = max(1, min(snapshot["p50"], bucket.max_satvb))
            try:
                psbt_result = self.consolidation_manager.prepare_psbt(target_satvb)
                result["psbt"] = psbt_result
                alert_payload = {
                    "type": "psbt_prepare",
                    "bucket": bucket.name,
                    "target_satvb": target_satvb,
                    "policy_note": FEE_POLICIES.get(bucket.name, {}).get("note", ""),
                    "result": psbt_result,
                    "ts": ts.isoformat() + "Z"
                }
                self.alert_manager.post_webhook(alert_payload)
                logger.info(
                    f"Prepared consolidation PSBT for bucket {bucket.name} "
                    f"with target {target_satvb} sat/vB: {psbt_result.get('status', 'unknown')}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to prepare consolidation PSBT for bucket {bucket.name} "
                    f"with target {target_satvb} sat/vB: {e}",
                    exc_info=True
                )
        
        return result
    
    def run_continuous(self, poll_secs: int, dry_run: bool, prepare_psbt: bool):
        """
        Run continuous monitoring loop.
        
        Args:
            poll_secs: Seconds between polls
            dry_run: If True, only log (no side effects beyond alerts)
            prepare_psbt: Whether to prepare PSBTs when conditions are met
        """
        while True:
            try:
                result = self.run_once(prepare_psbt)
                snapshot = result["snapshot"]
                stats = result["rolling_stats"]
                bucket = classify_fee_bucket(snapshot["p50"])
                ts = datetime.utcnow()
                
                # Bucket classification + logging
                line = (
                    f"[{ts.isoformat()}Z] "
                    f"p50={snapshot['p50']} sat/vB [{bucket.name}] | "
                    f"p25={snapshot['p25']} p75={snapshot['p75']} p90={snapshot['p90']} | "
                    f"tx={snapshot['tx_count']} | "
                    f"roll_avg={stats['avg']}({stats.get('n', 0)}pts)"
                )
                logger.info(line)
                
                # Send alert if bucket changed
                self.alert_manager.maybe_alert_bucket_change(
                    bucket,
                    {
                        "p50": snapshot["p50"],
                        "p75": snapshot["p75"],
                        "p95": snapshot.get("p95", snapshot["p90"]),
                        "rolling_avg": stats["avg"],
                        "tx": snapshot["tx_count"],
                        "bucket_note": FEE_POLICIES.get(bucket.name, {}).get("note", "")
                    }
                )
                
                # Check for fee spikes and policy adjustments
                spike_config = self.config.spike_detection_config
                current_satvb = snapshot["p50"]
                trail_avg = stats["avg"]

                if policies.should_alert_spike(current_satvb, trail_avg, spike_config):
                    spike_payload = {
                        "type": "fee_spike",
                        "now_sat_vb": round(current_satvb, 2),
                        "trail_avg_sat_vb": round(trail_avg, 2),
                        "spike_pct": round(100.0 * (current_satvb - trail_avg) / max(trail_avg, 1e-9), 2),
                        "at": ts.isoformat() + "Z"
                    }
                    
                    # Also include policy adjustment suggestion
                    proposal = policies.propose_adjustment(current_satvb, trail_avg, spike_config)
                    spike_payload["suggestion"] = proposal
                    
                    # Calculate cooldown in seconds (minutes * 60)
                    cooldown_secs = spike_config.get("cooldown_minutes", 20) * 60
                    
                    self.alert_manager.maybe_alert_spike(spike_payload, cooldown_secs)
                
                if dry_run:
                    time.sleep(poll_secs)
                    continue
                
            except KeyboardInterrupt:
                logger.info("Exiting.")
                sys.exit(0)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
            
            time.sleep(poll_secs)

