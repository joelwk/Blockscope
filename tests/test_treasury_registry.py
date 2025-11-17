"""Tests for treasury registry module."""

import yaml
import tempfile
from pathlib import Path
from feesentinel.treasury_registry import TreasuryRegistry, load_treasury_registry


def test_load_simple_addresses():
    """Test loading simple addresses list."""
    config = {
        "addresses": ["bc1qtest1", "bc1qtest2"]
    }
    registry = load_treasury_registry(config)
    
    assert len(registry.address_index) == 2
    assert "bc1qtest1" in registry.address_index
    assert "bc1qtest2" in registry.address_index
    
    # Check default metadata
    meta1 = registry.get_address_metadata("bc1qtest1")
    assert meta1.category == "unknown"
    assert meta1.entity_id == "unknown"


def test_load_famous_addresses():
    """Test loading famous addresses with metadata."""
    config = {
        "famous_addresses": [
            {
                "id": "genesis",
                "label": "Genesis Block",
                "category": "protocol_monument",
                "addresses": ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"]
            }
        ]
    }
    registry = load_treasury_registry(config)
    
    assert len(registry.address_index) == 1
    meta = registry.get_address_metadata("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
    assert meta.category == "protocol_monument"
    assert meta.entity_id == "genesis"
    assert meta.entity_label == "Genesis Block"
    
    # Check entity
    entity = registry.get_entity_metadata("genesis")
    assert entity is not None
    assert entity.category == "protocol_monument"


def test_load_clusters():
    """Test loading entity clusters."""
    config = {
        "clusters": [
            {
                "id": "usg_treasury",
                "label": "US Government",
                "category": "USG_seizure",
                "addresses": ["bc1qaddr1", "bc1qaddr2"],
                "notes": "USG holdings"
            }
        ]
    }
    registry = load_treasury_registry(config)
    
    assert len(registry.address_index) == 2
    assert len(registry.entities) == 1
    
    entity = registry.get_entity_metadata("usg_treasury")
    assert entity.category == "USG_seizure"
    assert len(entity.addresses) == 2


def test_load_external_file():
    """Test loading addresses from external YAML file."""
    # Create temporary YAML file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({
            "famous_addresses": [
                {
                    "id": "test_entity",
                    "label": "Test Entity",
                    "category": "test",
                    "addresses": ["bc1qexternal"]
                }
            ]
        }, f)
        file_path = f.name
    
    try:
        config = {
            "address_files": [file_path]
        }
        registry = load_treasury_registry(config)
        
        assert len(registry.address_index) == 1
        meta = registry.get_address_metadata("bc1qexternal")
        assert meta.category == "test"
        assert meta.entity_id == "test_entity"
    finally:
        Path(file_path).unlink()


def test_duplicate_address_warning():
    """Test that duplicate addresses with conflicting metadata are handled."""
    config = {
        "famous_addresses": [
            {
                "id": "entity1",
                "label": "Entity 1",
                "category": "category1",
                "addresses": ["bc1qduplicate"]
            },
            {
                "id": "entity2",
                "label": "Entity 2",
                "category": "category2",
                "addresses": ["bc1qduplicate"]
            }
        ]
    }
    registry = load_treasury_registry(config)
    
    # Should use first definition
    meta = registry.get_address_metadata("bc1qduplicate")
    assert meta.entity_id == "entity1"
    assert meta.category == "category1"


def test_merge_inline_and_external():
    """Test merging inline config and external files."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump({
            "famous_addresses": [
                {
                    "id": "external_entity",
                    "label": "External",
                    "category": "external",
                    "addresses": ["bc1qexternal"]
                }
            ]
        }, f)
        file_path = f.name
    
    try:
        config = {
            "famous_addresses": [
                {
                    "id": "inline_entity",
                    "label": "Inline",
                    "category": "inline",
                    "addresses": ["bc1qinline"]
                }
            ],
            "address_files": [file_path]
        }
        registry = load_treasury_registry(config)
        
        assert len(registry.address_index) == 2
        assert "bc1qinline" in registry.address_index
        assert "bc1qexternal" in registry.address_index
        
        assert registry.get_address_metadata("bc1qinline").category == "inline"
        assert registry.get_address_metadata("bc1qexternal").category == "external"
    finally:
        Path(file_path).unlink()


def test_empty_config():
    """Test loading empty config."""
    registry = load_treasury_registry({})
    assert len(registry.address_index) == 0
    assert len(registry.entities) == 0


def test_missing_id_handling():
    """Test that entries without id are skipped."""
    config = {
        "famous_addresses": [
            {
                "label": "No ID",
                "category": "test",
                "addresses": ["bc1qtest"]
            }
        ]
    }
    registry = load_treasury_registry(config)
    
    # Entry should be skipped
    assert len(registry.address_index) == 0


def test_treasury_addresses_set():
    """Test that treasury_addresses set is populated correctly."""
    config = {
        "addresses": ["bc1q1", "bc1q2"],
        "famous_addresses": [
            {
                "id": "test",
                "label": "Test",
                "category": "test",
                "addresses": ["bc1q3"]
            }
        ]
        }
    registry = load_treasury_registry(config)
    
    assert len(registry.treasury_addresses) == 3
    assert "bc1q1" in registry.treasury_addresses
    assert "bc1q2" in registry.treasury_addresses
    assert "bc1q3" in registry.treasury_addresses

