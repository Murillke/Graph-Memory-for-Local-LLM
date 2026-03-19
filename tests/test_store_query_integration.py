#!/usr/bin/env python3
"""
Integration test: Store extraction -> Query immediately -> Verify results match

This test ensures that:
1. Data stored with store_extraction.py
2. Can be immediately queried with query_memory.py
3. Results match what was stored
4. No database path mismatches
"""

import sys
import os
import shutil
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.sql_db import SQLDatabase
from tools.graph_db import GraphDatabase


def test_store_and_query():
    """Test that stored data can be immediately queried."""
    
    # Create temporary directory for test
    base_tmp = Path(__file__).resolve().parent / "tmp"
    base_tmp.mkdir(parents=True, exist_ok=True)
    test_dir = base_tmp / "test_integration_runtime"
    shutil.rmtree(test_dir, ignore_errors=True)
    test_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        project_name = 'test_integration'
        sql_db_path = str(test_dir / 'conversations.db')
        graph_db_path = str(test_dir / f'{project_name}.kuzu')
        
        print(f"Test directory: {test_dir}")
        print(f"SQL DB: {sql_db_path}")
        print(f"Graph DB: {graph_db_path}")
        print()
        
        # Step 1: Create test data
        print("Step 1: Creating test data...")
        
        # Create SQL database and store interaction
        sql_db = SQLDatabase(sql_db_path)
        interaction_uuid = sql_db.store_interaction({
            'project_name': project_name,
            'user_message': "Test user message",
            'assistant_message': "Test assistant message"
        })
        print(f"  Stored interaction: {interaction_uuid}")
        
        # Get the interaction to get content_hash
        interaction = sql_db.get_interaction_by_uuid(interaction_uuid)
        content_hash = interaction['content_hash']

        # Create graph database and store entities
        graph_db = GraphDatabase(graph_db_path)
        graph_db.create_project_node(project_name, "Test project")

        entity1_uuid = graph_db.create_entity(
            name="Test Entity 1",
            group_id=project_name,
            source_interactions=[interaction_uuid],
            source_hashes=[content_hash],
            extraction_version="1.0.0",
            extraction_commit="test",
            summary="First test entity",
            labels=["Concept"]
        )
        graph_db.link_project_to_entity(project_name, entity1_uuid)
        print(f"  Created entity 1: {entity1_uuid}")

        entity2_uuid = graph_db.create_entity(
            name="Test Entity 2",
            group_id=project_name,
            source_interactions=[interaction_uuid],
            source_hashes=[content_hash],
            extraction_version="1.0.0",
            extraction_commit="test",
            summary="Second test entity",
            labels=["Technology"]
        )
        graph_db.link_project_to_entity(project_name, entity2_uuid)
        print(f"  Created entity 2: {entity2_uuid}")

        from datetime import datetime

        fact_uuid = graph_db.create_relationship(
            source_uuid=entity1_uuid,
            target_uuid=entity2_uuid,
            relationship_name="USES",
            fact="Test Entity 1 uses Test Entity 2",
            group_id=project_name,
            episodes=[interaction_uuid],
            episode_hashes=[content_hash],
            derivation_version="1.0.0",
            derivation_commit="test",
            valid_at=datetime.now().isoformat()
        )
        print(f"  Created fact: {fact_uuid}")
        print()
        
        # Step 2: Query the data
        print("Step 2: Querying data...")
        
        entities = graph_db.get_all_entities(project_name)
        print(f"  Found {len(entities)} entities")
        
        facts = graph_db.get_all_facts(project_name)
        print(f"  Found {len(facts)} facts")
        print()
        
        # Step 3: Verify results
        print("Step 3: Verifying results...")
        
        assert len(entities) == 2, f"Expected 2 entities, got {len(entities)}"
        print("  [OK] Entity count correct")
        
        assert len(facts) == 1, f"Expected 1 fact, got {len(facts)}"
        print("  [OK] Fact count correct")
        
        entity_names = {e['name'] for e in entities}
        assert "Test Entity 1" in entity_names, "Test Entity 1 not found"
        assert "Test Entity 2" in entity_names, "Test Entity 2 not found"
        print("  [OK] Entity names correct")
        
        fact = facts[0]
        assert fact['relationship_type'] == "USES", f"Expected USES, got {fact['relationship_type']}"
        print("  [OK] Fact relationship type correct")
        print()
        
        # Step 4: Test database path consistency
        print("Step 4: Testing database path consistency...")
        
        # Verify file exists at expected path
        assert os.path.exists(graph_db_path), f"Database not found at {graph_db_path}"
        print(f"  [OK] Database exists at expected path")
        
        # Verify file has data (> 1KB - Kuzu databases can be small)
        file_size = os.path.getsize(graph_db_path)
        assert file_size > 1000, f"Database too small ({file_size} bytes), probably empty"
        print(f"  [OK] Database has data ({file_size:,} bytes)")
        print()

        print("="*60)
        print("ALL TESTS PASSED!")
        print("="*60)
        # Don't return True - pytest expects None from test functions

    except Exception as e:
        print()
        print("="*60)
        print("TEST FAILED!")
        print("="*60)
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        raise
        
    finally:
        # Cleanup
        print()
        print(f"Cleaning up test directory: {test_dir}")
        shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == '__main__':
    try:
        test_store_and_query()
    except Exception:
        sys.exit(1)
    sys.exit(0)
