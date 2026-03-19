"""
Entity extraction using LLM.
Adapted from Graphiti's entity extraction logic.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from .llm_client import LLMClient, get_default_client
from .prompts import (
    get_entity_extraction_prompt,
    ExtractedEntities,
    ExtractedEntity
)


def extract_entities_from_interaction(
    user_message: str,
    assistant_message: str,
    previous_interactions: List[Dict[str, str]] = None,
    llm_client: Optional[LLMClient] = None
) -> List[Dict[str, Any]]:
    """
    Extract entities from a conversation interaction using LLM.
    
    Args:
        user_message: User's message
        assistant_message: Assistant's response
        previous_interactions: Previous interactions for context (optional)
        llm_client: LLM client to use (optional, will create default if not provided)
    
    Returns:
        List of extracted entities with metadata:
        [
            {
                "name": "React",
                "type": "Technology",
                "summary": "A JavaScript library for building user interfaces",
                "extraction_timestamp": "2026-03-01T10:00:00Z"
            },
            ...
        ]
    """
    if llm_client is None:
        llm_client = get_default_client()
    
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
    messages = get_entity_extraction_prompt(
        current_message=current_message,
        previous_messages=previous_messages
    )
    
    # Call LLM with structured output
    try:
        result = llm_client.call(
            messages=messages,
            response_format=ExtractedEntities,
            temperature=0.0
        )
        
        # Convert to dict format with metadata
        extraction_timestamp = datetime.now().isoformat() + "Z"
        
        entities = []
        for entity in result.entities:
            entities.append({
                "name": entity.name,
                "type": entity.type,
                "summary": entity.summary or "",
                "extraction_timestamp": extraction_timestamp
            })
        
        return entities
    
    except Exception as e:
        print(f"Error extracting entities: {e}")
        return []


def extract_entities_batch(
    interactions: List[Dict[str, str]],
    llm_client: Optional[LLMClient] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract entities from multiple interactions.
    
    Args:
        interactions: List of interaction dicts with 'uuid', 'user_message', 'assistant_message'
        llm_client: LLM client to use (optional)
    
    Returns:
        Dict mapping interaction UUID to list of extracted entities:
        {
            "uuid-123": [{"name": "React", ...}, ...],
            "uuid-456": [{"name": "Python", ...}, ...],
            ...
        }
    """
    if llm_client is None:
        llm_client = get_default_client()
    
    results = {}
    
    for i, interaction in enumerate(interactions):
        uuid = interaction.get('uuid', f'interaction-{i}')
        
        # Get previous interactions for context
        previous = interactions[max(0, i-3):i] if i > 0 else []
        
        # Extract entities
        entities = extract_entities_from_interaction(
            user_message=interaction['user_message'],
            assistant_message=interaction['assistant_message'],
            previous_interactions=previous,
            llm_client=llm_client
        )
        
        results[uuid] = entities
        
        print(f"[OK] Extracted {len(entities)} entities from interaction {i+1}/{len(interactions)}")
    
    return results


# ============================================================
# Testing
# ============================================================

def test_extraction():
    """Test entity extraction with a sample interaction."""
    print("Testing entity extraction...")
    
    user_msg = "We're using React and Python to build LadybugDB"
    assistant_msg = "Great! React is perfect for the frontend and Python for the backend."
    
    entities = extract_entities_from_interaction(user_msg, assistant_msg)
    
    print(f"\nExtracted {len(entities)} entities:")
    for entity in entities:
        print(f"  - {entity['name']} ({entity['type']}): {entity['summary']}")
    
    return len(entities) > 0


if __name__ == "__main__":
    test_extraction()

