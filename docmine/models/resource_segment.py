"""ResourceSegment model representing a stable knowledge unit."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
import json


@dataclass
class ResourceSegment:
    """
    A stable, re-ingestable, de-duplicatable unit of knowledge.

    Segments are the primary retrieval unit. They are deterministically
    generated from an InformationResource and maintain provenance.

    Attributes:
        id: Deterministic hash (stable across re-ingestion)
        ir_id: Foreign key to parent InformationResource
        segment_index: Order within the IR (0-indexed)
        text: Actual content (1-3 sentences, normalized)
        provenance: Precise location metadata (page, offsets, etc.)
        text_hash: SHA256 of normalized text
        created_at: Creation timestamp
    """

    id: str
    ir_id: str
    segment_index: int
    text: str
    provenance: Dict[str, Any]
    text_hash: str
    created_at: Optional[datetime] = None

    def __post_init__(self):
        """Initialize timestamp if not provided."""
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    @property
    def provenance_json(self) -> str:
        """Serialize provenance to JSON string."""
        return json.dumps(self.provenance)

    @classmethod
    def from_provenance_json(cls, provenance_json: str, **kwargs) -> 'ResourceSegment':
        """
        Create a ResourceSegment from JSON provenance.

        Args:
            provenance_json: JSON string
            **kwargs: Other ResourceSegment fields

        Returns:
            ResourceSegment instance
        """
        provenance = json.loads(provenance_json) if provenance_json else {}
        return cls(provenance=provenance, **kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "ir_id": self.ir_id,
            "segment_index": self.segment_index,
            "text": self.text,
            "provenance": self.provenance,
            "text_hash": self.text_hash,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        preview = self.text[:50] + "..." if len(self.text) > 50 else self.text
        return f"ResourceSegment(id={self.id[:8]}..., text='{preview}')"
