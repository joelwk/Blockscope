"""Treasury address and cluster registry for event monitoring."""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from .logging import get_logger

logger = get_logger(__name__)


@dataclass
class AddressMetadata:
    """Metadata for a single treasury address."""
    address: str
    entity_id: str
    entity_label: str
    category: str
    tags: List[str] = field(default_factory=list)


@dataclass
class EntityMetadata:
    """Metadata for an entity/cluster."""
    id: str
    label: str
    category: str
    addresses: List[str]
    notes: str = ""


class TreasuryRegistry:
    """Registry for treasury addresses and entities with metadata."""
    
    def __init__(self):
        """Initialize empty registry."""
        self.address_index: Dict[str, AddressMetadata] = {}
        self.entities: Dict[str, EntityMetadata] = {}
        self.treasury_addresses: Set[str] = set()
    
    def load_from_config(self, treasury_config: Dict) -> None:
        """
        Load addresses and entities from treasury config section.
        
        Args:
            treasury_config: Treasury filter configuration dict
        """
        # Load simple addresses list (legacy/backward compatibility)
        simple_addresses = treasury_config.get("addresses", [])
        for addr in simple_addresses:
            if addr not in self.address_index:
                self._add_address(
                    address=addr,
                    entity_id="unknown",
                    entity_label="Unknown",
                    category="unknown",
                    tags=[]
                )
        
        # Load famous addresses
        famous_addresses = treasury_config.get("famous_addresses", [])
        for entry in famous_addresses:
            self._load_famous_address_entry(entry)
        
        # Load clusters
        clusters = treasury_config.get("clusters", [])
        for cluster in clusters:
            self._load_cluster_entry(cluster)
        
        # Load external address files
        address_files = treasury_config.get("address_files", [])
        for file_path in address_files:
            self._load_external_file(file_path)
        
        # Update treasury_addresses set for fast membership checks
        self.treasury_addresses = set(self.address_index.keys())
        
        # Log summary
        categories = set(meta.category for meta in self.address_index.values())
        logger.info(
            f"Loaded treasury registry: {len(self.address_index)} addresses, "
            f"{len(self.entities)} entities, {len(categories)} categories"
        )
    
    def _load_famous_address_entry(self, entry: Dict) -> None:
        """
        Load a famous address entry.
        
        Args:
            entry: Dict with id, label, category, addresses keys
        """
        entry_id = entry.get("id", "")
        label = entry.get("label", "")
        category = entry.get("category", "unknown")
        addresses = entry.get("addresses", [])
        tags = entry.get("tags", [])
        
        if not entry_id:
            logger.warning("Famous address entry missing 'id', skipping")
            return
        
        if not addresses:
            logger.warning(f"Famous address entry '{entry_id}' has no addresses, skipping")
            return
        
        # Add each address with entity metadata
        for addr in addresses:
            self._add_address(
                address=addr,
                entity_id=entry_id,
                entity_label=label,
                category=category,
                tags=tags
            )
        
        # Create or update entity
        if entry_id not in self.entities:
            self.entities[entry_id] = EntityMetadata(
                id=entry_id,
                label=label,
                category=category,
                addresses=list(addresses),
                notes=entry.get("notes", "")
            )
        else:
            # Merge addresses
            existing = self.entities[entry_id]
            existing.addresses.extend([a for a in addresses if a not in existing.addresses])
    
    def _load_cluster_entry(self, cluster: Dict) -> None:
        """
        Load a cluster/entity entry.
        
        Args:
            cluster: Dict with id, label, category, addresses keys
        """
        cluster_id = cluster.get("id", "")
        label = cluster.get("label", "")
        category = cluster.get("category", "unknown")
        addresses = cluster.get("addresses", [])
        notes = cluster.get("notes", "")
        tags = cluster.get("tags", [])
        
        if not cluster_id:
            logger.warning("Cluster entry missing 'id', skipping")
            return
        
        if not addresses:
            logger.warning(f"Cluster entry '{cluster_id}' has no addresses, skipping")
            return
        
        # Add each address with entity metadata
        for addr in addresses:
            self._add_address(
                address=addr,
                entity_id=cluster_id,
                entity_label=label,
                category=category,
                tags=tags
            )
        
        # Create or update entity
        if cluster_id not in self.entities:
            self.entities[cluster_id] = EntityMetadata(
                id=cluster_id,
                label=label,
                category=category,
                addresses=list(addresses),
                notes=notes
            )
        else:
            # Merge addresses
            existing = self.entities[cluster_id]
            existing.addresses.extend([a for a in addresses if a not in existing.addresses])
    
    def _load_external_file(self, file_path: str) -> None:
        """
        Load addresses and entities from external YAML file.
        
        Args:
            file_path: Path to YAML file
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"Address file not found: {file_path}, skipping")
            return
        
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f) or {}
            
            # Support same structure as inline config
            famous_addresses = data.get("famous_addresses", [])
            for entry in famous_addresses:
                self._load_famous_address_entry(entry)
            
            clusters = data.get("clusters", [])
            for cluster in clusters:
                self._load_cluster_entry(cluster)
            
            # Also support simple addresses list
            simple_addresses = data.get("addresses", [])
            for addr in simple_addresses:
                if addr not in self.address_index:
                    self._add_address(
                        address=addr,
                        entity_id="unknown",
                        entity_label="Unknown",
                        category="unknown",
                        tags=[]
                    )
            
            logger.info(f"Loaded {len(famous_addresses)} famous addresses and {len(clusters)} clusters from {file_path}")
        
        except Exception as e:
            logger.error(f"Failed to load address file {file_path}: {e}", exc_info=True)
    
    def _add_address(self, address: str, entity_id: str, entity_label: str, category: str, tags: List[str]) -> None:
        """
        Add an address to the registry with validation.
        
        Args:
            address: Bitcoin address
            entity_id: Entity identifier
            entity_label: Human-readable entity label
            category: Category (e.g., "USG_seizure", "hack", "burn")
            tags: Optional tags
        """
        if address in self.address_index:
            existing = self.address_index[address]
            # Warn if conflicting metadata
            if existing.entity_id != entity_id or existing.category != category:
                logger.warning(
                    f"Address {address[:16]}... already registered with different metadata: "
                    f"existing=({existing.entity_id}, {existing.category}), "
                    f"new=({entity_id}, {category}). Using existing."
                )
            return
        
        self.address_index[address] = AddressMetadata(
            address=address,
            entity_id=entity_id,
            entity_label=entity_label,
            category=category,
            tags=tags
        )
    
    def get_address_metadata(self, address: str) -> Optional[AddressMetadata]:
        """
        Get metadata for an address.
        
        Args:
            address: Bitcoin address
            
        Returns:
            AddressMetadata if found, None otherwise
        """
        return self.address_index.get(address)
    
    def get_entity_metadata(self, entity_id: str) -> Optional[EntityMetadata]:
        """
        Get metadata for an entity.
        
        Args:
            entity_id: Entity identifier
            
        Returns:
            EntityMetadata if found, None otherwise
        """
        return self.entities.get(entity_id)


def load_treasury_registry(treasury_config: Dict) -> TreasuryRegistry:
    """
    Load treasury registry from configuration.
    
    Args:
        treasury_config: Treasury filter configuration dict
        
    Returns:
        TreasuryRegistry instance
    """
    registry = TreasuryRegistry()
    registry.load_from_config(treasury_config)
    return registry

