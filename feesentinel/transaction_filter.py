"""Transaction filtering for treasury UTXOs, ordinals, and covenants."""

import re
from typing import Dict, List, Set, Optional
from .rpc import RPCClient
from .treasury_registry import TreasuryRegistry
from .logging import get_logger

logger = get_logger(__name__)


class TransactionFilter:
    """Filters transactions for treasury UTXOs, ordinals, and covenants."""

    def __init__(
        self,
        rpc_client: RPCClient,
        treasury_addresses: List[str] = None,
        treasury_registry: Optional[TreasuryRegistry] = None,
        watch_inputs: bool = True,
        watch_outputs: bool = True,
        detect_ordinals: bool = True,
        ordinal_hotspots: List[Dict] = None,
        detect_covenants: bool = False,
        covenant_patterns: List[str] = None
    ):
        """
        Initialize transaction filter.

        Args:
            rpc_client: RPC client instance
            treasury_addresses: List of addresses to watch (legacy/fallback)
            treasury_registry: TreasuryRegistry instance with metadata
            watch_inputs: Watch for spends from treasury addresses
            watch_outputs: Watch for receives to treasury addresses
            detect_ordinals: Enable ordinal/inscription detection
            ordinal_hotspots: List of hotspot configs {id, label, addresses}
            detect_covenants: Enable covenant detection
            covenant_patterns: List of covenant patterns to detect
        """
        self.rpc_client = rpc_client
        self.treasury_registry = treasury_registry
        
        # Build treasury_addresses set from registry or fallback to simple list
        if treasury_registry:
            self.treasury_addresses = treasury_registry.treasury_addresses
        else:
            self.treasury_addresses = set(treasury_addresses or [])
        
        self.watch_inputs = watch_inputs
        self.watch_outputs = watch_outputs
        self.detect_ordinals = detect_ordinals
        self.ordinal_hotspots = ordinal_hotspots or []
        self.hotspot_addresses = set()
        for hotspot in self.ordinal_hotspots:
            self.hotspot_addresses.update(hotspot.get("addresses", []))
        self.detect_covenants = detect_covenants
        self.covenant_patterns = covenant_patterns or []
        
        logger.info(
            f"Initialized transaction filter: "
            f"treasury_addresses={len(self.treasury_addresses)}, "
            f"ordinals={detect_ordinals}, hotspots={len(self.hotspot_addresses)}, "
            f"covenants={detect_covenants}"
        )

    def get_transaction(self, txid: str, block_hash: str = None) -> Optional[Dict]:
        """
        Get transaction details.

        Args:
            txid: Transaction ID
            block_hash: Block hash (required for transactions already in blocks)

        Returns:
            Transaction dictionary or None if not found
        """
        try:
            if block_hash:
                # For transactions in blocks, provide block hash to enable query
                return self.rpc_client.call("getrawtransaction", txid, True, block_hash)
            else:
                # Try mempool first, then fallback to block query
                return self.rpc_client.call("getrawtransaction", txid, True)
        except Exception as e:
            # If mempool query fails and we don't have block_hash, try without verbose
            if not block_hash:
                try:
                    return self.rpc_client.call("getrawtransaction", txid, False)
                except:
                    pass
            logger.debug(f"Failed to get transaction {txid[:16]}...: {e}")
            return None

    def get_txout(self, txid: str, vout: int) -> Optional[Dict]:
        """
        Get transaction output details.

        Args:
            txid: Transaction ID
            vout: Output index

        Returns:
            Output dictionary or None if spent/not found
        """
        try:
            return self.rpc_client.call("gettxout", txid, vout)
        except Exception as e:
            logger.debug(f"Failed to get txout {txid}:{vout}: {e}")
            return None

    def check_treasury_utxo(self, tx: Dict) -> Dict:
        """
        Check if transaction touches treasury addresses.

        Args:
            tx: Transaction dictionary

        Returns:
            Dictionary with enriched match information:
            {
                "matched": bool,
                "type": "spend" | "receive" | "both" | None,
                "addresses": List[str],  # Legacy: simple list
                "inputs": List[Dict],  # Legacy: basic input info
                "outputs": List[Dict],  # Legacy: basic output info
                "enriched_addresses": List[Dict],  # New: with category, entity, value
                "entities": List[Dict],  # New: aggregated per entity
                "summary": Dict  # New: per-category totals
            }
        """
        if not self.treasury_addresses:
            return {
                "matched": False,
                "type": None,
                "addresses": [],
                "inputs": [],
                "outputs": [],
                "enriched_addresses": [],
                "entities": [],
                "summary": {}
            }
        
        matched_inputs = []
        matched_outputs = []
        matched_addresses = set()
        enriched_addresses = []
        entity_stats = {}  # entity_id -> {in_sats, out_sats, directions}
        
        # Check inputs (spends)
        if self.watch_inputs and "vin" in tx:
            for vin in tx.get("vin", []):
                if "txid" in vin and "vout" in vin:
                    prev_tx = self.get_transaction(vin["txid"])
                    if prev_tx and "vout" in prev_tx:
                        prev_out = prev_tx["vout"][vin["vout"]]
                        if "scriptPubKey" in prev_out and "addresses" in prev_out["scriptPubKey"]:
                            addresses = prev_out["scriptPubKey"]["addresses"]
                            value_sats = int(prev_out.get("value", 0) * 100_000_000)  # Convert BTC to sats
                            for addr in addresses:
                                if addr in self.treasury_addresses:
                                    matched_inputs.append({
                                        "txid": vin["txid"],
                                        "vout": vin["vout"],
                                        "address": addr
                                    })
                                    matched_addresses.add(addr)
                                    
                                    # Enrich with metadata
                                    meta = None
                                    if self.treasury_registry:
                                        meta = self.treasury_registry.get_address_metadata(addr)
                                    
                                    enriched_addresses.append({
                                        "address": addr,
                                        "category": meta.category if meta else "unknown",
                                        "entity_id": meta.entity_id if meta else "unknown",
                                        "entity_label": meta.entity_label if meta else "Unknown",
                                        "direction": "input",
                                        "value_sats": value_sats
                                    })
                                    
                                    # Aggregate entity stats
                                    entity_id = meta.entity_id if meta else "unknown"
                                    if entity_id not in entity_stats:
                                        entity_stats[entity_id] = {
                                            "entity_id": entity_id,
                                            "entity_label": meta.entity_label if meta else "Unknown",
                                            "category": meta.category if meta else "unknown",
                                            "in_sats": 0,
                                            "out_sats": 0,
                                            "directions": set()
                                        }
                                    entity_stats[entity_id]["out_sats"] += value_sats
                                    entity_stats[entity_id]["directions"].add("spend")
        
        # Check outputs (receives)
        if self.watch_outputs and "vout" in tx:
            for vout_idx, vout in enumerate(tx.get("vout", [])):
                if "scriptPubKey" in vout and "addresses" in vout["scriptPubKey"]:
                    addresses = vout["scriptPubKey"]["addresses"]
                    value_sats = int(vout.get("value", 0) * 100_000_000)  # Convert BTC to sats
                    for addr in addresses:
                        if addr in self.treasury_addresses:
                            matched_outputs.append({
                                "vout": vout_idx,
                                "address": addr,
                                "value": vout.get("value", 0)
                            })
                            matched_addresses.add(addr)
                            
                            # Enrich with metadata
                            meta = None
                            if self.treasury_registry:
                                meta = self.treasury_registry.get_address_metadata(addr)
                            
                            enriched_addresses.append({
                                "address": addr,
                                "category": meta.category if meta else "unknown",
                                "entity_id": meta.entity_id if meta else "unknown",
                                "entity_label": meta.entity_label if meta else "Unknown",
                                "direction": "output",
                                "value_sats": value_sats
                            })
                            
                            # Aggregate entity stats
                            entity_id = meta.entity_id if meta else "unknown"
                            if entity_id not in entity_stats:
                                entity_stats[entity_id] = {
                                    "entity_id": entity_id,
                                    "entity_label": meta.entity_label if meta else "Unknown",
                                    "category": meta.category if meta else "unknown",
                                    "in_sats": 0,
                                    "out_sats": 0,
                                    "directions": set()
                                }
                            entity_stats[entity_id]["in_sats"] += value_sats
                            entity_stats[entity_id]["directions"].add("receive")
        
        matched = len(matched_inputs) > 0 or len(matched_outputs) > 0
        
        event_type = None
        if matched:
            if matched_inputs and matched_outputs:
                event_type = "both"
            elif matched_inputs:
                event_type = "spend"
            elif matched_outputs:
                event_type = "receive"
        
        # Build entities list (convert sets to lists for JSON serialization)
        entities = []
        for entity_id, stats in entity_stats.items():
            entities.append({
                "entity_id": stats["entity_id"],
                "entity_label": stats["entity_label"],
                "category": stats["category"],
                "directions": list(stats["directions"]),
                "in_sats": stats["in_sats"],
                "out_sats": stats["out_sats"]
            })
        
        # Build summary by category
        summary = {}
        for entity in entities:
            category = entity["category"]
            if category not in summary:
                summary[category] = {
                    "in_sats": 0,
                    "out_sats": 0,
                    "entity_count": 0
                }
            summary[category]["in_sats"] += entity["in_sats"]
            summary[category]["out_sats"] += entity["out_sats"]
            summary[category]["entity_count"] += 1
        
        return {
            "matched": matched,
            "type": event_type,
            "addresses": list(matched_addresses),  # Legacy compatibility
            "inputs": matched_inputs,  # Legacy compatibility
            "outputs": matched_outputs,  # Legacy compatibility
            "enriched_addresses": enriched_addresses,
            "entities": entities,
            "summary": summary
        }

    def check_ordinal(self, tx: Dict) -> Dict:
        """
        Check if transaction contains an ordinal inscription.

        Ordinals are typically identified by:
        - OP_FALSE OP_IF ... OP_ENDIF pattern in scriptSig or witness
        - Envelope pattern: OP_FALSE OP_IF "ord" OP_1 <data> OP_ENDIF

        Args:
            tx: Transaction dictionary

        Returns:
            Dictionary with match information:
            {
                "matched": bool,
                "inscriptions": List[Dict],
                "hotspots": List[Dict]  # New: matched hotspots
            }
        """
        if not self.detect_ordinals:
            return {"matched": False, "inscriptions": [], "hotspots": []}
        
        inscriptions = []
        matched_hotspots = []
        
        # Check witness data (SegWit)
        if "vin" in tx:
            for vin_idx, vin in enumerate(tx.get("vin", [])):
                if "txinwitness" in vin:
                    witness = vin["txinwitness"]
                    # Look for ordinal envelope pattern in witness
                    if len(witness) >= 3:
                        # Pattern: OP_FALSE OP_IF "ord" OP_1 <data> OP_ENDIF
                        # In witness stack, this appears as strings
                        for i in range(len(witness) - 2):
                            if witness[i] == "" and witness[i+1].startswith("ord"):
                                inscriptions.append({
                                    "input_index": vin_idx,
                                    "type": "witness",
                                    "pattern": witness[i+1]
                                })
                                break
        
        # Check scriptSig (legacy)
        if "vin" in tx:
            for vin_idx, vin in enumerate(tx.get("vin", [])):
                if "scriptSig" in vin and "hex" in vin["scriptSig"]:
                    script_hex = vin["scriptSig"]["hex"]
                    # Simple check for OP_FALSE OP_IF pattern
                    # OP_FALSE = 0x00, OP_IF = 0x63
                    if "0063" in script_hex.lower():
                        inscriptions.append({
                            "input_index": vin_idx,
                            "type": "scriptSig",
                            "script_hex": script_hex[:100]  # First 100 chars
                        })
        
        # Check for hotspot matches
        if self.hotspot_addresses and inscriptions:
            # Check inputs
            if "vin" in tx:
                for vin in tx.get("vin", []):
                    if "txid" in vin and "vout" in vin:
                        prev_tx = self.get_transaction(vin["txid"])
                        if prev_tx and "vout" in prev_tx:
                            prev_out = prev_tx["vout"][vin["vout"]]
                            if "scriptPubKey" in prev_out and "addresses" in prev_out["scriptPubKey"]:
                                addresses = prev_out["scriptPubKey"]["addresses"]
                                for addr in addresses:
                                    if addr in self.hotspot_addresses:
                                        # Find matching hotspot config
                                        for hotspot in self.ordinal_hotspots:
                                            if addr in hotspot.get("addresses", []):
                                                matched_hotspots.append({
                                                    "id": hotspot.get("id", ""),
                                                    "label": hotspot.get("label", ""),
                                                    "address": addr,
                                                    "side": "input"
                                                })
                                                break
            
            # Check outputs
            if "vout" in tx:
                for vout_idx, vout in enumerate(tx.get("vout", [])):
                    if "scriptPubKey" in vout and "addresses" in vout["scriptPubKey"]:
                        addresses = vout["scriptPubKey"]["addresses"]
                        for addr in addresses:
                            if addr in self.hotspot_addresses:
                                # Find matching hotspot config
                                for hotspot in self.ordinal_hotspots:
                                    if addr in hotspot.get("addresses", []):
                                        matched_hotspots.append({
                                            "id": hotspot.get("id", ""),
                                            "label": hotspot.get("label", ""),
                                            "address": addr,
                                            "side": "output"
                                        })
                                        break
        
        matched = len(inscriptions) > 0
        
        return {
            "matched": matched,
            "inscriptions": inscriptions,
            "hotspots": matched_hotspots
        }

    def check_covenant(self, tx: Dict) -> Dict:
        """
        Check if transaction contains covenant patterns.

        Common covenant patterns:
        - OP_CHECKTEMPLATEVERIFY (OP_CTV)
        - Other covenant opcodes

        Args:
            tx: Transaction dictionary

        Returns:
            Dictionary with match information:
            {
                "matched": bool,
                "patterns": List[str]
            }
        """
        if not self.detect_covenants:
            return {"matched": False, "patterns": []}
        
        matched_patterns = []
        
        # Check outputs for covenant patterns
        if "vout" in tx:
            for vout in tx.get("vout", []):
                if "scriptPubKey" in vout and "hex" in vout["scriptPubKey"]:
                    script_hex = vout["scriptPubKey"]["hex"].lower()
                    
                    # OP_CHECKTEMPLATEVERIFY = 0xb3 (179)
                    # Check for "b3" as a standalone byte at byte boundaries
                    # In hex strings, bytes are pairs of hex digits (e.g., "b3" = byte 0xb3)
                    # We check if "b3" appears at even positions (0, 2, 4, 6...) which are byte boundaries
                    # Note: This is a heuristic - proper detection would require script parsing
                    for i in range(0, len(script_hex) - 1, 2):  # Step by 2 (byte boundaries)
                        if script_hex[i:i+2] == "b3":
                            matched_patterns.append("OP_CHECKTEMPLATEVERIFY")
                            break  # Only need to find it once per output
                    
                    # Check for custom patterns
                    for pattern in self.covenant_patterns:
                        if pattern.lower() in script_hex:
                            matched_patterns.append(pattern)
        
        matched = len(matched_patterns) > 0
        
        return {
            "matched": matched,
            "patterns": matched_patterns
        }

    def filter_transaction(self, txid: str, block_hash: str = None) -> Dict:
        """
        Filter a transaction for all configured patterns.

        Args:
            txid: Transaction ID
            block_hash: Block hash (required for transactions already in blocks)

        Returns:
            Dictionary with filter results:
            {
                "txid": str,
                "treasury": Dict,
                "ordinal": Dict,
                "covenant": Dict,
                "matched": bool
            }
        """
        tx = self.get_transaction(txid, block_hash)
        if not tx:
            return {
                "txid": txid,
                "treasury": {"matched": False},
                "ordinal": {"matched": False},
                "covenant": {"matched": False},
                "matched": False
            }
        
        treasury_result = self.check_treasury_utxo(tx)
        ordinal_result = self.check_ordinal(tx)
        covenant_result = self.check_covenant(tx)
        
        matched = (
            treasury_result["matched"] or
            ordinal_result["matched"] or
            covenant_result["matched"]
        )
        
        return {
            "txid": txid,
            "treasury": treasury_result,
            "ordinal": ordinal_result,
            "covenant": covenant_result,
            "matched": matched,
            "transaction": tx
        }

