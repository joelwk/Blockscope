from bitcoinrpc.authproxy import AuthServiceProxy
import socket
import logging
import logging.handlers
from pathlib import Path

# Constants
# Note: Sensitive values should be set via environment variables
# RPC credentials can be set via FS_RPC_USER and FS_RPC_PASS
# SSH server can be set via FS_SSH_SERVER
import os

RPC_HOST = os.getenv("FS_RPC_HOST", "127.0.0.1")
RPC_PORT = int(os.getenv("FS_RPC_PORT", "8332"))
RPC_USER = os.getenv("FS_RPC_USER", "")
RPC_PASSWORD = os.getenv("FS_RPC_PASS", "")
SSH_SERVER = os.getenv("FS_SSH_SERVER", "")

# Setup logging for scripts
def _setup_script_logging():
    """Setup logging for scripts directory."""
    log_dir = Path("logs") / "scripts"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger("scripts.common_calls")
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # File handler
    log_file = log_dir / "common_calls.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10485760,  # 10MB
        backupCount=10,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger

logger = _setup_script_logging()

# SSH tunnel command (run this in a separate terminal before using the RPC connection):
# ssh -L 8332:127.0.0.1:8332 joel@10.0.0.251
# Or use: ./start_tunnel.sh

def check_tunnel_active() -> bool:
    """Check if SSH tunnel is active by attempting to connect to local port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((RPC_HOST, RPC_PORT))
        sock.close()
        return result == 0
    except Exception:
        return False

def create_rpc_connection() -> AuthServiceProxy:
    """Create and return an authenticated RPC connection to Bitcoin node."""
    if not RPC_USER or not RPC_PASSWORD:
        raise ValueError(
            "RPC credentials not set. Please set FS_RPC_USER and FS_RPC_PASS "
            "environment variables or update scripts/common_calls.py"
        )
    rpc_url = f"http://{RPC_USER}:{RPC_PASSWORD}@{RPC_HOST}:{RPC_PORT}"
    return AuthServiceProxy(rpc_url)


def print_node_info() -> None:
    """Print comprehensive Bitcoin node information."""
    # Check if SSH tunnel is active
    if not check_tunnel_active():
        warning_msg = "SSH tunnel is not active!"
        logger.warning(warning_msg)
        print("⚠️  SSH tunnel is not active!")
        if SSH_SERVER:
            logger.info(f"Please start the tunnel: ssh -L {RPC_PORT}:127.0.0.1:{RPC_PORT} {SSH_SERVER}")
            print(f"Please start the tunnel in a separate terminal:")
            print(f"  ssh -L {RPC_PORT}:127.0.0.1:{RPC_PORT} {SSH_SERVER}")
        else:
            print("Please configure FS_SSH_SERVER environment variable or set up your tunnel manually.")
        print(f"Or run: ./start_tunnel.sh")
        return
    
    try:
        logger.info("Connecting to Bitcoin node via RPC")
        rpc = create_rpc_connection()
        
        print("=" * 80)
        print("BITCOIN NODE INFORMATION")
        print("=" * 80)
        logger.info("Retrieving Bitcoin node information")
        
        # Blockchain Information
        print("\n--- BLOCKCHAIN INFO ---")
        blockchain_info = rpc.getblockchaininfo()
        chain = blockchain_info.get('chain', 'N/A')
        blocks = blockchain_info.get('blocks', 'N/A')
        logger.info(f"Chain: {chain}, Blocks: {blocks}")
        print(f"Chain: {chain}")
        print(f"Blocks: {blocks:,}")
        print(f"Headers: {blockchain_info.get('headers', 'N/A'):,}")
        print(f"Best Block Hash: {blockchain_info.get('bestblockhash', 'N/A')}")
        print(f"Difficulty: {blockchain_info.get('difficulty', 'N/A'):,.2f}")
        print(f"Verification Progress: {blockchain_info.get('verificationprogress', 0) * 100:.2f}%")
        print(f"Size on Disk: {blockchain_info.get('size_on_disk', 0) / (1024**3):.2f} GB")
        print(f"Pruned: {blockchain_info.get('pruned', False)}")
        if blockchain_info.get('pruned'):
            print(f"Prune Height: {blockchain_info.get('pruneheight', 'N/A'):,}")
        
        # Mempool Information
        print("\n--- MEMPOOL INFO ---")
        mempool_info = rpc.getmempoolinfo()
        mempool_size = mempool_info.get('size', 'N/A')
        logger.info(f"Mempool size: {mempool_size} transactions")
        print(f"Size: {mempool_size:,} transactions")
        print(f"Bytes: {mempool_info.get('bytes', 0) / (1024**2):.2f} MB")
        print(f"Usage: {mempool_info.get('usage', 0) / (1024**2):.2f} MB")
        print(f"Max Mempool: {mempool_info.get('maxmempool', 0) / (1024**2):.2f} MB")
        print(f"Mempool Min Fee: {mempool_info.get('mempoolminfee', 0):.8f} BTC/kB")
        
        # Network Information
        print("\n--- NETWORK INFO ---")
        network_info = rpc.getnetworkinfo()
        connections = network_info.get('connections', 'N/A')
        logger.info(f"Network connections: {connections}")
        print(f"Version: {network_info.get('version', 'N/A')}")
        print(f"Subversion: {network_info.get('subversion', 'N/A')}")
        print(f"Protocol Version: {network_info.get('protocolversion', 'N/A')}")
        print(f"Connections: {connections}")
        print(f"Network Active: {network_info.get('networkactive', False)}")
        print(f"Relay Fee: {network_info.get('relayfee', 0):.8f} BTC/kB")
        
        
        # Raw Mempool (first 10 transaction IDs)
        print("\n--- MEMPOOL TRANSACTIONS (First 10) ---")
        raw_mempool = rpc.getrawmempool()
        if raw_mempool:
            logger.debug(f"Found {len(raw_mempool)} transactions in mempool")
            for i, txid in enumerate(raw_mempool[:10], 1):
                print(f"{i}. {txid}")
            if len(raw_mempool) > 10:
                print(f"... and {len(raw_mempool) - 10} more transactions")
        else:
            logger.info("Mempool is empty")
            print("Mempool is empty")
        
        print("\n" + "=" * 80)
        logger.info("Node information retrieval completed successfully")
        
    except Exception as e:
        logger.error(f"Error connecting to Bitcoin node: {e}", exc_info=True)
        print(f"Error connecting to Bitcoin node: {e}")
        print("\nTroubleshooting:")
        print("1. SSH tunnel is active (check with: ./start_tunnel.sh or ./start_tunnel_bg.sh)")
        print("2. Bitcoin node is running on the remote server")
        print("3. RPC credentials are correct")


if __name__ == "__main__":
    print_node_info()
