"""Entity model representing real-world concepts."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
import json


@dataclass
class Entity:
    """
    A stable object representing a real-world concept.

    Examples: gene, protein, experiment, condition, strain, reagent,
    person, paper, etc.

    Attributes:
        id: Unique identifier (UUID)
        namespace: Multi-corpus namespace
        type: Entity type (gene, protein, strain, etc.)
        name: Canonical name
        aliases: Alternative names, abbreviations
        metadata: Type-specific attributes
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    id: str
    namespace: str
    type: str
    name: str
    aliases: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        """Initialize timestamps if not provided."""
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()

    @property
    def aliases_json(self) -> str:
        """Serialize aliases to JSON string."""
        return json.dumps(self.aliases)

    @property
    def metadata_json(self) -> str:
        """Serialize metadata to JSON string."""
        return json.dumps(self.metadata)

    @classmethod
    def from_json(
        cls,
        aliases_json: Optional[str] = None,
        metadata_json: Optional[str] = None,
        **kwargs
    ) -> 'Entity':
        """
        Create an Entity from JSON fields.

        Args:
            aliases_json: JSON string for aliases
            metadata_json: JSON string for metadata
            **kwargs: Other Entity fields

        Returns:
            Entity instance
        """
        aliases = json.loads(aliases_json) if aliases_json else []
        metadata = json.loads(metadata_json) if metadata_json else {}
        return cls(aliases=aliases, metadata=metadata, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "namespace": self.namespace,
            "type": self.type,
            "name": self.name,
            "aliases": self.aliases,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"Entity(id={self.id}, type={self.type}, name={self.name})"


@dataclass
class EntityLink:
    """
    Link between a ResourceSegment and an Entity.

    Represents relationships like "mentions", "about", "primary_subject".

    Attributes:
        segment_id: Foreign key to ResourceSegment
        entity_id: Foreign key to Entity
        link_type: Type of relationship (mentions, about, primary)
        confidence: Extraction confidence (0.0 - 1.0)
        created_at: Creation timestamp
    """

    segment_id: str
    entity_id: str
    link_type: str
    confidence: float
    created_at: Optional[datetime] = None

    def __post_init__(self):
        """Initialize timestamp and validate confidence."""
        if self.created_at is None:
            self.created_at = datetime.utcnow()

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "segment_id": self.segment_id,
            "entity_id": self.entity_id,
            "link_type": self.link_type,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f"EntityLink(segment={self.segment_id[:8]}..., entity={self.entity_id[:8]}..., type={self.link_type})"
