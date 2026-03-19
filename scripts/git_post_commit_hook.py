#!/usr/bin/env python3
"""
Git post-commit hook to capture code changes in the code graph.

This script is called automatically after each git commit.
It extracts commit metadata and code changes, then stores them in the code graph.
"""

import sys
import os
import subprocess
import hashlib
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.code_graph import CodeGraphDB


def get_commit_info():
    """Get information about the latest commit."""
    try:
        # Get commit hash
        commit_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        
        # Get commit message
        message = subprocess.check_output(['git', 'log', '-1', '--pretty=%B'], text=True).strip()
        
        # Get author
        author = subprocess.check_output(['git', 'log', '-1', '--pretty=%an'], text=True).strip()
        author_email = subprocess.check_output(['git', 'log', '-1', '--pretty=%ae'], text=True).strip()
        
        # Get timestamp
        timestamp_str = subprocess.check_output(['git', 'log', '-1', '--pretty=%aI'], text=True).strip()
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        
        # Get branch
        branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], text=True).strip()
        
        # Get parent hashes
        parent_output = subprocess.check_output(['git', 'log', '-1', '--pretty=%P'], text=True).strip()
        parent_hashes = parent_output.split() if parent_output else []
        
        return {
            'hash': commit_hash,
            'message': message,
            'author': author,
            'author_email': author_email,
            'timestamp': timestamp,
            'branch': branch,
            'parent_hashes': parent_hashes
        }
    except Exception as e:
        print(f"[ERROR] Failed to get commit info: {e}", file=sys.stderr)
        return None


def get_changed_files(commit_hash):
    """Get list of files changed in the commit."""
    try:
        # Get diff stats
        output = subprocess.check_output(
            ['git', 'diff-tree', '--no-commit-id', '--numstat', '-r', commit_hash],
            text=True
        )
        
        files = []
        for line in output.strip().split('\n'):
            if not line:
                continue
            
            parts = line.split('\t')
            if len(parts) >= 3:
                added = parts[0]
                removed = parts[1]
                path = parts[2]
                
                # Determine change type
                if added == '-' and removed == '-':
                    change_type = 'binary'
                elif added == '0' and removed != '0':
                    change_type = 'deleted'
                elif added != '0' and removed == '0':
                    change_type = 'added'
                else:
                    change_type = 'modified'
                
                files.append({
                    'path': path,
                    'lines_added': int(added) if added.isdigit() else 0,
                    'lines_removed': int(removed) if removed.isdigit() else 0,
                    'change_type': change_type
                })
        
        return files
    except Exception as e:
        print(f"[ERROR] Failed to get changed files: {e}", file=sys.stderr)
        return []


def detect_language(file_path):
    """Detect programming language from file extension."""
    ext_map = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.ts': 'TypeScript',
        '.java': 'Java',
        '.cpp': 'C++',
        '.c': 'C',
        '.h': 'C/C++ Header',
        '.cs': 'C#',
        '.go': 'Go',
        '.rs': 'Rust',
        '.rb': 'Ruby',
        '.php': 'PHP',
        '.swift': 'Swift',
        '.kt': 'Kotlin',
        '.md': 'Markdown',
        '.json': 'JSON',
        '.yaml': 'YAML',
        '.yml': 'YAML',
        '.sql': 'SQL',
        '.sh': 'Shell',
        '.ps1': 'PowerShell',
        '.cypher': 'Cypher'
    }
    
    ext = os.path.splitext(file_path)[1].lower()
    return ext_map.get(ext, 'Unknown')


def main():
    """Main hook execution."""
    print("[INFO] Running post-commit hook...")
    
    # Get project name from config or default
    project_name = os.environ.get('LLM_MEMORY_PROJECT', 'llm_memory')
    
    # Get commit info
    commit_info = get_commit_info()
    if not commit_info:
        print("[ERROR] Failed to get commit info", file=sys.stderr)
        return 1
    
    print(f"[INFO] Processing commit: {commit_info['hash'][:8]}")
    print(f"[INFO] Message: {commit_info['message'][:50]}...")
    
    # Initialize code graph
    try:
        code_graph = CodeGraphDB(project_name)
    except Exception as e:
        print(f"[ERROR] Failed to initialize code graph: {e}", file=sys.stderr)
        return 1
    
    # Add commit to graph
    success = code_graph.add_commit(
        commit_info['hash'],
        commit_info['message'],
        commit_info['author'],
        commit_info['author_email'],
        commit_info['timestamp'],
        commit_info['branch'],
        commit_info['parent_hashes']
    )
    
    if not success:
        print("[ERROR] Failed to add commit to graph", file=sys.stderr)
        code_graph.close()
        return 1
    
    # Get changed files
    changed_files = get_changed_files(commit_info['hash'])
    print(f"[INFO] Changed files: {len(changed_files)}")
    
    # Add files and link to commit
    for file_info in changed_files:
        file_path = file_info['path']
        language = detect_language(file_path)
        extension = os.path.splitext(file_path)[1]
        
        # Add file
        code_graph.add_file(file_path, language, extension)
        
        # Link commit to file
        code_graph.link_commit_modified_file(
            commit_info['hash'],
            file_path,
            file_info['lines_added'],
            file_info['lines_removed'],
            file_info['change_type']
        )
    
    code_graph.close()
    print("[SUCCESS] Code graph updated!")
    return 0


if __name__ == '__main__':
    sys.exit(main())

