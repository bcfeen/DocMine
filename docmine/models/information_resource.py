"""InformationResource model representing a source document."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
import json


@dataclass
class InformationResource:
    """
    A stable object representing a source document or resource.

    Attributes:
        id: Unique identifier (UUID)
        namespace: Multi-corpus namespace (e.g., "lab_alpha")
        source_type: Type of source (pdf, md, txt, web, etc.)
        source_uri: Canonical stable URI (e.g., "file:///path/doc.pdf")
        content_hash: SHA256 hash of content for change detection
        metadata: Arbitrary metadata (author, title, date, etc.)
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    id: str
    namespace: str
    source_type: str
    source_uri: str
    content_hash: str
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
    def metadata_json(self) -> str:
        """Serialize metadata to JSON string."""
        return json.dumps(self.metadata)

    @classmethod
    def from_metadata_json(cls, metadata_json: str, **kwargs) -> 'InformationResource':
        """
        Create an InformationResource from JSON metadata.

        Args:
            metadata_json: JSON string
            **kwargs: Other InformationResource fields

        Returns:
            InformationResource instance
        """
        metadata = json.loads(metadata_json) if metadata_json else {}
        return cls(metadata=metadata, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "namespace": self.namespace,
            "source_type": self.source_type,
            "source_uri": self.source_uri,
            "content_hash": self.content_hash,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"InformationResource(id={self.id}, uri={self.source_uri})"
