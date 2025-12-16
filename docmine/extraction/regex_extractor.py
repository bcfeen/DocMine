"""Regex-based entity extractor (baseline implementation)."""

import re
from typing import List, Dict, Set, Pattern

from .base_extractor import BaseEntityExtractor, ExtractedEntity


class RegexEntityExtractor(BaseEntityExtractor):
    """
    Baseline entity extractor using regular expression patterns.

    Fast, free, and deterministic, but limited recall.
    Good starting point for domain-specific extraction.
    """

    # Default patterns for common entity types
    DEFAULT_PATTERNS: Dict[str, str] = {
        # Strain identifiers: 2-4 uppercase letters + 3-6 alphanumeric
        # Examples: CCNA001, YPH499, BY4741
        "strain": r"\b[A-Z]{2,4}[A-Z0-9]{3,6}\b",

        # Gene symbols: 2-5 uppercase letters + 1-2 digits
        # Examples: BRCA1, TP53, MYC
        "gene": r"\b[A-Z]{2,5}[0-9]{1,2}\b",

        # Protein identifiers: Similar to genes but may have prefixes
        # Examples: p53, HER2, CD4
        "protein": r"\b[a-zA-Z]{2,4}[0-9]{1,3}\b",

        # Email addresses
        "email": r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",

        # DOI (Digital Object Identifier)
        "doi": r"\b10\.\d{4,}/[-._;()/:a-zA-Z0-9]+\b",

        # PubMed IDs
        "pmid": r"\bPMID:?\s*(\d{7,8})\b",

        # Accession numbers (generic: 1-3 letters + 5-7 digits)
        "accession": r"\b[A-Z]{1,3}\d{5,7}\b",
    }

    def __init__(
        self,
        patterns: Dict[str, str] = None,
        case_sensitive: bool = True,
        min_confidence: float = 0.5
    ):
        """
        Initialize regex entity extractor.

        Args:
            patterns: Custom patterns dict {type: regex_pattern}.
                      If None, uses DEFAULT_PATTERNS.
            case_sensitive: Whether patterns are case-sensitive
            min_confidence: Minimum confidence threshold (0.0 - 1.0)
        """
        self.patterns: Dict[str, Pattern] = {}
        self.case_sensitive = case_sensitive
        self.min_confidence = min_confidence

        # Compile patterns
        pattern_dict = patterns if patterns is not None else self.DEFAULT_PATTERNS
        flags = 0 if case_sensitive else re.IGNORECASE

        for entity_type, pattern_str in pattern_dict.items():
            try:
                self.patterns[entity_type] = re.compile(pattern_str, flags)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern for '{entity_type}': {e}")

    def extract(self, text: str) -> List[ExtractedEntity]:
        """
        Extract entities from text using regex patterns.

        Args:
            text: Input text

        Returns:
            List of ExtractedEntity objects
        """
        entities: List[ExtractedEntity] = []
        seen: Set[tuple] = set()  # (type, name) to avoid duplicates

        for entity_type, pattern in self.patterns.items():
            matches = pattern.finditer(text)

            for match in matches:
                name = match.group(0).strip()

                # Skip empty matches
                if not name:
                    continue

                # Skip duplicates
                key = (entity_type, name)
                if key in seen:
                    continue
                seen.add(key)

                # Calculate confidence based on pattern specificity
                confidence = self._calculate_confidence(entity_type, name)

                # Skip if below threshold
                if confidence < self.min_confidence:
                    continue

                entities.append(ExtractedEntity(
                    type=entity_type,
                    name=name,
                    confidence=confidence
                ))

        return entities

    def _calculate_confidence(self, entity_type: str, name: str) -> float:
        """
        Calculate extraction confidence for a match.

        This is a heuristic based on pattern specificity and string characteristics.

        Args:
            entity_type: Type of entity
            name: Extracted name

        Returns:
            Confidence score (0.0 - 1.0)
        """
        base_confidence = 0.7  # Regex patterns have moderate confidence

        # Adjust based on string characteristics
        modifiers = 0.0

        # Longer strings are more specific
        if len(name) >= 6:
            modifiers += 0.1

        # Mixed case is more specific
        if name != name.upper() and name != name.lower():
            modifiers += 0.1

        # Numbers increase specificity
        if any(c.isdigit() for c in name):
            modifiers += 0.05

        # Type-specific adjustments
        if entity_type in ("email", "doi", "pmid"):
            # These patterns are very specific
            modifiers += 0.2

        return min(1.0, base_confidence + modifiers)

    def add_pattern(self, entity_type: str, pattern: str):
        """
        Add a new extraction pattern.

        Args:
            entity_type: Type of entity to extract
            pattern: Regex pattern string
        """
        flags = 0 if self.case_sensitive else re.IGNORECASE
        try:
            self.patterns[entity_type] = re.compile(pattern, flags)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern for '{entity_type}': {e}")

    def remove_pattern(self, entity_type: str):
        """
        Remove an extraction pattern.

        Args:
            entity_type: Type of entity to stop extracting
        """
        if entity_type in self.patterns:
            del self.patterns[entity_type]

    def list_patterns(self) -> Dict[str, str]:
        """
        List all current patterns.

        Returns:
            Dictionary of {type: pattern_string}
        """
        return {
            entity_type: pattern.pattern
            for entity_type, pattern in self.patterns.items()
        }
