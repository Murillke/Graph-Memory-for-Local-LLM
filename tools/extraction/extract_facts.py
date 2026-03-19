"""
Fact/relationship extraction using LLM.
Adapted from Graphiti's edge extraction logic.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from .llm_client import LLMClient, get_default_client
from .prompts import (
    get_fact_extraction_prompt,
    ExtractedFacts,
    ExtractedFact
)


def extract_facts_from_interaction(
    user_message: str,
    assistant_message: str,
    entities: List[str],
    previous_interactions: List[Dict[str, str]] = None,
    reference_time: Optional[str] = None,
    llm_client: Optional[LLMClient] = None
) -> List[Dict[str, Any]]:
    """
    Extract facts/relationships from a conversation interaction using LLM.
    
    Args:
        user_message: User's message
        assistant_message: Assistant's response
        entities: List of entity names that were extracted
        previous_interactions: Previous interactions for context (optional)
        reference_time: Reference timestamp for resolving relative dates (ISO 8601)
        llm_client: LLM client to use (optional)
    
    Returns:
        List of extracted facts with metadata:
        [
            {
                "source_entity": "LadybugDB",
                "target_entity": "Python",
                "relationship_type": "BUILT_WITH",
                "fact": "LadybugDB is built with Python",
                "valid_at": "2026-03-01T00:00:00Z",
                "invalid_at": "",
                "derivation_timestamp": "2026-03-01T10:00:00Z"
            },
            ...
        ]
    """
    if llm_client is None:
        llm_client = get_default_client()
    
    if reference_time is None:
        reference_time = datetime.now().isoformat() + "Z"
    
    # Format current message
    current_message = f"User: {user_message}\nAssistant: {assistant_message}"
    
    # Format previous messages for context
    previous_messages = []
    if previous_interactions:
        for interaction in previous_interactions[-3:]:  # Last 3 for context
            prev_msg = f"User: {interaction.get('user_message', '')}\n"
            prev_msg += f"Assistant: {interaction.get('assistant_message', '')}"
            previous_messages.append(prev_msg)
    
    # Get extraction prompt
    messages = get_fact_extraction_prompt(
        current_message=current_message,
        entities=entities,
        previous_messages=previous_messages,
        reference_time=reference_time
    )
    
    # Call LLM with structured output
    try:
        result = llm_client.call(
            messages=messages,
            response_format=ExtractedFacts,
            temperature=0.0
        )
        
        # Convert to dict format with metadata
        derivation_timestamp = datetime.now().isoformat() + "Z"
        
        facts = []
        for fact in result.facts:
            facts.append({
                "source_entity": fact.source_entity,
                "target_entity": fact.target_entity,
                "relationship_type": fact.relationship_type,
                "fact": fact.fact,
                "valid_at": fact.valid_at or reference_time,
                "invalid_at": fact.invalid_at or "",
                "derivation_timestamp": derivation_timestamp
            })
        
        return facts
    
    except Exception as e:
        print(f"Error extracting facts: {e}")
        return []


def extract_facts_batch(
    interactions: List[Dict[str, str]],
    entities_by_interaction: Dict[str, List[Dict[str, Any]]],
    llm_client: Optional[LLMClient] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract facts from multiple interactions.
    
    Args:
        interactions: List of interaction dicts with 'uuid', 'user_message', 'assistant_message'
        entities_by_interaction: Dict mapping interaction UUID to list of extracted entities
        llm_client: LLM client to use (optional)
    
    Returns:
        Dict mapping interaction UUID to list of extracted facts:
        {
            "uuid-123": [{"source_entity": "LadybugDB", ...}, ...],
            "uuid-456": [{"source_entity": "React", ...}, ...],
            ...
        }
    """
    if llm_client is None:
        llm_client = get_default_client()
    
    results = {}
    
    for i, interaction in enumerate(interactions):
        uuid = interaction.get('uuid', f'interaction-{i}')
        
        # Get entities for this interaction
        entities = entities_by_interaction.get(uuid, [])
        entity_names = [e['name'] for e in entities]
        
        if not entity_names:
            print(f"[WARNING]  No entities for interaction {i+1}/{len(interactions)}, skipping fact extraction")
            results[uuid] = []
            continue
        
        # Get previous interactions for context
        previous = interactions[max(0, i-3):i] if i > 0 else []
        
        # Get reference time from interaction
        reference_time = interaction.get('timestamp')
        
        # Extract facts
        facts = extract_facts_from_interaction(
            user_message=interaction['user_message'],
            assistant_message=interaction['assistant_message'],
            entities=entity_names,
            previous_interactions=previous,
            reference_time=reference_time,
            llm_client=llm_client
        )
        
        results[uuid] = facts
        
        print(f"[OK] Extracted {len(facts)} facts from interaction {i+1}/{len(interactions)}")
    
    return results


# ============================================================
# Testing
# ============================================================

def test_extraction():
    """Test fact extraction with a sample interaction."""
    print("Testing fact extraction...")
    
    user_msg = "We're using React and Python to build LadybugDB"
    assistant_msg = "Great! React is perfect for the frontend and Python for the backend."
    entities = ["React", "Python", "LadybugDB"]
    
    facts = extract_facts_from_interaction(user_msg, assistant_msg, entities)
    
    print(f"\nExtracted {len(facts)} facts:")
    for fact in facts:
        print(f"  - {fact['source_entity']} --[{fact['relationship_type']}]--> {fact['target_entity']}")
        print(f"    Fact: {fact['fact']}")
    
    return len(facts) > 0


if __name__ == "__main__":
    test_extraction()

