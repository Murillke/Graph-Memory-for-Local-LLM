"""
Verify document integrity by checking if hash has changed since last import.

Usage:
    python scripts/verify_document.py --project PROJECT --file PATH

This script:
1. Calculates current hash of the document
2. Queries graph database for previous imports of this document
3. Compares hashes to detect if document has been modified
4. Reports verification status
"""

import sys
import os
sys.path.insert(0, '.')

import argparse
import hashlib
import json
from tools.graph_db import GraphDatabase

def calculate_file_hash(file_path):
    """Calculate SHA-256 hash of file"""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()

def main():
    parser = argparse.ArgumentParser(description="Verify document integrity by checking hash")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--file", required=True, help="Path to document file")
    parser.add_argument("--graph-db", help="Path to graph database (overrides config)")
    
    args = parser.parse_args()
    
    # Check file exists
    if not os.path.exists(args.file):
        print(f"[ERROR] File not found: {args.file}")
        sys.exit(1)
    
    # Calculate current hash
    print(f"Calculating hash for: {args.file}")
    current_hash = calculate_file_hash(args.file)
    print(f"Current hash: {current_hash}")
    
    # Get database path
    if args.graph_db:
        db_path = args.graph_db
    else:
        config_file = 'mem.config.json'
        if not os.path.exists(config_file):
            print(f"[ERROR] Config file not found: {config_file}")
            sys.exit(1)

        with open(config_file, 'r') as f:
            config = json.load(f)

        db_path = config['database']['graph_path']
    
    # Query database for previous imports
    print(f"\nQuerying database for previous imports...")
    db = GraphDatabase(db_path)
    
    # Search for Entity nodes with this file name and file_hash attribute
    file_name = os.path.basename(args.file)
    result = db.conn.execute("""
        MATCH (e:Entity)
        WHERE e.name CONTAINS $file_name
          AND e.attributes IS NOT NULL
        RETURN e.name, e.attributes, e.created_at
        ORDER BY e.created_at DESC
    """, {'file_name': file_name})
    
    found_documents = []
    while result.has_next():
        row = result.get_next()
        name, attributes, created_at = row[0], row[1], row[2]
        
        # Check if attributes contain file_hash
        if attributes and 'file_hash' in attributes:
            found_documents.append({
                'name': name,
                'hash': attributes['file_hash'],
                'created_at': created_at,
                'attributes': attributes
            })
    
    db.close()
    
    # Report results
    print(f"\n" + "="*80)
    print("VERIFICATION RESULTS")
    print("="*80)
    
    if not found_documents:
        print(f"\n[NOT FOUND] No previous imports found for '{file_name}'")
        print(f"This document has not been imported yet.")
        print(f"\nTo import: python scripts/import_document.py --project {args.project} --file {args.file}")
        sys.exit(0)
    
    print(f"\nFound {len(found_documents)} previous import(s):")
    
    all_match = True
    for i, doc in enumerate(found_documents, 1):
        print(f"\n{i}. {doc['name']}")
        print(f"   Imported: {doc['created_at']}")
        print(f"   Stored hash: {doc['hash']}")
        
        if doc['hash'] == current_hash:
            print(f"   [OK] Hash matches - document unchanged")
        else:
            print(f"   [MODIFIED] Hash mismatch - document has been modified!")
            all_match = False
    
    print(f"\n" + "="*80)
    if all_match:
        print("[SUCCESS] Document integrity verified - no changes detected")
        sys.exit(0)
    else:
        print("[WARNING] Document has been modified since last import!")
        print("The file content has changed. Consider re-importing if changes are intentional.")
        sys.exit(1)

if __name__ == '__main__':
    main()

