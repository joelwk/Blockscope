"""State management for event monitoring - handles idempotency and reorg safety."""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime
from .logging import get_logger

logger = get_logger(__name__)


class StateManager:
    """Manages persistent state for event monitoring (idempotency, reorg handling)."""

    def __init__(self, backend: str = "sqlite", db_path: str = None, json_path: str = None):
        """
        Initialize state manager.

        Args:
            backend: "sqlite" or "json"
            db_path: Path to SQLite database (for sqlite backend)
            json_path: Path to JSON file (for json backend)
        """
        self.backend = backend
        self.db_path = db_path or "state/eventwatcher.db"
        self.json_path = json_path or "state/eventwatcher.json"
        
        if backend == "sqlite":
            self._init_sqlite()
        elif backend == "json":
            self._init_json()
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def _init_sqlite(self):
        """Initialize SQLite database."""
        db_path = Path(self.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        # Create tables
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                height INTEGER PRIMARY KEY,
                hash TEXT NOT NULL,
                processed_at TEXT NOT NULL,
                UNIQUE(height, hash)
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                txid TEXT PRIMARY KEY,
                block_height INTEGER NOT NULL,
                block_hash TEXT NOT NULL,
                processed_at TEXT NOT NULL,
                event_type TEXT,
                FOREIGN KEY (block_height, block_hash) REFERENCES blocks(height, hash)
            )
        """)
        
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tx_block ON transactions(block_height, block_hash)
        """)
        
        self.conn.commit()
        logger.info(f"Initialized SQLite state database: {self.db_path}")

    def _init_json(self):
        """Initialize JSON state file."""
        json_path = Path(self.json_path)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        
        if json_path.exists():
            with open(json_path, 'r') as f:
                self.state = json.load(f)
        else:
            self.state = {
                "blocks": {},
                "transactions": {},
                "last_height": None
            }
            self._save_json()
        
        logger.info(f"Initialized JSON state file: {self.json_path}")

    def _save_json(self):
        """Save JSON state to file."""
        json_path = Path(self.json_path)
        with open(json_path, 'w') as f:
            json.dump(self.state, f, indent=2)

    def get_last_height(self) -> Optional[int]:
        """Get the last processed block height."""
        if self.backend == "sqlite":
            row = self.conn.execute("SELECT MAX(height) as max_height FROM blocks").fetchone()
            return row["max_height"] if row and row["max_height"] is not None else None
        else:
            return self.state.get("last_height")

    def mark_block_processed(self, height: int, block_hash: str):
        """
        Mark a block as processed.

        Args:
            height: Block height
            block_hash: Block hash
        """
        processed_at = datetime.utcnow().isoformat() + "Z"
        
        if self.backend == "sqlite":
            self.conn.execute("""
                INSERT OR REPLACE INTO blocks (height, hash, processed_at)
                VALUES (?, ?, ?)
            """, (height, block_hash, processed_at))
            self.conn.commit()
        else:
            self.state["blocks"][str(height)] = {
                "hash": block_hash,
                "processed_at": processed_at
            }
            self.state["last_height"] = height
            self._save_json()
        
        logger.debug(f"Marked block {height} ({block_hash[:16]}...) as processed")

    def is_transaction_processed(self, txid: str) -> bool:
        """
        Check if a transaction has been processed.

        Args:
            txid: Transaction ID

        Returns:
            True if transaction was already processed
        """
        if self.backend == "sqlite":
            row = self.conn.execute(
                "SELECT 1 FROM transactions WHERE txid = ?",
                (txid,)
            ).fetchone()
            return row is not None
        else:
            return txid in self.state["transactions"]

    def mark_transaction_processed(self, txid: str, block_height: int, block_hash: str, event_type: str = None):
        """
        Mark a transaction as processed.

        Args:
            txid: Transaction ID
            block_height: Block height where transaction was included
            block_hash: Block hash
            event_type: Type of event emitted (optional)
        """
        processed_at = datetime.utcnow().isoformat() + "Z"
        
        if self.backend == "sqlite":
            self.conn.execute("""
                INSERT OR REPLACE INTO transactions 
                (txid, block_height, block_hash, processed_at, event_type)
                VALUES (?, ?, ?, ?, ?)
            """, (txid, block_height, block_hash, processed_at, event_type))
            self.conn.commit()
        else:
            self.state["transactions"][txid] = {
                "block_height": block_height,
                "block_hash": block_hash,
                "processed_at": processed_at,
                "event_type": event_type
            }
            self._save_json()
        
        logger.debug(f"Marked transaction {txid[:16]}... as processed")

    def get_block_hash(self, height: int) -> Optional[str]:
        """
        Get the stored hash for a block height.

        Args:
            height: Block height

        Returns:
            Block hash if found, None otherwise
        """
        if self.backend == "sqlite":
            row = self.conn.execute(
                "SELECT hash FROM blocks WHERE height = ?",
                (height,)
            ).fetchone()
            return row["hash"] if row else None
        else:
            block_data = self.state["blocks"].get(str(height))
            return block_data["hash"] if block_data else None

    def detect_reorg(self, height: int, current_hash: str) -> bool:
        """
        Detect if a reorg occurred at a given height.

        Args:
            height: Block height to check
            current_hash: Current block hash at that height

        Returns:
            True if reorg detected (hash mismatch)
        """
        stored_hash = self.get_block_hash(height)
        if stored_hash is None:
            return False  # Not processed yet
        
        if stored_hash != current_hash:
            logger.warning(
                f"Reorg detected at height {height}: "
                f"stored={stored_hash[:16]}..., current={current_hash[:16]}..."
            )
            return True
        
        return False

    def rollback_from_height(self, from_height: int):
        """
        Rollback state from a given height onwards.

        Args:
            from_height: Block height to rollback from (inclusive)
        """
        logger.info(f"Rolling back state from height {from_height}")
        
        if self.backend == "sqlite":
            # Delete transactions from reorged blocks
            self.conn.execute("""
                DELETE FROM transactions 
                WHERE block_height >= ?
            """, (from_height,))
            
            # Delete blocks from reorged height
            self.conn.execute("""
                DELETE FROM blocks 
                WHERE height >= ?
            """, (from_height,))
            
            self.conn.commit()
        else:
            # Remove blocks and transactions
            heights_to_remove = [
                h for h in self.state["blocks"].keys()
                if int(h) >= from_height
            ]
            for h in heights_to_remove:
                block_data = self.state["blocks"].pop(h)
                block_hash = block_data["hash"]
                
                # Remove transactions from this block
                txids_to_remove = [
                    txid for txid, tx_data in self.state["transactions"].items()
                    if tx_data["block_hash"] == block_hash
                ]
                for txid in txids_to_remove:
                    self.state["transactions"].pop(txid)
            
            # Update last height
            remaining_heights = [
                int(h) for h in self.state["blocks"].keys()
            ]
            self.state["last_height"] = max(remaining_heights) if remaining_heights else None
            self._save_json()
        
        logger.info(f"Rollback complete, removed blocks from height {from_height}")

    def get_processed_transactions(self, block_height: int, block_hash: str) -> List[str]:
        """
        Get list of processed transaction IDs for a block.

        Args:
            block_height: Block height
            block_hash: Block hash

        Returns:
            List of transaction IDs
        """
        if self.backend == "sqlite":
            rows = self.conn.execute("""
                SELECT txid FROM transactions 
                WHERE block_height = ? AND block_hash = ?
            """, (block_height, block_hash)).fetchall()
            return [row["txid"] for row in rows]
        else:
            return [
                txid for txid, tx_data in self.state["transactions"].items()
                if tx_data["block_height"] == block_height and tx_data["block_hash"] == block_hash
            ]

    def close(self):
        """Close connections and cleanup."""
        if self.backend == "sqlite" and hasattr(self, 'conn'):
            self.conn.close()
            logger.debug("Closed SQLite connection")

