"""
Code graph database management.

Manages a separate KuzuDB graph for tracking code evolution.
"""

import os
from pathlib import Path
from datetime import datetime

from tools.db_utils import open_kuzu_database


class CodeGraphDB:
    """Manages the code evolution graph database."""
    
    def __init__(self, project_name):
        """
        Initialize code graph database.

        Uses the SAME database as conversation graph, just different node/relationship tables.

        Args:
            project_name: Name of the project
        """
        self.project_name = project_name
        self.db_path = f"memory/{project_name}.graph"  # SAME database as conversation graph!
        self.schema_path = "schema/code_graph_schema.cypher"

        # Create database directory if needed
        os.makedirs("memory", exist_ok=True)

        # Initialize database
        self.db, self.conn = open_kuzu_database(self.db_path)

        # Create schema if needed
        self._initialize_schema()
    
    def _initialize_schema(self):
        """Create schema if it doesn't exist."""
        if not os.path.exists(self.schema_path):
            print(f"[ERROR] Schema file not found: {self.schema_path}")
            return

        # Read schema file
        with open(self.schema_path, 'r') as f:
            schema_sql = f.read()

        # Remove comment lines
        lines = []
        for line in schema_sql.split('\n'):
            # Skip lines that are only comments
            stripped = line.strip()
            if not stripped.startswith('--'):
                lines.append(line)

        schema_sql = '\n'.join(lines)

        # Execute each statement (split by semicolon)
        statements = [s.strip() for s in schema_sql.split(';') if s.strip()]

        for statement in statements:
            try:
                self.conn.execute(statement)
            except Exception as e:
                # Ignore "already exists" errors
                if "already exists" not in str(e).lower():
                    print(f"[WARN] Schema statement failed: {e}")
    
    def add_commit(self, commit_hash, message, author, author_email, timestamp, branch, parent_hashes=None):
        """
        Add a commit to the graph.
        
        Args:
            commit_hash: Git commit hash
            message: Commit message
            author: Author name
            author_email: Author email
            timestamp: Commit timestamp
            branch: Branch name
            parent_hashes: List of parent commit hashes
        
        Returns:
            bool: True if successful
        """
        try:
            parent_hashes = parent_hashes or []
            
            self.conn.execute("""
                CREATE (c:Commit {
                    hash: $hash,
                    message: $message,
                    author: $author,
                    author_email: $email,
                    timestamp: $timestamp,
                    branch: $branch,
                    parent_hashes: $parents
                })
            """, {
                'hash': commit_hash,
                'message': message,
                'author': author,
                'email': author_email,
                'timestamp': timestamp,
                'branch': branch,
                'parents': parent_hashes
            })
            
            return True
        except Exception as e:
            print(f"[ERROR] Failed to add commit: {e}")
            return False
    
    def add_file(self, file_path, language=None, extension=None):
        """
        Add or update a file in the graph.
        
        Args:
            file_path: Path to the file
            language: Programming language
            extension: File extension
        
        Returns:
            bool: True if successful
        """
        try:
            # Detect extension if not provided
            if extension is None:
                extension = Path(file_path).suffix
            
            self.conn.execute("""
                MERGE (f:File {path: $path})
                ON CREATE SET f.language = $language,
                             f.extension = $extension,
                             f.last_modified = current_timestamp()
                ON MATCH SET f.last_modified = current_timestamp()
            """, {
                'path': file_path,
                'language': language,
                'extension': extension
            })
            
            return True
        except Exception as e:
            print(f"[ERROR] Failed to add file: {e}")
            return False
    
    def add_function(self, func_id, name, signature, file_path, start_line, end_line, language):
        """
        Add a function to the graph.
        
        Args:
            func_id: Unique function ID
            name: Function name
            signature: Function signature
            file_path: Path to file containing function
            start_line: Starting line number
            end_line: Ending line number
            language: Programming language
        
        Returns:
            bool: True if successful
        """
        try:
            self.conn.execute("""
                CREATE (f:Function {
                    id: $id,
                    name: $name,
                    signature: $signature,
                    file_path: $file_path,
                    start_line: $start_line,
                    end_line: $end_line,
                    language: $language
                })
            """, {
                'id': func_id,
                'name': name,
                'signature': signature,
                'file_path': file_path,
                'start_line': start_line,
                'end_line': end_line,
                'language': language
            })
            
            return True
        except Exception as e:
            print(f"[ERROR] Failed to add function: {e}")
            return False

    def link_commit_modified_file(self, commit_hash, file_path, lines_added, lines_removed, change_type, old_path=None):
        """Link commit to modified file."""
        try:
            self.conn.execute("""
                MATCH (c:Commit {hash: $commit}), (f:File {path: $file})
                CREATE (c)-[:MODIFIED {
                    lines_added: $added,
                    lines_removed: $removed,
                    change_type: $type,
                    old_path: $old_path
                }]->(f)
            """, {
                'commit': commit_hash,
                'file': file_path,
                'added': lines_added,
                'removed': lines_removed,
                'type': change_type,
                'old_path': old_path
            })
            return True
        except Exception as e:
            print(f"[ERROR] Failed to link commit to file: {e}")
            return False

    def link_commit_added_function(self, commit_hash, func_id):
        """Link commit to added function."""
        try:
            self.conn.execute("""
                MATCH (c:Commit {hash: $commit}), (f:Function {id: $func})
                CREATE (c)-[:ADDED_FUNCTION]->(f)
            """, {'commit': commit_hash, 'func': func_id})
            return True
        except Exception as e:
            print(f"[ERROR] Failed to link commit to added function: {e}")
            return False

    def link_commit_removed_function(self, commit_hash, func_id):
        """Link commit to removed function."""
        try:
            self.conn.execute("""
                MATCH (c:Commit {hash: $commit}), (f:Function {id: $func})
                CREATE (c)-[:REMOVED_FUNCTION]->(f)
            """, {'commit': commit_hash, 'func': func_id})
            return True
        except Exception as e:
            print(f"[ERROR] Failed to link commit to removed function: {e}")
            return False

    def link_commit_modified_function(self, commit_hash, func_id, lines_changed):
        """Link commit to modified function."""
        try:
            self.conn.execute("""
                MATCH (c:Commit {hash: $commit}), (f:Function {id: $func})
                CREATE (c)-[:MODIFIED_FUNCTION {lines_changed: $lines}]->(f)
            """, {'commit': commit_hash, 'func': func_id, 'lines': lines_changed})
            return True
        except Exception as e:
            print(f"[ERROR] Failed to link commit to modified function: {e}")
            return False

    def link_file_contains_function(self, file_path, func_id):
        """Link file to function it contains."""
        try:
            self.conn.execute("""
                MATCH (f:File {path: $file}), (fn:Function {id: $func})
                CREATE (f)-[:CONTAINS]->(fn)
            """, {'file': file_path, 'func': func_id})
            return True
        except Exception as e:
            print(f"[ERROR] Failed to link file to function: {e}")
            return False

    def close(self):
        """Close database connection."""
        if hasattr(self, 'conn'):
            self.conn.close()
