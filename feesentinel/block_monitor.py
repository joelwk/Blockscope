"""Block monitoring and reorg detection for event monitoring."""

from typing import Dict, Optional, Tuple
from .rpc import RPCClient
from .state_manager import StateManager
from .logging import get_logger

logger = get_logger(__name__)


class BlockMonitor:
    """Monitors Bitcoin blocks and detects reorganizations."""

    def __init__(self, rpc_client: RPCClient, state_manager: StateManager, max_reorg_depth: int = 6):
        """
        Initialize block monitor.

        Args:
            rpc_client: RPC client instance
            state_manager: State manager instance
            max_reorg_depth: Maximum reorg depth to handle
        """
        self.rpc_client = rpc_client
        self.state_manager = state_manager
        self.max_reorg_depth = max_reorg_depth

    def get_current_height(self) -> int:
        """
        Get current blockchain height.

        Returns:
            Current block height
        """
        return self.rpc_client.call("getblockcount")

    def get_block_hash(self, height: int) -> str:
        """
        Get block hash for a given height.

        Args:
            height: Block height

        Returns:
            Block hash
        """
        return self.rpc_client.call("getblockhash", height)

    def get_block_info(self, block_hash: str) -> Dict:
        """
        Get block information.

        Args:
            block_hash: Block hash

        Returns:
            Block information dictionary
        """
        return self.rpc_client.call("getblock", block_hash, 1)  # verbosity=1 for JSON

    def get_new_blocks(self) -> Tuple[Optional[int], Optional[str], bool]:
        """
        Get new blocks since last processed height.
        Also checks for reorgs.

        Returns:
            Tuple of (height, block_hash, reorg_detected)
            Returns (None, None, False) if no new blocks
        """
        current_height = self.get_current_height()
        last_height = self.state_manager.get_last_height()
        
        # If no previous height, start from current
        if last_height is None:
            logger.info(f"No previous height found, starting from current height {current_height}")
            return current_height, self.get_block_hash(current_height), False
        
        # Check for new blocks
        if current_height <= last_height:
            return None, None, False
        
        # Check for reorgs by verifying stored hashes match current chain
        reorg_detected = False
        reorg_start_height = None
        
        # Check last few blocks for reorgs (up to max_reorg_depth)
        check_start = max(last_height - self.max_reorg_depth + 1, 0)
        for height in range(check_start, last_height + 1):
            stored_hash = self.state_manager.get_block_hash(height)
            if stored_hash:
                current_hash = self.get_block_hash(height)
                if stored_hash != current_hash:
                    reorg_detected = True
                    if reorg_start_height is None:
                        reorg_start_height = height
                    logger.warning(
                        f"Reorg detected: height {height} hash mismatch "
                        f"(stored: {stored_hash[:16]}..., current: {current_hash[:16]}...)"
                    )
        
        # Handle reorg
        if reorg_detected and reorg_start_height is not None:
            logger.info(f"Rolling back state from height {reorg_start_height}")
            self.state_manager.rollback_from_height(reorg_start_height)
            # Return the reorg start height as the next block to process
            return reorg_start_height, self.get_block_hash(reorg_start_height), True
        
        # No reorg, return next block
        next_height = last_height + 1
        if next_height <= current_height:
            return next_height, self.get_block_hash(next_height), False
        
        return None, None, False

    def get_block_transactions(self, block_hash: str) -> list:
        """
        Get list of transaction IDs from a block.

        Args:
            block_hash: Block hash

        Returns:
            List of transaction IDs
        """
        block_info = self.get_block_info(block_hash)
        return block_info.get("tx", [])

    def process_block(self, height: int, block_hash: str) -> Dict:
        """
        Process a block and mark it as processed.

        Args:
            height: Block height
            block_hash: Block hash

        Returns:
            Block information dictionary
        """
        block_info = self.get_block_info(block_hash)
        self.state_manager.mark_block_processed(height, block_hash)
        
        logger.info(
            f"Processed block {height} ({block_hash[:16]}...): "
            f"{len(block_info.get('tx', []))} transactions"
        )
        
        return block_info

