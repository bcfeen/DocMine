"""Data models for knowledge-centric system."""

from .information_resource import InformationResource
from .resource_segment import ResourceSegment
from .entity import Entity, EntityLink
from .stable_id import (
    generate_ir_id,
    generate_segment_id,
    generate_entity_id,
    generate_text_hash,
    generate_content_hash,
    normalize_text,
    build_provenance_key,
)

__all__ = [
    "InformationResource",
    "ResourceSegment",
    "Entity",
    "EntityLink",
    "generate_ir_id",
    "generate_segment_id",
    "generate_entity_id",
    "generate_text_hash",
    "generate_content_hash",
    "normalize_text",
    "build_provenance_key",
]
