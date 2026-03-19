"""
Entity Deduplication - Copied and adapted from Graphiti.

This module provides entity deduplication using a two-phase approach:
1. Deterministic: Exact matching + MinHash/LSH fuzzy matching
2. LLM-based: Semantic matching for ambiguous cases

Based on Graphiti's proven deduplication logic.
"""

import re
import math
from hashlib import blake2b
from typing import List, Dict, Any, Set, Tuple
from collections import defaultdict

# Configuration (from Graphiti)
_NAME_ENTROPY_THRESHOLD = 1.5
_MIN_NAME_LENGTH = 6
_MIN_TOKEN_COUNT = 2
_FUZZY_JACCARD_THRESHOLD = 0.9
_MINHASH_PERMUTATIONS = 32
_MINHASH_BAND_SIZE = 4


def normalize_entity_name_exact(name: str) -> str:
    """
    Normalize entity name for exact matching.

    Lowercase and collapse whitespace so equal names map to same key.

    Args:
        name: Entity name

    Returns:
        Normalized name
    """
    normalized = re.sub(r'[\s]+', ' ', name.lower())
    return normalized.strip()


def normalize_entity_name_fuzzy(name: str) -> str:
    """
    Normalize entity name for fuzzy matching.

    Keep alphanumerics and apostrophes for n-gram shingles.

    Args:
        name: Entity name

    Returns:
        Normalized name for fuzzy matching
    """
    normalized = re.sub(r"[^a-z0-9' ]", ' ', normalize_entity_name_exact(name))
    normalized = normalized.strip()
    return re.sub(r'[\s]+', ' ', normalized)


def calculate_name_entropy(normalized_name: str) -> float:
    """
    Calculate Shannon entropy of entity name.

    Approximate text specificity using Shannon entropy over characters.
    Short or repetitive names yield low entropy.

    Args:
        normalized_name: Normalized entity name

    Returns:
        Entropy value
    """
    if not normalized_name:
        return 0.0

    counts: Dict[str, int] = {}
    for char in normalized_name.replace(' ', ''):
        counts[char] = counts.get(char, 0) + 1

    total = sum(counts.values())
    if total == 0:
        return 0.0

    entropy = 0.0
    for count in counts.values():
        probability = count / total
        entropy -= probability * math.log2(probability)

    return entropy


def has_high_entropy(normalized_name: str) -> bool:
    """
    Check if name has high enough entropy for fuzzy matching.

    Filter out very short or low-entropy names that are unreliable.

    Args:
        normalized_name: Normalized entity name

    Returns:
        True if name is suitable for fuzzy matching
    """
    token_count = len(normalized_name.split())
    if len(normalized_name) < _MIN_NAME_LENGTH and token_count < _MIN_TOKEN_COUNT:
        return False

    return calculate_name_entropy(normalized_name) >= _NAME_ENTROPY_THRESHOLD


def create_shingles(normalized_name: str) -> Set[str]:
    """
    Create 3-gram shingles from normalized name.

    Args:
        normalized_name: Normalized entity name

    Returns:
        Set of 3-gram shingles
    """
    cleaned = normalized_name.replace(' ', '')
    if len(cleaned) < 2:
        return {cleaned} if cleaned else set()

    return {cleaned[i:i+3] for i in range(len(cleaned) - 2)}


def hash_shingle(shingle: str, seed: int) -> int:
    """
    Generate deterministic 64-bit hash for a shingle.

    Args:
        shingle: Shingle string
        seed: Permutation seed

    Returns:
        64-bit hash value
    """
    digest = blake2b(f'{seed}:{shingle}'.encode(), digest_size=8)
    return int.from_bytes(digest.digest(), 'big')


def calculate_minhash_signature(shingles: Set[str]) -> Tuple[int, ...]:
    """
    Compute MinHash signature for shingle set.

    Args:
        shingles: Set of shingles

    Returns:
        MinHash signature tuple
    """
    if not shingles:
        return tuple()

    seeds = range(_MINHASH_PERMUTATIONS)
    signature: List[int] = []
    for seed in seeds:
        min_hash = min(hash_shingle(shingle, seed) for shingle in shingles)
        signature.append(min_hash)

    return tuple(signature)


def create_lsh_bands(signature: Tuple[int, ...]) -> List[Tuple[int, ...]]:
    """
    Split MinHash signature into bands for LSH.

    Args:
        signature: MinHash signature

    Returns:
        List of bands
    """
    if not signature:
        return []

    bands: List[Tuple[int, ...]] = []
    for start in range(0, len(signature), _MINHASH_BAND_SIZE):
        band = signature[start:start + _MINHASH_BAND_SIZE]
        if len(band) == _MINHASH_BAND_SIZE:
            bands.append(band)
    return bands


def calculate_jaccard_similarity(a: Set[str], b: Set[str]) -> float:
    """
    Calculate Jaccard similarity between two shingle sets.

    Args:
        a: First shingle set
        b: Second shingle set

    Returns:
        Jaccard similarity (0.0 to 1.0)
    """
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0

    intersection = len(a.intersection(b))
    union = len(a.union(b))
    return intersection / union if union else 0.0


def find_duplicate_candidates_deterministic(
    new_entity: Dict[str, Any],
    existing_entities: List[Dict[str, Any]]
) -> List[Tuple[Dict[str, Any], float]]:
    """
    Find duplicate candidates using deterministic methods.

    Phase 1: Exact name matching
    Phase 2: MinHash + LSH fuzzy matching

    Args:
        new_entity: New entity to check
        existing_entities: List of existing entities

    Returns:
        List of (entity, similarity_score) tuples above threshold
    """
    new_name = new_entity.get('name', '')
    normalized_exact = normalize_entity_name_exact(new_name)
    normalized_fuzzy = normalize_entity_name_fuzzy(new_name)

    # Phase 1: Exact matching
    exact_matches = []
    for entity in existing_entities:
        entity_name = entity.get('name', '')
        if normalize_entity_name_exact(entity_name) == normalized_exact:
            exact_matches.append((entity, 1.0))

    if exact_matches:
        return exact_matches

    # Phase 2: Fuzzy matching (only if high entropy)
    if not has_high_entropy(normalized_fuzzy):
        return []

    # Create shingles and signature for new entity
    new_shingles = create_shingles(normalized_fuzzy)
    new_signature = calculate_minhash_signature(new_shingles)
    new_bands = create_lsh_bands(new_signature)

    # Build LSH buckets for existing entities
    lsh_buckets: Dict[Tuple[int, Tuple[int, ...]], List[Dict[str, Any]]] = defaultdict(list)
    entity_shingles: Dict[str, Set[str]] = {}

    for entity in existing_entities:
        entity_name = entity.get('name', '')
        entity_uuid = entity.get('uuid', '')
        entity_fuzzy = normalize_entity_name_fuzzy(entity_name)

        shingles = create_shingles(entity_fuzzy)
        entity_shingles[entity_uuid] = shingles

        signature = calculate_minhash_signature(shingles)
        for band_index, band in enumerate(create_lsh_bands(signature)):
            lsh_buckets[(band_index, band)].append(entity)

    # Find candidates in same LSH buckets
    candidate_entities: Set[str] = set()
    for band_index, band in enumerate(new_bands):
        candidates = lsh_buckets.get((band_index, band), [])
        for candidate in candidates:
            candidate_entities.add(candidate.get('uuid', ''))

    # Calculate Jaccard similarity for candidates
    fuzzy_matches = []
    for entity in existing_entities:
        entity_uuid = entity.get('uuid', '')
        if entity_uuid not in candidate_entities:
            continue

        entity_shingles_set = entity_shingles.get(entity_uuid, set())
        similarity = calculate_jaccard_similarity(new_shingles, entity_shingles_set)

        if similarity >= _FUZZY_JACCARD_THRESHOLD:
            fuzzy_matches.append((entity, similarity))

    return fuzzy_matches


def get_llm_dedup_prompt(
    new_entity: Dict[str, Any],
    candidate_entities: List[Dict[str, Any]]
) -> str:
    """
    Generate LLM prompt for semantic deduplication.

    For ambiguous cases that deterministic methods couldn't resolve.

    Args:
        new_entity: New entity to check
        candidate_entities: List of candidate duplicate entities

    Returns:
        Prompt string for LLM
    """
    new_name = new_entity.get('name', '')
    new_type = new_entity.get('type', '')
    new_summary = new_entity.get('summary', '')

    candidates_str = "\n".join([
        f"- {e.get('name', '')} ({e.get('type', '')}): {e.get('summary', '')}"
        for e in candidate_entities
    ])

    prompt = f"""You are a helpful assistant that determines whether a NEW ENTITY is a duplicate of any EXISTING ENTITIES.

NEW ENTITY:
- Name: {new_name}
- Type: {new_type}
- Summary: {new_summary}

EXISTING ENTITIES:
{candidates_str}

Entities should only be considered duplicates if they refer to the *same real-world object or concept*.

Do NOT mark entities as duplicates if:
- They are related but distinct
- They have similar names but refer to separate instances or concepts

TASK:
Compare the NEW ENTITY against each EXISTING ENTITY.
If it refers to the same real-world object, identify the matching entity by name.

Respond with JSON:
{{
  "is_duplicate": true/false,
  "duplicate_name": "name of matching entity or empty string"
}}"""

    return prompt
