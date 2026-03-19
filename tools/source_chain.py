#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Source Chain Builder

Builds hash chain from SQL interactions for storage in graph entities.
This allows the graph to be verified independently of SQL.
"""

import json
from typing import List, Dict, Optional
from tools.sql_db import SQLDatabase


def build_source_chain_from_interactions(sql_db: SQLDatabase, interaction_uuids: List[str]) -> List[Dict[str, str]]:
    """
    Build source chain from interaction UUIDs.

    Args:
        sql_db: SQL database connection
        interaction_uuids: List of interaction UUIDs

    Returns:
        List of dicts with 'hash' and 'previous_hash' for each interaction
    """
    if not interaction_uuids:
        return []

    chain = []

    for uuid in interaction_uuids:
        # Get interaction from SQL using the database's method
        interaction = sql_db.get_interaction_by_uuid(uuid)

        if interaction:
            chain.append({
                'hash': interaction['content_hash'],
                'previous_hash': interaction['previous_hash'] if interaction['previous_hash'] else None
            })

    return chain


def verify_source_chain(source_chain: List[Dict[str, str]]) -> tuple:
    """
    Verify that a source chain is valid.
    
    Args:
        source_chain: List of dicts with 'hash' and 'previous_hash'
        
    Returns:
        tuple: (valid: bool, message: str)
    """
    if not source_chain:
        return True, "Empty chain (valid)"
    
    # First item should have no previous_hash or it should be null
    if source_chain[0]['previous_hash'] not in [None, 'None', '']:
        # This is OK - it links to an earlier interaction
        pass
    
    # Verify chain links
    for i in range(1, len(source_chain)):
        expected_previous = source_chain[i-1]['hash']
        actual_previous = source_chain[i]['previous_hash']
        
        if actual_previous != expected_previous:
            return False, f"Chain broken at index {i}: expected previous_hash={expected_previous}, got {actual_previous}"
    
    return True, f"Chain valid ({len(source_chain)} items)"


def get_chain_root_hash(source_chain: List[Dict[str, str]]) -> Optional[str]:
    """
    Get the root hash of a chain (first item's hash).
    
    Args:
        source_chain: List of dicts with 'hash' and 'previous_hash'
        
    Returns:
        str: Root hash, or None if chain is empty
    """
    if not source_chain:
        return None
    
    return source_chain[0]['hash']


def get_chain_tip_hash(source_chain: List[Dict[str, str]]) -> Optional[str]:
    """
    Get the tip hash of a chain (last item's hash).
    
    Args:
        source_chain: List of dicts with 'hash' and 'previous_hash'
        
    Returns:
        str: Tip hash, or None if chain is empty
    """
    if not source_chain:
        return None
    
    return source_chain[-1]['hash']


def merge_source_chains(chains: List[List[Dict[str, str]]]) -> List[Dict[str, str]]:
    """
    Merge multiple source chains into one.
    
    Useful when an entity is extracted from multiple interactions.
    
    Args:
        chains: List of source chains
        
    Returns:
        Merged chain (deduplicated, ordered)
    """
    # Flatten all chains
    all_items = []
    seen_hashes = set()
    
    for chain in chains:
        for item in chain:
            if item['hash'] not in seen_hashes:
                all_items.append(item)
                seen_hashes.add(item['hash'])
    
    # Sort by chain order (items with previous_hash come after their parent)
    # This is a simple topological sort
    sorted_items = []
    remaining = all_items.copy()
    
    while remaining:
        # Find items whose previous_hash is either None or already in sorted_items
        added_this_round = []
        
        for item in remaining:
            if item['previous_hash'] is None or item['previous_hash'] == '':
                # Root item
                sorted_items.append(item)
                added_this_round.append(item)
            else:
                # Check if parent is in sorted_items
                parent_hashes = [i['hash'] for i in sorted_items]
                if item['previous_hash'] in parent_hashes:
                    sorted_items.append(item)
                    added_this_round.append(item)
        
        # Remove added items from remaining
        for item in added_this_round:
            remaining.remove(item)
        
        # If we didn't add anything this round, we have a broken chain
        if not added_this_round and remaining:
            # Just append remaining items (chain might be broken)
            sorted_items.extend(remaining)
            break
    
    return sorted_items

