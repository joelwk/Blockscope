"""Main event monitoring runner - orchestrates block monitoring, filtering, and event emission."""

import sys
import time
import requests
from typing import Dict, Optional
from datetime import datetime
from .rpc import RPCClient
from .block_monitor import BlockMonitor
from .transaction_filter import TransactionFilter
from .event_emitter import EventEmitter
from .state_manager import StateManager
from .treasury_registry import load_treasury_registry
from .config import Config
from .logging import get_logger
from .structured_output import StructuredOutputWriter

logger = get_logger(__name__)


class EventWatcherRunner:
    """Main runner for event monitoring service."""

    def __init__(self, config: Config, structured_writer: Optional[StructuredOutputWriter] = None):
        """
        Initialize event monitoring runner.

        Args:
            config: Configuration instance
        """
        self.config = config
        self._structured_writer = structured_writer
        
        # Initialize RPC client
        self.rpc_client = RPCClient(
            config.rpc_url,
            config.rpc_user,
            config.rpc_password
        )
        
        # Initialize state manager
        event_config = config.event_watcher_config
        self.state_manager = StateManager(
            backend=event_config.get("state_backend", "sqlite"),
            db_path=event_config.get("state_db_path"),
            json_path=event_config.get("state_json_path")
        )
        
        # Initialize block monitor
        self.block_monitor = BlockMonitor(
            self.rpc_client,
            self.state_manager,
            max_reorg_depth=event_config.get("max_reorg_depth", 6)
        )
        
        # Initialize transaction filter
        filters_config = event_config.get("filters", {})
        treasury_config = filters_config.get("treasury", {})
        ordinals_config = filters_config.get("ordinals", {})
        covenants_config = filters_config.get("covenants", {})
        
        # Load treasury registry if treasury filter is enabled
        treasury_registry = None
        treasury_addresses = []
        if treasury_config.get("enabled", False):
            treasury_registry = load_treasury_registry(treasury_config)
            treasury_addresses = treasury_config.get("addresses", [])
        
        # Get ordinal hotspots
        ordinal_hotspots = []
        if ordinals_config.get("enabled", False):
            ordinal_hotspots = ordinals_config.get("hotspots", [])
        
        self.transaction_filter = TransactionFilter(
            self.rpc_client,
            treasury_addresses=treasury_addresses,
            treasury_registry=treasury_registry,
            watch_inputs=treasury_config.get("watch_inputs", True),
            watch_outputs=treasury_config.get("watch_outputs", True),
            detect_ordinals=ordinals_config.get("enabled", False) and ordinals_config.get("detect_inscriptions", True),
            ordinal_hotspots=ordinal_hotspots,
            detect_covenants=covenants_config.get("enabled", False),
            covenant_patterns=covenants_config.get("patterns", [])
        )
        
        # Initialize event emitter
        events_config = event_config.get("events", {})
        webhook_urls = []
        if events_config.get("webhook_url"):
            webhook_urls.append(events_config["webhook_url"])
        webhook_urls.extend(events_config.get("webhook_urls", []))
        
        self.event_emitter = EventEmitter(
            webhook_urls=webhook_urls,
            retry_attempts=events_config.get("retry_attempts", 3),
            retry_backoff_secs=events_config.get("retry_backoff_secs", 5),
            structured_writer=self._structured_writer,
        )
        
        # Metrics
        self.metrics = {
            "blocks_processed": 0,
            "transactions_filtered": 0,
            "events_emitted": 0,
            "reorgs_detected": 0,
            "treasury_matches": 0,
            "ordinal_matches": 0,
            "covenant_matches": 0
        }
        
        logger.info("Event monitoring runner initialized")

    def process_block(self, height: int, block_hash: str, reorg: bool = False):
        """
        Process a single block.

        Args:
            height: Block height
            block_hash: Block hash
            reorg: Whether this is a reorg recovery
        """
        logger.info(f"Processing block {height} ({block_hash[:16]}...)")
        
        # Get block info
        block_info = self.block_monitor.process_block(height, block_hash)
        txids = block_info.get("tx", [])
        
        # Emit block event
        self.event_emitter.emit_block_event(
            height, block_hash, len(txids), reorg=reorg
        )
        
        # Process transactions
        events_emitted = 0
        for txid in txids:
            # Check if already processed (idempotency)
            if self.state_manager.is_transaction_processed(txid):
                logger.debug(f"Transaction {txid[:16]}... already processed, skipping")
                continue
            
            # Filter transaction (pass block_hash for transactions already in blocks)
            filter_result = self.transaction_filter.filter_transaction(txid, block_hash)
            self.metrics["transactions_filtered"] += 1
            
            if not filter_result["matched"]:
                # Mark as processed even if no match (for idempotency)
                self.state_manager.mark_transaction_processed(
                    txid, height, block_hash, event_type=None
                )
                continue
            
            # Emit events based on matches
            event_type = None
            
            if filter_result["treasury"]["matched"]:
                self.event_emitter.emit_treasury_event(
                    filter_result["treasury"], txid, height
                )
                self.metrics["treasury_matches"] += 1
                event_type = "treasury"
                events_emitted += 1
            
            if filter_result["ordinal"]["matched"]:
                self.event_emitter.emit_ordinal_event(
                    filter_result["ordinal"], txid, height
                )
                self.metrics["ordinal_matches"] += 1
                if not event_type:
                    event_type = "ordinal"
                events_emitted += 1
            
            if filter_result["covenant"]["matched"]:
                self.event_emitter.emit_covenant_event(
                    filter_result["covenant"], txid, height
                )
                self.metrics["covenant_matches"] += 1
                if not event_type:
                    event_type = "covenant"
                events_emitted += 1
            
            # Mark transaction as processed
            self.state_manager.mark_transaction_processed(
                txid, height, block_hash, event_type=event_type
            )
        
        self.metrics["blocks_processed"] += 1
        self.metrics["events_emitted"] += events_emitted

        if reorg:
            self.metrics["reorgs_detected"] += 1

        logger.info(
            f"Block {height} processed: {len(txids)} transactions, "
            f"{events_emitted} events emitted"
        )

        # Optionally record a structured per-block summary for future rollups
        if self._structured_writer is not None:
            block_summary = {
                "type": "block_summary",
                "height": height,
                "block_hash": block_hash,
                "reorg": reorg,
                "tx_count": len(txids),
                "events_emitted": events_emitted,
                "metrics": self.metrics.copy(),
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            self._structured_writer.record_block_summary(block_summary)

    def run_once(self) -> Dict:
        """
        Run one iteration of event monitoring.

        Returns:
            Dictionary with processing results
        """
        height, block_hash, reorg = self.block_monitor.get_new_blocks()
        
        if height is None:
            return {
                "processed": False,
                "height": None,
                "metrics": self.metrics.copy()
            }
        
        self.process_block(height, block_hash, reorg=reorg)
        
        return {
            "processed": True,
            "height": height,
            "block_hash": block_hash,
            "reorg": reorg,
            "metrics": self.metrics.copy()
        }

    def run_continuous(self, poll_interval_secs: int):
        """
        Run continuous event monitoring loop.

        Args:
            poll_interval_secs: Seconds between block checks
        """
        logger.info(f"Starting continuous event monitoring (poll interval: {poll_interval_secs}s)")
        
        event_config = self.config.event_watcher_config
        metrics_config = event_config.get("metrics", {})
        log_interval_secs = metrics_config.get("log_interval_secs", 300)
        last_metrics_log = datetime.utcnow()
        
        # Connection error retry settings
        connection_retry_delay = 10  # seconds
        
        while True:
            try:
                result = self.run_once()
                
                # Log metrics periodically
                now = datetime.utcnow()
                if (now - last_metrics_log).total_seconds() >= log_interval_secs:
                    self._log_metrics()
                    last_metrics_log = now
                
                if not result["processed"]:
                    time.sleep(poll_interval_secs)
                    continue
                
            except KeyboardInterrupt:
                logger.info("Exiting event monitoring")
                self.state_manager.close()
                sys.exit(0)
            except (requests.exceptions.ConnectionError, requests.exceptions.RequestException) as e:
                logger.warning(
                    f"Connection error (RPC endpoint may not be ready): {e}. "
                    f"Retrying in {connection_retry_delay}s..."
                )
                time.sleep(connection_retry_delay)
            except Exception as e:
                logger.error(f"Error in event monitoring loop: {e}", exc_info=True)
                time.sleep(poll_interval_secs)

    def _log_metrics(self):
        """Log current metrics."""
        logger.info(
            f"Metrics: blocks={self.metrics['blocks_processed']}, "
            f"tx_filtered={self.metrics['transactions_filtered']}, "
            f"events={self.metrics['events_emitted']}, "
            f"reorgs={self.metrics['reorgs_detected']}, "
            f"treasury={self.metrics['treasury_matches']}, "
            f"ordinals={self.metrics['ordinal_matches']}, "
            f"covenants={self.metrics['covenant_matches']}"
        )

    def close(self):
        """Close connections and cleanup."""
        self.state_manager.close()
        logger.info("Event monitoring runner closed")

