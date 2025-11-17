"""Tests for fee percentile calculations."""

from unittest.mock import Mock
from feesentinel.fees import current_fee_percentiles
from feesentinel.rpc import RPCClient


def test_fee_percentiles_empty_mempool():
    """Test fee calculation with empty mempool."""
    rpc_client = Mock(spec=RPCClient)
    rpc_client.call.side_effect = [
        {},  # getrawmempool returns empty
        {"mempoolminfee": 0.00001}  # getmempoolinfo returns minfee in BTC/kB
    ]
    
    result = current_fee_percentiles(rpc_client)
    
    # mempoolminfee: 0.00001 BTC/kB = 0.00001 * 1e8 / 1000 = 1 sat/vB
    assert result["p50"] == 1
    assert result["p25"] == 1
    assert result["p75"] == 1
    assert result["tx_count"] == 0


def test_fee_percentiles_with_transactions():
    """Test fee calculation with sample transactions."""
    rpc_client = Mock(spec=RPCClient)
    rpc_client.call.return_value = {
        "tx1": {"fee": 0.00001, "vsize": 250},  # 4 sat/vB
        "tx2": {"fee": 0.00002, "vsize": 250},  # 8 sat/vB
        "tx3": {"fee": 0.00003, "vsize": 250},  # 12 sat/vB
        "tx4": {"fee": 0.00004, "vsize": 250},  # 16 sat/vB
        "tx5": {"fee": 0.00005, "vsize": 250},  # 20 sat/vB
    }
    
    result = current_fee_percentiles(rpc_client)
    
    assert result["tx_count"] == 5
    assert result["p50"] == 12  # Median of [4, 8, 12, 16, 20]
    assert result["p25"] == 8
    assert result["p75"] == 16

