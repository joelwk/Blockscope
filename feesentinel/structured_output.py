"""Structured output writer for Blockscope events and alerts.

This module provides a small abstraction for writing JSONL records that can
later be ingested into relational or analytical databases.
"""

from pathlib import Path
from typing import Dict, Optional
import json
from datetime import datetime

from .logging import get_logger

logger = get_logger(__name__)


DEFAULT_EVENTS_FILENAME = "events.jsonl"
DEFAULT_BLOCKS_FILENAME = "blocks.jsonl"
DEFAULT_FEE_ALERTS_FILENAME = "fee_alerts.jsonl"
DEFAULT_FEE_SNAPSHOTS_FILENAME = "fee_snapshots.jsonl"


class StructuredOutputWriter:
    """Write structured JSONL records for future database rollups.

    This writer focuses on four high-level record types:
    - events: blockchain events (treasury, ordinals, covenants, blocks, etc.)
    - blocks: per-block summaries and metrics
    - fee_alerts: fee bucket change and PSBT-related alerts
    - fee_snapshots: periodic fee snapshots with rolling statistics
    """

    def __init__(
        self,
        base_dir: str,
        events_filename: str = DEFAULT_EVENTS_FILENAME,
        blocks_filename: str = DEFAULT_BLOCKS_FILENAME,
        fee_alerts_filename: str = DEFAULT_FEE_ALERTS_FILENAME,
        fee_snapshots_filename: str = DEFAULT_FEE_SNAPSHOTS_FILENAME,
    ) -> None:
        self.base_path = Path(base_dir)
        self.base_path.mkdir(parents=True, exist_ok=True)

        self.events_path = self.base_path / events_filename
        self.blocks_path = self.base_path / blocks_filename
        self.fee_alerts_path = self.base_path / fee_alerts_filename
        self.fee_snapshots_path = self.base_path / fee_snapshots_filename

    def _append_line(self, path: Path, record: Dict) -> None:
        """Append a single JSON record to the given file as one line.

        The file is opened in append mode for simplicity; ingestion tools can
        treat this as a JSONL stream.
        """
        try:
            # Ensure a timestamp exists for downstream consumers
            if "timestamp" not in record and "ts" not in record:
                record["timestamp"] = datetime.utcnow().isoformat() + "Z"

            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:
            # Never crash the main loop due to structured output failures.
            logger.error("Failed to append structured record to %s: %s", path, exc, exc_info=True)

    def record_event(self, payload: Dict) -> None:
        """Record a blockchain event.

        The payload is expected to include at least a ``type`` field and any
        additional metadata added by the event emitter.
        """
        self._append_line(self.events_path, payload)

    def record_block_summary(self, payload: Dict) -> None:
        """Record a per-block summary.

        Typical fields include block height, hash, tx count, reorg flag, and
        metrics captured by the event watcher.
        """
        self._append_line(self.blocks_path, payload)

    def record_fee_alert(self, payload: Dict) -> None:
        """Record a fee bucket change or PSBT-related alert payload."""
        self._append_line(self.fee_alerts_path, payload)

    def record_fee_snapshot(self, payload: Dict) -> None:
        """Record a periodic fee snapshot with rolling statistics."""
        self._append_line(self.fee_snapshots_path, payload)
