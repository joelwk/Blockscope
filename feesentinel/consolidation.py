"""PSBT preparation for UTXO consolidation."""

import os
import time
from typing import Dict
from .rpc import RPCClient
from .constants import SATOSHIS_PER_BTC, SATVB_TO_BTCKVB_FACTOR, MAX_CONFIRMATIONS


class ConsolidationManager:
    """Manages UTXO consolidation PSBT preparation."""
    
    def __init__(
        self,
        rpc_client: RPCClient,
        target_address: str,
        min_utxo_sats: int,
        max_inputs: int,
        label: str
    ):
        """
        Initialize consolidation manager.
        
        Args:
            rpc_client: RPC client instance
            target_address: Target address for consolidation (empty to disable)
            min_utxo_sats: Minimum UTXO size in satoshis to include
            max_inputs: Maximum number of inputs per PSBT
            label: Label for consolidation transactions
        """
        self.rpc_client = rpc_client
        self.target_address = target_address
        self.min_utxo_sats = min_utxo_sats
        self.max_inputs = max_inputs
        self.label = label
    
    def prepare_psbt(self, target_satvb: int) -> Dict:
        """
        Create a PSBT that sweeps small UTXOs to target address (without broadcasting).
        
        Args:
            target_satvb: Target fee rate in sat/vB
        
        Returns:
            Dictionary with status, inputs count, psbt_path, and target_satvb
        """
        if not self.target_address:
            return {"status": "skipped", "reason": "no target address configured"}
        
        # List unspent, pick small ones first
        utxos = self.rpc_client.call(
            "listunspent",
            0,
            MAX_CONFIRMATIONS,
            [],
            True,
            {"minimumAmount": self.min_utxo_sats / SATOSHIS_PER_BTC}
        )
        
        utxos.sort(key=lambda u: int(round(u["amount"] * SATOSHIS_PER_BTC)))  # ascending
        
        inputs = []
        total_in = 0
        for utxo in utxos:
            if len(inputs) >= self.max_inputs:
                break
            amt = int(round(utxo["amount"] * 1e8))
            inputs.append({"txid": utxo["txid"], "vout": utxo["vout"]})
            total_in += amt
        
        if not inputs:
            return {"status": "skipped", "reason": "no utxos matched"}
        
        # Set feerate in BTC/kvB; convert from sat/vB using conversion factor
        feerate_btckvb = target_satvb * SATVB_TO_BTCKVB_FACTOR
        outputs = [{self.target_address: total_in / SATOSHIS_PER_BTC}]  # raw; wallet will subtract fee
        opts = {
            "subtractFeeFromOutputs": [0],
            "replaceable": False,
            "fee_rate": feerate_btckvb
        }
        
        psbt_result = self.rpc_client.call(
            "walletcreatefundedpsbt",
            inputs,
            outputs,
            0,
            opts,
            True
        )
        psbt = psbt_result["psbt"]
        
        # Save to file for manual review/sign/broadcast later
        outpath = os.path.abspath(
            f"consolidate_{int(time.time())}_{target_satvb}satvb.psbt"
        )
        with open(outpath, "w") as f:
            f.write(psbt)
        
        return {
            "status": "ok",
            "inputs": len(inputs),
            "psbt_path": outpath,
            "target_satvb": target_satvb
        }

