"""Stable ID generation utilities for knowledge objects."""

import hashlib
import uuid
from typing import Dict, Any


def generate_ir_id() -> str:
    """
    Generate a unique ID for an InformationResource.

    Returns:
        UUID string
    """
    return str(uuid.uuid4())


def generate_entity_id() -> str:
    """
    Generate a unique ID for an Entity.

    Returns:
        UUID string
    """
    return str(uuid.uuid4())


def normalize_text(text: str) -> str:
    """
    Normalize text for consistent hashing.

    Collapses whitespace and strips leading/trailing space.

    Args:
        text: Input text

    Returns:
        Normalized text
    """
    return " ".join(text.strip().split())


def generate_segment_id(
    namespace: str,
    source_uri: str,
    provenance_key: str,
    text: str
) -> str:
    """
    Generate a deterministic ID for a ResourceSegment.

    The ID is a SHA256 hash of:
    - namespace
    - source_uri (from parent IR)
    - provenance_key (deterministic location identifier)
    - normalized text

    This ensures that the same segment from the same source will always
    have the same ID, enabling idempotent ingestion.

    Args:
        namespace: Namespace (e.g., "lab_alpha")
        source_uri: Canonical URI of the source (e.g., "file:///doc.pdf")
        provenance_key: Location key (e.g., "5:3" for page 5, sentence 3)
        text: Segment text content

    Returns:
        SHA256 hash as hex string

    Example:
        >>> generate_segment_id(
        ...     "lab_a",
        ...     "file:///paper.pdf",
        ...     "5:3",
        ...     "The CCNA001 strain showed resistance."
        ... )
        'a1b2c3d4e5f6...'
    """
    # Normalize text
    normalized = normalize_text(text)

    # Combine all components
    components = f"{namespace}|{source_uri}|{provenance_key}|{normalized}"

    # Generate SHA256 hash
    hash_object = hashlib.sha256(components.encode('utf-8'))
    return hash_object.hexdigest()


def generate_text_hash(text: str) -> str:
    """
    Generate a hash of text content (for change detection).

    Args:
        text: Text to hash

    Returns:
        SHA256 hash as hex string
    """
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def generate_content_hash(content: bytes) -> str:
    """
    Generate a hash of binary content (for IR change detection).

    Args:
        content: Binary content (e.g., PDF file bytes)

    Returns:
        SHA256 hash as hex string
    """
    return hashlib.sha256(content).hexdigest()


def build_provenance_key(provenance: Dict[str, Any]) -> str:
    """
    Build a deterministic provenance key from provenance metadata.

    Args:
        provenance: Provenance dictionary

    Returns:
        Provenance key string

    Examples:
        >>> build_provenance_key({"page": 5, "sentence": 3})
        '5:3'
        >>> build_provenance_key({"heading_path": "intro/background", "para": 2, "sentence": 1})
        'intro/background:2:1'
    """
    if "page" in provenance and "sentence" in provenance:
        # PDF format
        return f"{provenance['page']}:{provenance['sentence']}"

    elif "heading_path" in provenance:
        # Markdown format
        return f"{provenance['heading_path']}:{provenance.get('para', 0)}:{provenance.get('sentence', 0)}"

    elif "line" in provenance:
        # Plain text format
        return f"{provenance['line']}:{provenance.get('sentence', 0)}"

    elif "table" in provenance and "row" in provenance:
        # Table format
        return f"{provenance['table']}:{provenance['row']}:{provenance.get('col', '')}"

    else:
        # Fallback: use all keys sorted
        keys = sorted(provenance.keys())
        return ":".join(str(provenance[k]) for k in keys)
