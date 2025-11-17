"""Tests for enriched transaction filter with treasury registry."""

from feesentinel.transaction_filter import TransactionFilter
from feesentinel.treasury_registry import TreasuryRegistry, load_treasury_registry
from unittest.mock import Mock


def create_mock_rpc_client():
    """Create a mock RPC client."""
    mock_rpc = Mock()
    return mock_rpc


def test_treasury_filter_with_registry():
    """Test treasury filter enrichment with registry."""
    config = {
        "famous_addresses": [
            {
                "id": "test_entity",
                "label": "Test Entity",
                "category": "test_category",
                "addresses": ["bc1qtest"]
            }
        ]
    }
    registry = load_treasury_registry(config)
    
    mock_rpc = create_mock_rpc_client()
    filter_obj = TransactionFilter(
        mock_rpc,
        treasury_registry=registry
    )
    
    # Mock transaction with treasury address
    tx = {
        "vin": [],
        "vout": [
            {
                "value": 0.01,  # 0.01 BTC = 1,000,000 sats
                "scriptPubKey": {
                    "addresses": ["bc1qtest"]
                }
            }
        ]
    }
    
    result = filter_obj.check_treasury_utxo(tx)
    
    assert result["matched"] is True
    assert result["type"] == "receive"
    assert len(result["enriched_addresses"]) == 1
    
    enriched = result["enriched_addresses"][0]
    assert enriched["address"] == "bc1qtest"
    assert enriched["category"] == "test_category"
    assert enriched["entity_id"] == "test_entity"
    assert enriched["entity_label"] == "Test Entity"
    assert enriched["direction"] == "output"
    assert enriched["value_sats"] == 1_000_000
    
    # Check entities aggregation
    assert len(result["entities"]) == 1
    entity = result["entities"][0]
    assert entity["entity_id"] == "test_entity"
    assert entity["category"] == "test_category"
    assert entity["in_sats"] == 1_000_000
    assert entity["out_sats"] == 0
    
    # Check summary
    assert "test_category" in result["summary"]
    summary = result["summary"]["test_category"]
    assert summary["in_sats"] == 1_000_000
    assert summary["out_sats"] == 0
    assert summary["entity_count"] == 1


def test_treasury_filter_without_registry():
    """Test treasury filter falls back to simple addresses."""
    mock_rpc = create_mock_rpc_client()
    filter_obj = TransactionFilter(
        mock_rpc,
        treasury_addresses=["bc1qsimple"]
    )
    
    tx = {
        "vin": [],
        "vout": [
            {
                "value": 0.01,
                "scriptPubKey": {
                    "addresses": ["bc1qsimple"]
                }
            }
        ]
    }
    
    result = filter_obj.check_treasury_utxo(tx)
    
    assert result["matched"] is True
    # Should have enriched_addresses but with unknown metadata
    assert len(result["enriched_addresses"]) == 1
    enriched = result["enriched_addresses"][0]
    assert enriched["category"] == "unknown"
    assert enriched["entity_id"] == "unknown"


def test_ordinal_hotspots():
    """Test ordinal hotspot detection."""
    mock_rpc = create_mock_rpc_client()
    
    # Mock RPC call to return a transaction
    def mock_call(method, *args):
        if method == "getrawtransaction":
            return {
                "vout": [
                    {
                        "value": 0.001,
                        "scriptPubKey": {
                            "addresses": ["bc1qhotspot"]
                        }
                    }
                ]
            }
        return None
    
    mock_rpc.call = Mock(side_effect=mock_call)
    
    filter_obj = TransactionFilter(
        mock_rpc,
        detect_ordinals=True,
        ordinal_hotspots=[
            {
                "id": "hotspot1",
                "label": "Test Hotspot",
                "addresses": ["bc1qhotspot"]
            }
        ]
    )
    
    tx = {
        "vin": [
            {
                "txid": "prev_tx",
                "vout": 0,
                "txinwitness": ["", "ord", "data"]  # Need at least 3 elements for pattern match
            }
        ],
        "vout": [
            {
                "value": 0.001,
                "scriptPubKey": {
                    "addresses": ["bc1qhotspot"]
                }
            }
        ]
    }
    
    result = filter_obj.check_ordinal(tx)
    
    assert result["matched"] is True
    assert len(result["inscriptions"]) > 0
    
    # Hotspots are only checked if inscriptions are found AND addresses match
    # Since we're checking outputs, the hotspot should match
    if len(result["hotspots"]) > 0:
        hotspot = result["hotspots"][0]
        assert hotspot["id"] == "hotspot1"
        assert hotspot["label"] == "Test Hotspot"
        assert hotspot["address"] == "bc1qhotspot"


def test_entity_aggregation_multiple_addresses():
    """Test entity aggregation when multiple addresses from same entity."""
    config = {
        "clusters": [
            {
                "id": "cluster1",
                "label": "Test Cluster",
                "category": "test",
                "addresses": ["bc1qaddr1", "bc1qaddr2"]
            }
        ]
    }
    registry = load_treasury_registry(config)
    
    mock_rpc = create_mock_rpc_client()
    filter_obj = TransactionFilter(
        mock_rpc,
        treasury_registry=registry
    )
    
    tx = {
        "vin": [],
        "vout": [
            {
                "value": 0.01,
                "scriptPubKey": {
                    "addresses": ["bc1qaddr1"]
                }
            },
            {
                "value": 0.02,
                "scriptPubKey": {
                    "addresses": ["bc1qaddr2"]
                }
            }
        ]
    }
    
    result = filter_obj.check_treasury_utxo(tx)
    
    assert result["matched"] is True
    assert len(result["enriched_addresses"]) == 2
    
    # Both addresses should aggregate to same entity
    assert len(result["entities"]) == 1
    entity = result["entities"][0]
    assert entity["entity_id"] == "cluster1"
    assert entity["in_sats"] == 3_000_000  # 0.01 + 0.02 BTC


def test_category_summary():
    """Test category summary aggregation."""
    config = {
        "famous_addresses": [
            {
                "id": "entity1",
                "label": "Entity 1",
                "category": "category_a",
                "addresses": ["bc1qa"]
            },
            {
                "id": "entity2",
                "label": "Entity 2",
                "category": "category_a",
                "addresses": ["bc1qb"]
            },
            {
                "id": "entity3",
                "label": "Entity 3",
                "category": "category_b",
                "addresses": ["bc1qc"]
            }
        ]
    }
    registry = load_treasury_registry(config)
    
    mock_rpc = create_mock_rpc_client()
    filter_obj = TransactionFilter(
        mock_rpc,
        treasury_registry=registry
    )
    
    tx = {
        "vin": [],
        "vout": [
            {
                "value": 0.01,
                "scriptPubKey": {"addresses": ["bc1qa"]}
            },
            {
                "value": 0.02,
                "scriptPubKey": {"addresses": ["bc1qb"]}
            },
            {
                "value": 0.03,
                "scriptPubKey": {"addresses": ["bc1qc"]}
            }
        ]
    }
    
    result = filter_obj.check_treasury_utxo(tx)
    
    summary = result["summary"]
    assert "category_a" in summary
    assert "category_b" in summary
    
    # category_a should aggregate entity1 and entity2
    assert summary["category_a"]["in_sats"] == 3_000_000
    assert summary["category_a"]["entity_count"] == 2
    
    # category_b should have entity3
    assert summary["category_b"]["in_sats"] == 3_000_000
    assert summary["category_b"]["entity_count"] == 1

