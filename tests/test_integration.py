#!/usr/bin/env python3
"""
Test Auggie integration with the memory system.

This simulates how Auggie would use the memory system during a conversation.
"""

import sys
import os
import json
import subprocess
import tempfile
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.sql_db import SQLDatabase
from tools.graph_db import GraphDatabase


class AuggieMemoryIntegration:
    """Integration layer between Auggie and the memory system."""
    
    def __init__(self, project_name: str, sql_db_path: str, graph_db_path: str, config_path: str):
        self.project_name = project_name
        self.sql_db_path = sql_db_path
        self.graph_db_path = graph_db_path
        self.config_path = config_path

    def _run(self, cmd: list) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["MEM_CONFIG"] = self.config_path
        return subprocess.run(cmd, capture_output=True, text=True, env=env)
    
    def store_interaction(self, user_message: str, assistant_message: str) -> dict:
        """Store a conversation interaction."""
        result = self._run(
            [
                sys.executable, "scripts/store_interaction.py",
                "--db", self.sql_db_path,
                "--project", self.project_name,
                "--user", user_message,
                "--assistant", assistant_message,
                "--json"
            ]
        )

        if result.returncode != 0:
            raise Exception(f"Failed to store interaction: {result.stderr}")

        return json.loads(result.stdout)

    def search_entities(self, query: str = "", labels: list = None) -> list:
        """Search for entities in the knowledge graph."""
        cmd = [
            sys.executable, "scripts/query_memory.py",
            "--db", self.graph_db_path,
            "--project", self.project_name,
            "--json"
        ]
        
        if query:
            search_file = Path("tmp/integration_search.txt")
            search_file.parent.mkdir(parents=True, exist_ok=True)
            search_file.write_text(query, encoding="utf-8")
            cmd.extend(["--search-file", str(search_file)])
        elif labels:
            cmd.extend(["--label", labels[0]])
        else:
            cmd.append("--all")
        
        result = self._run(cmd)
        
        if result.returncode != 0:
            raise Exception(f"Failed to search entities: {result.stderr}")
        
        return json.loads(result.stdout)
    
    def verify_integrity(self) -> bool:
        """Verify cryptographic integrity of the memory system."""
        result = self._run(
            [
                "python3", "scripts/verify_integrity.py",
                "--sql-db", self.sql_db_path,
                "--graph-db", self.graph_db_path,
                "--project", self.project_name,
                "--all"
            ]
        )
        
        return result.returncode == 0


def simulate_conversation():
    """Simulate a conversation between user and Auggie."""
    
    print("="*60)
    print("Simulating Auggie Conversation with Memory Integration")
    print("="*60)
    
    config_dir = tempfile.mkdtemp(prefix="integration-config-", dir="./tmp")
    config_path = os.path.join(config_dir, "mem.config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({
            "project_name": "integration-test",
            "python_path": "python3",
            "database": {
                "sql_path": "./tests/tmp/integration-test.db",
                "graph_path": "./tests/tmp/{project_name}.graph"
            },
            "paths": {
                "tmp_dir": "./tmp",
                "memory_dir": "./tests/tmp"
            }
        }, f, indent=2)

    # Initialize memory integration
    memory = AuggieMemoryIntegration(
        "integration-test",
        "./tests/tmp/integration-test.db",
        "./tests/tmp/integration-test.kuzu",
        config_path
    )
    
    # Conversation Turn 1
    print("\n[NOTE] Turn 1:")
    print("User: Let's build a web app with React and Node.js")
    
    assistant_response = "Great! I'll help you build a web app with React for the frontend and Node.js for the backend."
    print(f"Auggie: {assistant_response}")
    
    interaction1 = memory.store_interaction(
        "Let's build a web app with React and Node.js",
        assistant_response
    )
    print(f"[OK] Stored interaction {interaction1['uuid']}")
    
    # Manually create entities (in production, this would be done by extract_knowledge.py)
    # Note: We need to close the connection before subprocess can open it
    def create_entities():
        sql_db = SQLDatabase("./tests/tmp/integration-test.db")
        graph_db = GraphDatabase("./tests/tmp/integration-test.kuzu")

        graph_db.create_project_node("integration-test", "Integration test project")

        react_uuid = graph_db.create_entity(
            name="React",
            group_id="integration-test",
            source_interactions=[interaction1['uuid']],
            source_hashes=[interaction1['content_hash']],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary="Frontend framework",
            labels=["technology", "frontend"]
        )
        graph_db.link_project_to_entity("integration-test", react_uuid)

        nodejs_uuid = graph_db.create_entity(
            name="Node.js",
            group_id="integration-test",
            source_interactions=[interaction1['uuid']],
            source_hashes=[interaction1['content_hash']],
            extraction_version="v1.0.0",
            extraction_commit="test",
            summary="Backend runtime",
            labels=["technology", "backend"]
        )
        graph_db.link_project_to_entity("integration-test", nodejs_uuid)

        # Close connections
        graph_db.conn.close()
        graph_db.db.close()

    create_entities()
    print("[OK] Extracted 2 entities to graph")
    
    # Conversation Turn 2
    print("\n[NOTE] Turn 2:")
    print("User: What tech stack are we using?")
    
    # Query memory before responding
    entities = memory.search_entities(labels=["technology"])
    
    tech_names = [e['name'] for e in entities]
    assistant_response = f"We're using {' and '.join(tech_names)} for our web app."
    print(f"Auggie: {assistant_response}")
    print(f"  (Retrieved from memory: {len(entities)} entities)")
    
    interaction2 = memory.store_interaction(
        "What tech stack are we using?",
        assistant_response
    )
    print(f"[OK] Stored interaction {interaction2['uuid']}")
    
    # Conversation Turn 3
    print("\n[NOTE] Turn 3:")
    print("User: Can you verify the conversation history?")
    
    # Verify integrity
    verified = memory.verify_integrity()
    
    if verified:
        assistant_response = "[OK] Memory integrity verified! All interactions are intact with valid cryptographic proofs."
    else:
        assistant_response = "[ERROR] Warning: Memory integrity check failed!"
    
    print(f"Auggie: {assistant_response}")
    
    interaction3 = memory.store_interaction(
        "Can you verify the conversation history?",
        assistant_response
    )
    print(f"[OK] Stored interaction {interaction3['uuid']}")
    
    # Final summary
    print("\n" + "="*60)
    print("Conversation Summary")
    print("="*60)
    print(f"Total interactions: 3")
    print(f"Total entities: {len(entities)}")
    print(f"Integrity verified: {verified}")
    print("\n[OK] Integration test complete!")


if __name__ == '__main__':
    # Clean up any existing test data
    import shutil
    os.makedirs("./tests/tmp", exist_ok=True)
    for path in ["./tests/tmp/integration-test.db", "./tests/tmp/integration-test.kuzu"]:
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
    
    try:
        simulate_conversation()
    except Exception as e:
        print(f"\n[ERROR] Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

