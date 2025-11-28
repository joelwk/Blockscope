"""Block monitoring and reorg detection for event monitoring."""

from typing import Dict, Optional, Tuple
from .rpc import RPCClient, PrunedBlockError
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
            
        Raises:
            PrunedBlockError: If block is pruned and not available
        """
        return self.rpc_client.call("getblock", block_hash, 1)  # verbosity=1 for JSON
    
    def find_earliest_available_block(self, start_height: int, max_search_depth: int = 1000) -> Optional[int]:
        """
        Find the earliest available block height starting from a given height.
        Used when encountering pruned blocks - searches backwards to find first available block.
        
        Args:
            start_height: Height to start searching from
            max_search_depth: Maximum number of blocks to search backwards
            
        Returns:
            Earliest available block height, or None if not found within search depth
        """
        current_height = self.get_current_height()
        search_start = min(start_height, current_height)
        search_end = max(0, search_start - max_search_depth)
        
        logger.info(
            f"Searching for earliest available block from height {search_start} "
            f"(searching back to {search_end})"
        )
        
        for height in range(search_start, search_end - 1, -1):
            try:
                block_hash = self.get_block_hash(height)
                # Try to get block info to verify it's available
                self.get_block_info(block_hash)
                logger.info(f"Found earliest available block at height {height}")
                return height
            except PrunedBlockError:
                continue
            except Exception as e:
                logger.warning(f"Error checking block {height}: {e}, continuing search")
                continue
        
        logger.warning(f"Could not find available block within search depth {max_search_depth}")
        return None

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
                try:
                    current_hash = self.get_block_hash(height)
                    if stored_hash != current_hash:
                        reorg_detected = True
                        if reorg_start_height is None:
                            reorg_start_height = height
                        logger.warning(
                            f"Reorg detected: height {height} hash mismatch "
                            f"(stored: {stored_hash[:16]}..., current: {current_hash[:16]}...)"
                        )
                except PrunedBlockError:
                    # Block is pruned, can't verify reorg - reset to current height
                    logger.warning(
                        f"Stored block {height} is pruned, cannot verify reorg. "
                        f"Resetting state to current height {current_height}"
                    )
                    # Clear state and start from current height
                    self.state_manager.rollback_from_height(0)  # Clear all blocks
                    return current_height, self.get_block_hash(current_height), False
        
        # Handle reorg
        if reorg_detected and reorg_start_height is not None:
            logger.info(f"Rolling back state from height {reorg_start_height}")
            self.state_manager.rollback_from_height(reorg_start_height)
            # Return the reorg start height as the next block to process
            try:
                return reorg_start_height, self.get_block_hash(reorg_start_height), True
            except PrunedBlockError:
                # Reorg start block is pruned, find earliest available and reset
                logger.warning(
                    f"Reorg start block {reorg_start_height} is pruned. "
                    f"Finding earliest available block..."
                )
                earliest = self.find_earliest_available_block(reorg_start_height)
                if earliest is not None:
                    self.state_manager.rollback_from_height(earliest)
                    return earliest, self.get_block_hash(earliest), True
                else:
                    # Can't find available block, reset to current
                    logger.warning("Could not find available block, resetting to current height")
                    self.state_manager.rollback_from_height(0)
                    return current_height, self.get_block_hash(current_height), False
        
        # No reorg, return next block
        next_height = last_height + 1
        if next_height <= current_height:
            try:
                return next_height, self.get_block_hash(next_height), False
            except PrunedBlockError:
                # Next block is pruned, find earliest available
                logger.warning(
                    f"Next block {next_height} is pruned. Finding earliest available block..."
                )
                earliest = self.find_earliest_available_block(next_height)
                if earliest is not None:
                    # Reset state to earliest available block
                    self.state_manager.rollback_from_height(earliest)
                    return earliest, self.get_block_hash(earliest), False
                else:
                    # Can't find available block, reset to current
                    logger.warning("Could not find available block, resetting to current height")
                    self.state_manager.rollback_from_height(0)
                    return current_height, self.get_block_hash(current_height), False
        
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
            
        Raises:
            PrunedBlockError: If block is pruned and not available
        """
        block_info = self.get_block_info(block_hash)
        self.state_manager.mark_block_processed(height, block_hash)
        
        logger.info(
            f"Processed block {height} ({block_hash[:16]}...): "
            f"{len(block_info.get('tx', []))} transactions"
        )
        
        return block_info

