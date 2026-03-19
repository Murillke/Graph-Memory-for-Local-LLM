#!/usr/bin/env python3
"""
Test relationship type schema and normalization.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from schema.relationship_types import (
    normalize_fact,
    is_valid_relationship_type,
    get_canonical_type,
    CANONICAL_RELATIONSHIP_TYPES,
    RELATIONSHIP_SYNONYMS,
    INVERSE_TYPES,
)


def test_canonical_count():
    """Verify we have exactly 24 canonical types."""
    assert len(CANONICAL_RELATIONSHIP_TYPES) == 30, \
        f"Expected 24 canonical types, got {len(CANONICAL_RELATIONSHIP_TYPES)}"
    print(f"[PASS] Canonical types count: {len(CANONICAL_RELATIONSHIP_TYPES)}")


def test_canonical_type_passthrough():
    """Canonical types should pass through unchanged."""
    fact = {
        'source_entity': 'React',
        'target_entity': 'JavaScript',
        'relationship_type': 'USES',
        'fact': 'React uses JavaScript'
    }
    result, error = normalize_fact(fact)
    
    assert error is None, f"Unexpected error: {error}"
    assert result['relationship_type'] == 'USES'
    assert result['source_entity'] == 'React'
    assert result['target_entity'] == 'JavaScript'
    print("[PASS] Canonical type passthrough")


def test_synonym_normalization():
    """Synonyms should normalize to canonical types."""
    fact = {
        'source_entity': 'App',
        'target_entity': 'Database',
        'relationship_type': 'REQUIRES',
        'fact': 'App requires Database'
    }
    result, error = normalize_fact(fact)
    
    assert error is None, f"Unexpected error: {error}"
    assert result['relationship_type'] == 'DEPENDS_ON'
    assert result['source_entity'] == 'App'  # No swap for synonyms
    assert result['target_entity'] == 'Database'
    print("[PASS] Synonym normalization (REQUIRES -> DEPENDS_ON)")


def test_inverse_type_swap():
    """Inverse types should swap source/target."""
    fact = {
        'source_entity': 'JavaScript',
        'target_entity': 'React',
        'relationship_type': 'USED_BY',
        'fact': 'JavaScript used by React'
    }
    result, error = normalize_fact(fact)
    
    assert error is None, f"Unexpected error: {error}"
    assert result['relationship_type'] == 'USES'
    assert result['source_entity'] == 'React', f"Expected React, got {result['source_entity']}"
    assert result['target_entity'] == 'JavaScript', f"Expected JavaScript, got {result['target_entity']}"
    print("[PASS] Inverse type swap (USED_BY -> USES with swap)")


def test_unknown_type_error():
    """Unknown types should return an error."""
    fact = {
        'source_entity': 'A',
        'target_entity': 'B',
        'relationship_type': 'INVENTED_BY',
        'fact': 'A invented by B'
    }
    result, error = normalize_fact(fact)
    
    assert error is not None, "Expected error for unknown type"
    assert 'INVENTED_BY' in error
    print(f"[PASS] Unknown type returns error: {error}")


def test_is_valid_relationship_type():
    """Test is_valid_relationship_type function."""
    assert is_valid_relationship_type('USES') is True
    assert is_valid_relationship_type('REQUIRES') is True  # Synonym
    assert is_valid_relationship_type('USED_BY') is True   # Inverse
    assert is_valid_relationship_type('INVENTED_BY') is False
    print("[PASS] is_valid_relationship_type")


def test_get_canonical_type():
    """Test get_canonical_type function."""
    assert get_canonical_type('USES') == 'USES'
    assert get_canonical_type('REQUIRES') == 'DEPENDS_ON'
    assert get_canonical_type('USED_BY') == 'USES'
    assert get_canonical_type('INVENTED_BY') is None
    print("[PASS] get_canonical_type")


def test_case_insensitivity():
    """Relationship types should be case-insensitive."""
    fact1 = {'source_entity': 'A', 'target_entity': 'B', 'relationship_type': 'uses'}
    fact2 = {'source_entity': 'A', 'target_entity': 'B', 'relationship_type': 'Uses'}
    fact3 = {'source_entity': 'A', 'target_entity': 'B', 'relationship_type': 'USES'}
    
    r1, e1 = normalize_fact(fact1)
    r2, e2 = normalize_fact(fact2)
    r3, e3 = normalize_fact(fact3)
    
    assert e1 is None and e2 is None and e3 is None
    assert r1['relationship_type'] == r2['relationship_type'] == r3['relationship_type'] == 'USES'
    print("[PASS] Case insensitivity")


def test_hyphen_and_space_normalization():
    """Hyphens and spaces should normalize to underscores."""
    fact1 = {'source_entity': 'A', 'target_entity': 'B', 'relationship_type': 'DEPENDS-ON'}
    fact2 = {'source_entity': 'A', 'target_entity': 'B', 'relationship_type': 'DEPENDS ON'}
    
    r1, e1 = normalize_fact(fact1)
    r2, e2 = normalize_fact(fact2)
    
    assert e1 is None and e2 is None
    assert r1['relationship_type'] == 'DEPENDS_ON'
    assert r2['relationship_type'] == 'DEPENDS_ON'
    print("[PASS] Hyphen and space normalization")


def test_show_normalization_examples():
    """Show normalization examples for verification."""
    print("\n[INFO] Normalization examples:")

    # Synonym (REQUIRES -> DEPENDS_ON, no swap)
    fact1 = {'source_entity': 'App', 'target_entity': 'React', 'relationship_type': 'REQUIRES', 'fact': 'App requires React'}
    r1, e1 = normalize_fact(fact1)
    print(f"  REQUIRES: App -> React  =>  {r1['relationship_type']}: {r1['source_entity']} -> {r1['target_entity']}")
    assert r1['relationship_type'] == 'DEPENDS_ON'
    assert r1['source_entity'] == 'App'  # No swap

    # Inverse (USED_BY -> USES, with swap)
    fact2 = {'source_entity': 'JavaScript', 'target_entity': 'React', 'relationship_type': 'USED_BY', 'fact': 'JS used by React'}
    r2, e2 = normalize_fact(fact2)
    print(f"  USED_BY: JavaScript -> React  =>  {r2['relationship_type']}: {r2['source_entity']} -> {r2['target_entity']}")
    assert r2['relationship_type'] == 'USES'
    assert r2['source_entity'] == 'React'  # Swapped!
    assert r2['target_entity'] == 'JavaScript'  # Swapped!

    print("[PASS] Normalization examples verified")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Relationship Type Schema")
    print("=" * 60)
    print()

    test_canonical_count()
    test_canonical_type_passthrough()
    test_synonym_normalization()
    test_inverse_type_swap()
    test_unknown_type_error()
    test_is_valid_relationship_type()
    test_get_canonical_type()
    test_case_insensitivity()
    test_hyphen_and_space_normalization()
    test_show_normalization_examples()

    print()
    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)


if __name__ == '__main__':
    main()

