"""Base class for entity extractors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class ExtractedEntity:
    """
    An entity extracted from text.

    Attributes:
        type: Entity type (e.g., "strain", "gene", "protein")
        name: Canonical name
        aliases: Alternative names
        confidence: Extraction confidence (0.0 - 1.0)
        metadata: Additional type-specific metadata
    """
    type: str
    name: str
    aliases: List[str] = field(default_factory=list)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate confidence."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


class BaseEntityExtractor(ABC):
    """
    Abstract base class for entity extractors.

    Implementations must be:
    1. Cheap: No expensive API calls per segment
    2. Deterministic: Same input -> same output
    3. Extensible: Easy to add domain-specific patterns
    """

    @abstractmethod
    def extract(self, text: str) -> List[ExtractedEntity]:
        """
        Extract entities from text.

        Args:
            text: Input text

        Returns:
            List of ExtractedEntity objects
        """
        pass

    def extract_batch(self, texts: List[str]) -> List[List[ExtractedEntity]]:
        """
        Extract entities from multiple texts.

        Default implementation calls extract() for each text.
        Subclasses can override for batch optimization.

        Args:
            texts: List of input texts

        Returns:
            List of entity lists (one per input text)
        """
        return [self.extract(text) for text in texts]
