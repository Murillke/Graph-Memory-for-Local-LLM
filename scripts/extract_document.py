#!/usr/bin/env python3
"""
Extract knowledge from imported document using AI.

Usage:
    python scripts/extract_document.py \\
        --project llm_memory \\
        --source-uuid uuid-abc123
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.graph_db import GraphDatabase
from tools.extraction.llm_client import get_default_client
import argparse
import json
import subprocess


def safe_print(text):
    """Print with encoding fallback for Windows."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))


def extract_document(project_name: str, source_uuid: str):
    """Extract knowledge from document using AI."""
    
    safe_print(f"\n{'='*80}")
    safe_print(f"EXTRACTING KNOWLEDGE FROM DOCUMENT")
    safe_print(f"{'='*80}\n")
    
    # Get ExternalSource from graph
    safe_print("[1/5] Loading document metadata...")
    db_path = f"./memory/{project_name}.kuzu"
    db = GraphDatabase(db_path)
    
    try:
        external_source = db.get_entity_by_uuid(source_uuid)
        if not external_source:
            raise ValueError(f"ExternalSource not found: {source_uuid}")
        
        doc_name = external_source['name']
        safe_print(f"   Document: {doc_name}")
        
    finally:
        db.close()
    
    # Load content
    safe_print(f"\n[2/5] Loading extracted content...")
    content_file = Path(f"./tmp/{source_uuid}_content.txt")
    if not content_file.exists():
        raise FileNotFoundError(f"Content file not found: {content_file}")
    
    with open(content_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    safe_print(f"   Loaded {len(content)} characters")
    
    # Load extraction prompt
    safe_print(f"\n[3/5] Calling AI for extraction...")
    prompt_file = Path("prompts/extract-entities.md")
    with open(prompt_file, 'r', encoding='utf-8') as f:
        extraction_prompt = f.read()

    # Prepare messages for extraction
    messages = [
        {"role": "system", "content": extraction_prompt},
        {"role": "user", "content": f"""Document: {doc_name}

Content:
{content}

Please extract entities and facts from this document. Return ONLY valid JSON."""}
    ]

    # Call LLM
    llm_client = get_default_client()
    response = llm_client.call_with_json(messages)

    safe_print(f"   AI extraction complete")
    
    # Parse response
    safe_print(f"\n[4/5] Parsing extraction...")
    try:
        entities = response.get('entities', [])
        facts = response.get('facts', [])

        safe_print(f"   Extracted {len(entities)} entities, {len(facts)} facts")

    except Exception as e:
        safe_print(f"   ERROR parsing extraction: {e}")
        safe_print(f"   Response: {str(response)[:500]}...")
        raise
    
    # Create extraction file
    safe_print(f"\n[5/5] Creating extraction file...")
    extraction_file = {
        "project_name": project_name,
        "source_type": "external_document",
        "extraction_version": "v1.0.0",
        "extraction_commit": "document-extraction",
        "extractions": [
            {
                "source_uuid": source_uuid,
                "entities": entities,
                "facts": facts
            }
        ]
    }
    
    extraction_path = Path(f"./tmp/{source_uuid}_extraction.json")
    with open(extraction_path, 'w', encoding='utf-8') as f:
        json.dump(extraction_file, f, indent=2)
    
    safe_print(f"   Saved to: {extraction_path}")
    
    # Store extraction
    safe_print(f"\n[6/6] Storing extraction in graph...")
    result = subprocess.run(
        [
            sys.executable,
            "scripts/store_extraction.py",
            "--project", project_name,
            "--extraction-file", str(extraction_path)
        ],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        safe_print(f"   OK Extraction stored successfully")
    else:
        safe_print(f"   ERROR: {result.stderr}")
        raise Exception("Failed to store extraction")
    
    safe_print(f"\n{'='*80}")
    safe_print(f"OK EXTRACTION COMPLETE!")
    safe_print(f"{'='*80}\n")
    safe_print(f"Extracted {len(entities)} entities and {len(facts)} facts from {doc_name}")
    safe_print(f"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract knowledge from document")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--source-uuid", required=True, help="ExternalSource UUID")
    
    args = parser.parse_args()
    
    try:
        extract_document(args.project, args.source_uuid)
    except Exception as e:
        safe_print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

