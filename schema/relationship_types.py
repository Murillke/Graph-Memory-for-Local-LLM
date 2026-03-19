"""
Relationship Type Schema for Extraction Facts

This module defines the canonical relationship types, synonyms, and normalization
logic for extraction facts. All relationship types in extraction.json files
must be validated against this schema.

Based on: tmp/ACTION-PLAN-relationship-standardization.md v5
"""
from typing import Optional, Dict

# Relationship types organized by category (used for _help_relationship_types)
RELATIONSHIP_CATEGORIES: Dict[str, list] = {
    "Dependency": ["USES", "DEPENDS_ON", "BUILT_WITH", "WRITTEN_IN", "SUPPORTS", "NOT_SUPPORTS"],
    "Structure": ["IMPLEMENTS", "CONTAINS", "PART_OF", "LOCATED_AT"],
    "Lifecycle": ["CREATES", "SUPERSEDES"],
    "Documentation": ["DOCUMENTS", "REFERENCES"],
    "Causation": ["CAUSES", "RESOLVES"],
    "Security": ["VULNERABLE_TO", "NOT_VULNERABLE_TO", "MITIGATES", "COMPROMISES"],
    "Decisions": ["PREFERS", "DECIDED"],
    "Procedural": ["PRECEDES", "RUNS", "EXECUTES", "HAS_STEP_RUN", "RUNS_STEP", "EXTRACTED_FROM"],
    "Generic": ["RELATED_TO", "SIMILAR_TO"],
}

# All canonical types as a set (derived from categories for consistency)
CANONICAL_TYPES = set()
for types in RELATIONSHIP_CATEGORIES.values():
    CANONICAL_TYPES.update(types)

# 29 Canonical Relationship Types
CANONICAL_RELATIONSHIP_TYPES = [
    # Dependency/Usage
    "USES", "DEPENDS_ON", "BUILT_WITH", "WRITTEN_IN",
    "SUPPORTS", "NOT_SUPPORTS",
    # Structure
    "IMPLEMENTS", "CONTAINS", "PART_OF", "LOCATED_AT",
    # Lifecycle
    "CREATES", "SUPERSEDES",
    # Documentation
    "DOCUMENTS", "REFERENCES",
    # Causation/Resolution
    "CAUSES", "RESOLVES",
    # Security
    "VULNERABLE_TO", "NOT_VULNERABLE_TO", "MITIGATES", "COMPROMISES",
    # Preferences/Decisions
    "PREFERS", "DECIDED",
    # Procedural Memory
    "PRECEDES",         # Step ordering: Step1 PRECEDES Step2
    "RUNS",             # Execution: ProcedureRun RUNS Procedure
    "EXECUTES",         # Agent execution: Agent EXECUTES Procedure
    "HAS_STEP_RUN",     # Execution detail: ProcedureRun HAS_STEP_RUN StepRun
    "RUNS_STEP",        # Step execution: StepRun RUNS_STEP ProcedureStep
    "EXTRACTED_FROM",   # Provenance: Procedure EXTRACTED_FROM Document
    # Generic
    "RELATED_TO", "SIMILAR_TO",
]  # 30 canonical types

# Simple synonyms - just replace the type name (no source/target swap)
RELATIONSHIP_SYNONYMS = {
    "REQUIRES": "DEPENDS_ON",
    "NEEDS": "DEPENDS_ON",
    "UTILIZES": "USES",
    "EMPLOYS": "USES",
    "LEVERAGES": "USES",
    "IS_VULNERABLE_TO": "VULNERABLE_TO",
    "AFFECTED_BY": "VULNERABLE_TO",
    "IS_NOT_VULNERABLE_TO": "NOT_VULNERABLE_TO",
    "IMMUNE_TO": "NOT_VULNERABLE_TO",
    "PROTECTED_FROM": "NOT_VULNERABLE_TO",
    "FIXES": "RESOLVES",
    "REPLACES": "SUPERSEDES",
    "INCLUDES": "CONTAINS",
    "HAS": "CONTAINS",
    "OWNS": "CONTAINS",
    "BELONGS_TO": "PART_OF",
    "MEMBER_OF": "PART_OF",
    "EXTENDS": "IMPLEMENTS",
    "INHERITS": "IMPLEMENTS",
    "DESCRIBES": "DOCUMENTS",
    "LINKS_TO": "REFERENCES",
    "TRIGGERS": "CAUSES",
    "LEADS_TO": "CAUSES",
    "RESULTS_IN": "CAUSES",
    "ADDRESSES": "RESOLVES",
    "SOLVES": "RESOLVES",
    "ATTACKS": "COMPROMISES",
    "EXPLOITS": "COMPROMISES",
    "REDUCES": "MITIGATES",
    "PREVENTS": "MITIGATES",
    "CHOSE": "DECIDED",
    "SELECTED": "DECIDED",
    "FAVORS": "PREFERS",
    "LIKES": "PREFERS",
    "GENERATES": "CREATES",
    "PRODUCES": "CREATES",
    "BUILDS": "CREATES",
    "COMPATIBLE_WITH": "SUPPORTS",
    "WORKS_WITH": "SUPPORTS",
    "INCOMPATIBLE_WITH": "NOT_SUPPORTS",
    "ASSOCIATED_WITH": "RELATED_TO",
    "CONNECTED_TO": "RELATED_TO",
    "LINKED_WITH": "RELATED_TO",
    "RESEMBLES": "SIMILAR_TO",
    "LIKE": "SIMILAR_TO",
    "COMES_BEFORE": "PRECEDES",
    "FOLLOWED_BY": "PRECEDES",
    "INVOKES": "EXECUTES",
    "CALLS": "EXECUTES",
    "DERIVED_FROM": "EXTRACTED_FROM",
    "SOURCED_FROM": "EXTRACTED_FROM",
}

# Inverse types - require source/target swap
INVERSE_TYPES = {
    "USED_BY": "USES",
    "CAUSED_BY": "CAUSES",
    "SOLVED_BY": "RESOLVES",
    "RESOLVED_BY": "RESOLVES",
    "CREATED_BY": "CREATES",
    "BUILT_BY": "CREATES",
    "DOCUMENTED_BY": "DOCUMENTS",
    "REFERENCED_BY": "REFERENCES",
    "CONTAINED_IN": "CONTAINS",
    "IMPLEMENTED_BY": "IMPLEMENTS",
    "SUPPORTED_BY": "SUPPORTS",
    "SUPERSEDED_BY": "SUPERSEDES",
    "REPLACED_BY": "SUPERSEDES",
    "COMPROMISED_BY": "COMPROMISES",
    "MITIGATED_BY": "MITIGATES",
    "DECIDED_BY": "DECIDED",
    "PREFERRED_BY": "PREFERS",
    "FOLLOWS": "PRECEDES",
    "PRECEDED_BY": "PRECEDES",
    "RUN_BY": "RUNS",
    "EXECUTED_BY": "EXECUTES",
}


def normalize_relationship_type(rel_type: str) -> str:
    """
    Normalize a relationship type string to uppercase with underscores.
    
    Args:
        rel_type: Raw relationship type string
        
    Returns:
        Normalized string (uppercase, underscores instead of spaces/hyphens)
    """
    return rel_type.upper().replace("-", "_").replace(" ", "_").strip()


def normalize_fact(fact: dict) -> tuple[dict, Optional[str]]:
    """
    Normalize a fact's relationship type and swap source/target if needed.
    
    Args:
        fact: Dict with 'relationship_type', 'source_entity', 'target_entity', etc.
        
    Returns:
        (normalized_fact, error_message)
        - normalized_fact: Copy of fact with normalized type and possibly swapped entities
        - error_message: None if valid, error string if unknown type
    """
    rel_type = normalize_relationship_type(fact.get("relationship_type", ""))
    result = fact.copy()
    
    # Check inverse types first (require swap)
    if rel_type in INVERSE_TYPES:
        result["relationship_type"] = INVERSE_TYPES[rel_type]
        result["source_entity"], result["target_entity"] = (
            result["target_entity"], result["source_entity"]
        )
        return result, None
    
    # Check simple synonyms
    if rel_type in RELATIONSHIP_SYNONYMS:
        result["relationship_type"] = RELATIONSHIP_SYNONYMS[rel_type]
        return result, None
    
    # Check if already canonical
    if rel_type in CANONICAL_RELATIONSHIP_TYPES:
        result["relationship_type"] = rel_type
        return result, None
    
    # Unknown type - return error
    return result, f"Unknown relationship type: '{fact.get('relationship_type')}' (normalized: '{rel_type}')"


def is_valid_relationship_type(rel_type: str) -> bool:
    """
    Check if a relationship type is valid (canonical, synonym, or inverse).
    
    Args:
        rel_type: Relationship type string to check
        
    Returns:
        True if valid, False otherwise
    """
    normalized = normalize_relationship_type(rel_type)
    return (normalized in CANONICAL_RELATIONSHIP_TYPES or
            normalized in RELATIONSHIP_SYNONYMS or
            normalized in INVERSE_TYPES)


def get_canonical_type(rel_type: str) -> Optional[str]:
    """
    Get the canonical type for a relationship type (after normalization).
    
    Args:
        rel_type: Relationship type string
        
    Returns:
        Canonical type string, or None if unknown
    """
    normalized = normalize_relationship_type(rel_type)
    
    if normalized in CANONICAL_RELATIONSHIP_TYPES:
        return normalized
    if normalized in RELATIONSHIP_SYNONYMS:
        return RELATIONSHIP_SYNONYMS[normalized]
    if normalized in INVERSE_TYPES:
        return INVERSE_TYPES[normalized]
    
    return None

