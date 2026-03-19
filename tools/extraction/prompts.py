"""
LLM prompts for entity and fact extraction.
Adapted from Graphiti (https://github.com/getzep/graphiti)
"""

from typing import Any, List, Dict
from pydantic import BaseModel, Field


# ============================================================
# Pydantic Models for Structured Output
# ============================================================

class ExtractedEntity(BaseModel):
    """Single extracted entity."""
    name: str = Field(..., description="Name of the extracted entity")
    type: str = Field(..., description="Type of entity (e.g., Person, Technology, Organization)")
    summary: str = Field(default="", description="Brief summary of the entity")


class ExtractedEntities(BaseModel):
    """List of extracted entities."""
    entities: List[ExtractedEntity] = Field(..., description="List of extracted entities")


class ExtractedFact(BaseModel):
    """Single extracted fact/relationship."""
    source_entity: str = Field(..., description="Name of the source entity (must match an extracted entity)")
    target_entity: str = Field(..., description="Name of the target entity (must match an extracted entity)")
    relationship_type: str = Field(..., description="Type of relationship in SCREAMING_SNAKE_CASE (e.g., USES, BUILT_WITH)")
    fact: str = Field(..., description="Natural language description of the relationship")
    valid_at: str = Field(default="", description="When this fact became true (ISO 8601 format)")
    invalid_at: str = Field(default="", description="When this fact stopped being true (ISO 8601 format)")


class ExtractedFacts(BaseModel):
    """List of extracted facts."""
    facts: List[ExtractedFact] = Field(..., description="List of extracted facts/relationships")


# ============================================================
# Entity Extraction Prompts (from Graphiti)
# ============================================================

def get_entity_extraction_prompt(
    current_message: str,
    previous_messages: List[str] = None,
    entity_types: List[str] = None
) -> List[Dict[str, str]]:
    """
    Get prompt for extracting entities from a conversation message.
    
    Adapted from Graphiti's extract_message() prompt.
    
    Args:
        current_message: The current message to extract entities from
        previous_messages: Previous messages for context (optional)
        entity_types: List of entity types to extract (optional)
    
    Returns:
        List of message dicts for LLM (system + user prompts)
    """
    if previous_messages is None:
        previous_messages = []
    
    if entity_types is None:
        entity_types = [
            "Person - A human being or AI assistant",
            "Technology - Software, framework, library, database, or tool",
            "Organization - Company, project, or group",
            "Concept - Abstract idea, methodology, or principle",
            "Document - File, documentation, or written resource"
        ]
    
    entity_types_str = "\n".join(f"- {et}" for et in entity_types)
    previous_messages_str = "\n".join(previous_messages) if previous_messages else "(No previous messages)"
    
    system_prompt = """You are an AI assistant that extracts entity nodes from conversational messages.
Your primary task is to extract and classify significant entities mentioned in the conversation."""
    
    user_prompt = f"""
<ENTITY TYPES>
{entity_types_str}
</ENTITY TYPES>

<PREVIOUS MESSAGES>
{previous_messages_str}
</PREVIOUS MESSAGES>

<CURRENT MESSAGE>
{current_message}
</CURRENT MESSAGE>

Instructions:

You are given a conversation context and a CURRENT MESSAGE. Your task is to extract **entity nodes** mentioned **explicitly or implicitly** in the CURRENT MESSAGE.

1. **Entity Identification**:
   - Extract all significant entities, concepts, or actors mentioned in the CURRENT MESSAGE
   - Include technologies, tools, people, organizations, concepts, and documents
   - Disambiguate pronouns to actual entity names when possible

2. **Entity Classification**:
   - Classify each entity using one of the ENTITY TYPES above
   - Choose the most specific type that fits

3. **Entity Summary**:
   - Provide a brief 1-sentence summary of what the entity is or does
   - Use information from the current and previous messages

4. **Exclusions**:
   - Do NOT extract relationships or actions (those will be extracted separately)
   - Do NOT extract dates, times, or temporal information
   - Do NOT extract pronouns like "you", "me", "he/she/they", "we/us"

5. **Formatting**:
   - Use full, unambiguous names (e.g., "React.js" not just "React" if that's clearer)
   - Be consistent with naming across the conversation

Respond with a JSON object containing an "entities" array.
"""
    
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]


# ============================================================
# Fact Extraction Prompts (from Graphiti)
# ============================================================

def get_fact_extraction_prompt(
    current_message: str,
    entities: List[str],
    previous_messages: List[str] = None,
    reference_time: str = None
) -> List[Dict[str, str]]:
    """
    Get prompt for extracting facts/relationships from a conversation message.
    
    Adapted from Graphiti's edge() prompt.
    
    Args:
        current_message: The current message to extract facts from
        entities: List of entity names that were extracted
        previous_messages: Previous messages for context (optional)
        reference_time: Reference timestamp for resolving relative dates (ISO 8601)
    
    Returns:
        List of message dicts for LLM (system + user prompts)
    """
    if previous_messages is None:
        previous_messages = []
    
    if reference_time is None:
        from datetime import datetime
        reference_time = datetime.now().isoformat() + "Z"
    
    entities_str = "\n".join(f"- {entity}" for entity in entities)
    previous_messages_str = "\n".join(previous_messages) if previous_messages else "(No previous messages)"
    
    system_prompt = """You are an expert fact extractor that extracts relationships between entities from text.
You extract facts with relevant temporal information (when they became true and when they stopped being true)."""
    
    user_prompt = f"""
<PREVIOUS MESSAGES>
{previous_messages_str}
</PREVIOUS MESSAGES>

<CURRENT MESSAGE>
{current_message}
</CURRENT MESSAGE>

<ENTITIES>
{entities_str}
</ENTITIES>

<REFERENCE_TIME>
{reference_time}
</REFERENCE_TIME>

# TASK
Extract all factual relationships between the given ENTITIES based on the CURRENT MESSAGE.

Only extract facts that:
- Involve two DISTINCT ENTITIES from the ENTITIES list above
- Are clearly stated or unambiguously implied in the CURRENT MESSAGE
- Can be represented as edges in a knowledge graph

You may use information from PREVIOUS MESSAGES only to disambiguate references or support continuity.

# EXTRACTION RULES

1. **Entity Name Validation**: 
   - source_entity and target_entity must use EXACT names from the ENTITIES list
   - Using names not in the list will cause the fact to be rejected

2. Each fact must involve two **distinct** entities

3. Do not emit duplicate or semantically redundant facts

4. The fact should closely paraphrase the original sentence(s) - do not quote verbatim

5. Use REFERENCE_TIME to resolve vague or relative temporal expressions (e.g., "last week", "recently")

6. Do NOT hallucinate or infer temporal bounds from unrelated events

# RELATIONSHIP TYPE RULES

- Derive relationship_type from the relationship predicate in SCREAMING_SNAKE_CASE
- Examples: USES, BUILT_WITH, WORKS_ON, CREATED_BY, DEPENDS_ON, IMPLEMENTS

# DATETIME RULES

- Use ISO 8601 with "Z" suffix (UTC) (e.g., 2025-04-30T00:00:00Z)
- If the fact is ongoing (present tense), set valid_at to REFERENCE_TIME
- If a change/termination is expressed, set invalid_at to the relevant timestamp
- Leave both fields empty if no explicit or resolvable time is stated
- If only a date is mentioned (no time), assume 00:00:00
- If only a year is mentioned, use January 1st at 00:00:00

Respond with a JSON object containing a "facts" array.
"""
    
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
