"""
Schema module for extraction validation.
"""

from .relationship_types import (
    CANONICAL_RELATIONSHIP_TYPES,
    RELATIONSHIP_SYNONYMS,
    INVERSE_TYPES,
    normalize_fact,
    is_valid_relationship_type,
    get_canonical_type,
    normalize_relationship_type,
)

__all__ = [
    "CANONICAL_RELATIONSHIP_TYPES",
    "RELATIONSHIP_SYNONYMS", 
    "INVERSE_TYPES",
    "normalize_fact",
    "is_valid_relationship_type",
    "get_canonical_type",
    "normalize_relationship_type",
]

