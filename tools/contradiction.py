"""
Fact Contradiction Detection - Copied and adapted from Graphiti.

This module provides fact contradiction detection using LLM-based semantic analysis.
When a new fact contradicts existing facts, the old facts are invalidated with timestamps.

Based on Graphiti's proven contradiction detection logic.
"""

from typing import List, Dict, Any
from datetime import datetime


def get_contradiction_detection_prompt(
    new_fact: Dict[str, Any],
    existing_facts: List[Dict[str, Any]],
    invalidation_candidates: List[Dict[str, Any]] = None
) -> str:
    """
    Generate LLM prompt for contradiction detection.
    
    Args:
        new_fact: New fact to check
        existing_facts: List of existing facts
        invalidation_candidates: Optional list of facts that might be invalidated
        
    Returns:
        Prompt string for LLM
    """
    if invalidation_candidates is None:
        invalidation_candidates = []
    
    # Format new fact
    new_fact_str = f"""Source: {new_fact.get('source_entity', '')}
Relationship: {new_fact.get('relationship_type', '')}
Target: {new_fact.get('target_entity', '')}
Fact: {new_fact.get('fact', '')}"""
    
    # Format existing facts with indices
    existing_facts_str = ""
    for idx, fact in enumerate(existing_facts):
        existing_facts_str += f"""[{idx}] {fact.get('source_entity', '')} --[{fact.get('relationship_type', '')}]--> {fact.get('target_entity', '')}
    Fact: {fact.get('fact', '')}
    Valid: {fact.get('valid_at', '')} to {fact.get('invalid_at', 'present')}

"""
    
    # Format invalidation candidates with indices (continuing from existing facts)
    invalidation_candidates_str = ""
    start_idx = len(existing_facts)
    for idx, fact in enumerate(invalidation_candidates, start=start_idx):
        invalidation_candidates_str += f"""[{idx}] {fact.get('source_entity', '')} --[{fact.get('relationship_type', '')}]--> {fact.get('target_entity', '')}
    Fact: {fact.get('fact', '')}
    Valid: {fact.get('valid_at', '')} to {fact.get('invalid_at', 'present')}

"""
    
    prompt = f"""You are a helpful assistant that de-duplicates facts from fact lists and determines which existing facts are contradicted by the new fact.

Task:
You will receive TWO lists of facts with CONTINUOUS idx numbering across both lists.
EXISTING FACTS are indexed first, followed by FACT INVALIDATION CANDIDATES.

1. DUPLICATE DETECTION:
   - If the NEW FACT represents identical factual information as any fact in EXISTING FACTS, return those idx values in duplicate_facts.
   - Facts with similar information that contain key differences should NOT be marked as duplicates.
   - If no duplicates, return an empty list for duplicate_facts.

2. CONTRADICTION DETECTION:
   - Determine which facts the NEW FACT contradicts from either list.
   - A fact from EXISTING FACTS can be both a duplicate AND contradicted (e.g., semantically the same but the new fact updates/supersedes it).
   - Return all contradicted idx values in contradicted_facts.
   - If no contradictions, return an empty list for contradicted_facts.

IMPORTANT:
- duplicate_facts: ONLY idx values from EXISTING FACTS (cannot include FACT INVALIDATION CANDIDATES)
- contradicted_facts: idx values from EITHER list (EXISTING FACTS or FACT INVALIDATION CANDIDATES)
- The idx values are continuous across both lists (INVALIDATION CANDIDATES start where EXISTING FACTS end)

Guidelines:
1. Some facts may be very similar but will have key differences, particularly around numeric values.
   Do not mark these as duplicates.

<EXISTING FACTS>
{existing_facts_str if existing_facts_str else "None"}
</EXISTING FACTS>

<FACT INVALIDATION CANDIDATES>
{invalidation_candidates_str if invalidation_candidates_str else "None"}
</FACT INVALIDATION CANDIDATES>

<NEW FACT>
{new_fact_str}
</NEW FACT>

Respond with JSON:
{{
  "duplicate_facts": [list of idx values from EXISTING FACTS only],
  "contradicted_facts": [list of idx values from EITHER list]
}}"""
    
    return prompt


def parse_contradiction_response(response: str) -> Dict[str, List[int]]:
    """
    Parse LLM response for contradiction detection.
    
    Args:
        response: JSON string from LLM
        
    Returns:
        Dict with 'duplicate_facts' and 'contradicted_facts' lists
    """
    import json
    
    try:
        data = json.loads(response)
        return {
            'duplicate_facts': data.get('duplicate_facts', []),
            'contradicted_facts': data.get('contradicted_facts', [])
        }
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse contradiction response: {e}")


def invalidate_facts(
    graph_db,
    fact_uuids: List[str],
    invalid_at: str = None,
    superseded_by: str = None
) -> int:
    """
    Mark facts as invalid by setting invalid_at timestamp and superseded_by field.

    Args:
        graph_db: GraphDatabase instance
        fact_uuids: List of fact UUIDs to invalidate
        invalid_at: Timestamp when facts became invalid (default: now)
        superseded_by: UUID of fact that supersedes these facts (optional)

    Returns:
        Number of facts invalidated
    """
    if invalid_at is None:
        invalid_at = datetime.now().isoformat()

    count = 0
    for uuid in fact_uuids:
        # Update the relationship's invalid_at timestamp and superseded_by field
        try:
            if superseded_by:
                graph_db.conn.execute("""
                    MATCH ()-[r:RELATES_TO {uuid: $uuid}]->()
                    SET r.invalid_at = timestamp($invalid_at),
                        r.superseded_by = $superseded_by
                """, {
                    "uuid": uuid,
                    "invalid_at": invalid_at,
                    "superseded_by": superseded_by,
                })
            else:
                graph_db.conn.execute("""
                    MATCH ()-[r:RELATES_TO {uuid: $uuid}]->()
                    SET r.invalid_at = timestamp($invalid_at)
                """, {
                    "uuid": uuid,
                    "invalid_at": invalid_at,
                })
            count += 1
        except Exception as e:
            print(f"Error invalidating fact {uuid}: {e}")

    return count
