#!/usr/bin/env python3
"""
Read-only interface to the SQL database.

This class provides ONLY read operations - no writes allowed.
Use this for querying the database without risk of modification.

For write operations, use SQLDatabase class with proper authorization.
"""

import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime


class SQLDatabaseReadOnly:
    """
    Read-only interface to the conversation database.
    
    This class provides safe read-only access to the database.
    All write operations will raise PermissionError.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize read-only connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        # Open in read-only mode
        self.conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row
    
    def _get_connection(self):
        """Get read-only connection."""
        return self.conn
    
    # ========================================================================
    # READ OPERATIONS (ALLOWED)
    # ========================================================================
    
    def get_project_by_name(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Get project by name."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT name, description, created_at FROM projects WHERE name = ?",
            (project_name,)
        )
        row = cursor.fetchone()
        
        if row:
            return {
                "name": row[0],
                "description": row[1],
                "created_at": row[2]
            }
        return None
    
    def get_project_from_path(self, path: str) -> Optional[str]:
        """Look up which project a path belongs to."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT project_name FROM project_paths WHERE path = ?",
            (path,)
        )
        row = cursor.fetchone()
        
        return row["project_name"] if row else None
    
    def get_project_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """Get project by path (returns full project dict)."""
        project_name = self.get_project_from_path(path)
        if project_name:
            return self.get_project_by_name(project_name)
        return None
    
    def get_interaction_by_uuid(self, uuid: str) -> Optional[Dict[str, Any]]:
        """Get a single interaction by UUID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT uuid, project_name, user_message, assistant_message,
                   timestamp, content_hash, previous_hash, chain_index
            FROM interactions
            WHERE uuid = ?
        """, (uuid,))
        
        row = cursor.fetchone()
        
        if row:
            return {
                "uuid": row[0],
                "project_name": row[1],
                "user_message": row[2],
                "assistant_message": row[3],
                "timestamp": row[4],
                "content_hash": row[5],
                "previous_hash": row[6],
                "chain_index": row[7]
            }
        return None
    
    def get_all_interactions(self, project_name: str) -> List[Dict[str, Any]]:
        """Get all interactions for a project (for rebuild)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT uuid, project_name, user_message, assistant_message,
                   timestamp, content_hash, previous_hash, chain_index
            FROM interactions
            WHERE project_name = ?
            ORDER BY chain_index ASC
        """, (project_name,))
        
        interactions = []
        for row in cursor.fetchall():
            interactions.append({
                "uuid": row[0],
                "project_name": row[1],
                "user_message": row[2],
                "assistant_message": row[3],
                "timestamp": row[4],
                "content_hash": row[5],
                "previous_hash": row[6],
                "chain_index": row[7]
            })
        
        return interactions
    
    def get_unprocessed_interactions(self, project_name: str) -> List[Dict[str, Any]]:
        """Get interactions that haven't been extracted yet."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT uuid, project_name, user_message, assistant_message,
                   timestamp, content_hash, previous_hash, chain_index
            FROM interactions
            WHERE project_name = ? AND extracted = 0
            ORDER BY chain_index ASC
        """, (project_name,))
        
        interactions = []
        for row in cursor.fetchall():
            interactions.append({
                "uuid": row[0],
                "project_name": row[1],
                "user_message": row[2],
                "assistant_message": row[3],
                "timestamp": row[4],
                "content_hash": row[5],
                "previous_hash": row[6],
                "chain_index": row[7]
            })
        
        return interactions
    
    def verify_interaction_chain(self, project_name: str) -> Dict[str, Any]:
        """
        Verify the hash chain for a project.
        
        This is a READ operation - it only checks integrity, doesn't modify.
        """
        from tools.sql_db import SQLDatabase
        
        # Use the full SQLDatabase class for verification
        # (it only reads, doesn't write)
        temp_db = SQLDatabase(self.db_path)
        result = temp_db.verify_interaction_chain(project_name)
        
        return result
    
    # ========================================================================
    # WRITE OPERATIONS (BLOCKED)
    # ========================================================================
    
    def create_project(self, *args, **kwargs):
        """BLOCKED: Use SQLDatabase with proper authorization."""
        raise PermissionError("Write operation not allowed on read-only connection. Use SQLDatabase class.")
    
    def store_interaction(self, *args, **kwargs):
        """BLOCKED: Use SQLDatabase with proper authorization."""
        raise PermissionError("Write operation not allowed on read-only connection. Use SQLDatabase class.")
    
    def associate_path_with_project(self, *args, **kwargs):
        """BLOCKED: Use SQLDatabase with proper authorization."""
        raise PermissionError("Write operation not allowed on read-only connection. Use SQLDatabase class.")
    
    def mark_interactions_as_extracted(self, *args, **kwargs):
        """BLOCKED: Use SQLDatabase with proper authorization."""
        raise PermissionError("Write operation not allowed on read-only connection. Use SQLDatabase class.")

