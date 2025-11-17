"""Mempool fee percentile calculations."""

from typing import Dict
from .rpc import RPCClient
from .constants import SATOSHIS_PER_BTC, VB_PER_KB, WEIGHT_TO_VSIZE_RATIO, PERCENTILE_SCALE


def current_fee_percentiles(rpc_client: RPCClient) -> Dict[str, int]:
    """
    Compute sat/vB percentiles (p25, p50, p75, p90, p95) using getrawmempool(true).
    Fallback to getmempoolinfo.mempoolminfee if mempool is empty.
    
    Args:
        rpc_client: RPC client instance
    
    Returns:
        Dictionary with percentile keys (p25, p50, p75, p90, p95) and tx_count
    """
    txs = rpc_client.call("getrawmempool", True)  # dict: txid -> {fee, vsize, ...}
    
    if not txs:
        info = rpc_client.call("getmempoolinfo")
        # Convert BTC/kB to sat/vB: multiply by satoshis per BTC, divide by vB per kB
        minfee_satvb = int(round(info.get("mempoolminfee", 0) * SATOSHIS_PER_BTC / VB_PER_KB))
        return {
            "p25": minfee_satvb,
            "p50": minfee_satvb,
            "p75": minfee_satvb,
            "p90": minfee_satvb,
            "p95": minfee_satvb,
            "tx_count": 0
        }
    
    fees = []
    for tx_data in txs.values():
        # Determine virtual size
        vsize = tx_data.get("vsize")
        if vsize is None:
            weight = tx_data.get("weight")
            if weight is not None:
                vsize = max(1, int(round(weight / WEIGHT_TO_VSIZE_RATIO)))
            else:
                # Can't price without any notion of size
                continue
        else:
            vsize = max(1, int(vsize))

        # Determine fee in BTC
        fee_btc = tx_data.get("fee")
        if fee_btc is None:
            fees_obj = tx_data.get("fees")
            if isinstance(fees_obj, dict):
                fee_btc = fees_obj.get("base")

        if fee_btc is None:
            continue

        try:
            # Convert BTC fee to sat/vB: multiply by satoshis per BTC, divide by vsize
            fee_satvb = (float(fee_btc) * SATOSHIS_PER_BTC) / vsize
        except (ValueError, TypeError):
            continue

        fees.append(fee_satvb)
    
    fees.sort()
    
    def percentile(p: int) -> int:
        """Calculate percentile value. p in [0..100]"""
        if not fees:
            return 0
        idx = min(len(fees) - 1, max(0, int(round((p / PERCENTILE_SCALE) * (len(fees) - 1)))))
        return int(round(fees[idx]))
    
    return {
        "p25": percentile(25),
        "p50": percentile(50),
        "p75": percentile(75),
        "p90": percentile(90),
        "p95": percentile(95),
        "tx_count": len(fees),
    }

