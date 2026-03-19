"""
Automated knowledge extraction using LLM.

This module provides functions to automatically extract entities and facts
from conversation interactions using LLM capabilities.

NOTE: This is designed to be called by Auggie (the AI assistant) who will
use his own LLM capabilities to perform the extraction. No external API keys needed.
"""

import json
from typing import List, Dict, Any
from datetime import datetime

from tools.extraction.prompts import (
    get_entity_extraction_prompt,
    get_fact_extraction_prompt,
    ExtractedEntity,
    ExtractedFact
)


def format_interaction_for_extraction(interaction: Dict[str, Any]) -> str:
    """
    Format an interaction for extraction.

    Args:
        interaction: Interaction dict from SQL database

    Returns:
        Formatted string for LLM
    """
    user_msg = interaction.get('user_message', '')
    assistant_msg = interaction.get('assistant_message', '')
    timestamp = interaction.get('timestamp', '')

    return f"""Timestamp: {timestamp}

User: {user_msg}

Assistant: {assistant_msg}"""


def get_entity_extraction_instructions(interaction: Dict[str, Any]) -> str:
    """
    Get instructions for Auggie to extract entities from an interaction.

    This returns a prompt that Auggie can use to extract entities using his own LLM.

    Args:
        interaction: Interaction dict from SQL database

    Returns:
        Instructions string for Auggie
    """
    formatted_interaction = format_interaction_for_extraction(interaction)
    prompts = get_entity_extraction_prompt(formatted_interaction)

    instructions = f"""Please extract entities from this interaction using your LLM capabilities.

{prompts[0]['content']}

{prompts[1]['content']}

Respond with ONLY a JSON object in this exact format:
{{
  "entities": [
    {{
      "name": "Entity Name",
      "type": "Technology",
      "summary": "Brief description"
    }}
  ]
}}"""

    return instructions


def get_fact_extraction_instructions(
    interaction: Dict[str, Any],
    entities: List[str]
) -> str:
    """
    Get instructions for Auggie to extract facts from an interaction.

    Args:
        interaction: Interaction dict from SQL database
        entities: List of entity names that were extracted

    Returns:
        Instructions string for Auggie
    """
    formatted_interaction = format_interaction_for_extraction(interaction)
    reference_time = interaction.get('timestamp', datetime.now().isoformat())
    prompts = get_fact_extraction_prompt(
        formatted_interaction,
        entities,
        reference_time=reference_time
    )

    instructions = f"""Please extract facts/relationships from this interaction using your LLM capabilities.

{prompts[0]['content']}

{prompts[1]['content']}

Respond with ONLY a JSON object in this exact format:
{{
  "facts": [
    {{
      "source_entity": "Entity A",
      "target_entity": "Entity B",
      "relationship_type": "USES",
      "fact": "Entity A uses Entity B for something",
      "valid_at": "{reference_time}",
      "invalid_at": null
    }}
  ]
}}"""

    return instructions


def parse_entity_extraction_response(response: str) -> List[Dict[str, Any]]:
    """
    Parse Auggie's entity extraction response.

    Args:
        response: JSON string from Auggie

    Returns:
        List of entity dicts
    """
    try:
        data = json.loads(response)
        return data.get('entities', [])
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse entity extraction response: {e}")


def parse_fact_extraction_response(response: str) -> List[Dict[str, Any]]:
    """
    Parse Auggie's fact extraction response.

    Args:
        response: JSON string from Auggie

    Returns:
        List of fact dicts
    """
    try:
        data = json.loads(response)
        return data.get('facts', [])
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse fact extraction response: {e}")
