#!/usr/bin/env python3
"""
Import external documents into the knowledge graph.

Supports: .txt, .md, .pdf, .docx
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.graph_db import GraphDatabase
from tools.config import load_config
from tools.timestamp_proof import create_timestamp_proof
import argparse
import hashlib
import json
from datetime import datetime


IMPORT_DOC_EXAMPLES = """
Examples:
  # Basic import (uses filename as name)
  python scripts/import_document.py --project llm_memory --file document.pdf

  # Import with custom name/summary (use files for spaces)
  python scripts/import_document.py --project llm_memory --file doc.pdf --name-file tmp/name.txt --summary-file tmp/summary.txt

  # Import with auto-extraction
  python scripts/import_document.py --project llm_memory --file document.pdf --extract

  # Force re-import even if unchanged
  python scripts/import_document.py --project llm_memory --file document.pdf --force

Note: Use --name-file and --summary-file for names/summaries with spaces.
      Do NOT use echo to create these files (UTF-16 on Windows).
"""


class ImportDocArgumentParser(argparse.ArgumentParser):
    """Custom parser that prints examples on error."""
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n{IMPORT_DOC_EXAMPLES}")


def safe_print(text):
    """Print with encoding fallback for Windows."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))


def hash_file(file_path):
    """Calculate SHA256 hash of file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


def extract_text_from_txt(file_path):
    """Extract text from text file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def extract_text_from_pdf(file_path):
    """Extract text from PDF."""
    try:
        import PyPDF2
        text = []
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text.append(page.extract_text())
        return '\n\n'.join(text)
    except Exception as e:
        raise Exception(f"Failed to extract PDF text: {e}")


def extract_text_from_docx(file_path):
    """Extract text from Word document."""
    try:
        import docx
        doc = docx.Document(file_path)
        text = []
        for paragraph in doc.paragraphs:
            text.append(paragraph.text)
        return '\n\n'.join(text)
    except Exception as e:
        raise Exception(f"Failed to extract Word text: {e}")


def extract_text(file_path):
    """Extract text from document based on file type."""
    ext = Path(file_path).suffix.lower()

    if ext in ['.txt', '.md', '.json', '.xml', '.csv', '.py', '.js', '.sql', '.yaml', '.yml']:
        return extract_text_from_txt(file_path)
    elif ext == '.pdf':
        return extract_text_from_pdf(file_path)
    elif ext == '.docx':
        return extract_text_from_docx(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def find_latest_version(db, project_name, name):
    """Find latest version of document by name."""
    result = db.conn.execute("""
        MATCH (p:Project {name: $project_name})-[:HAS_ENTITY]->(doc:Entity)
        WHERE doc.name = $name
          AND doc.labels CONTAINS 'ExternalSource'
          AND (doc.status = 'active' OR doc.status IS NULL)
        RETURN doc.uuid, doc.attributes
        LIMIT 1
    """, {
        "project_name": project_name,
        "name": name,
    })

    if result.has_next():
        row = result.get_next()
        uuid = row[0]
        attributes = json.loads(row[1]) if row[1] else {}
        return {
            'uuid': uuid,
            'version': attributes.get('version', 1),
            'file_hash': attributes.get('file_hash', '')
        }
    return None


def mark_as_replaced(db, uuid):
    """Mark ExternalSource as replaced."""
    from datetime import datetime
    now = datetime.now().isoformat()
    db.conn.execute("""
        MATCH (doc:Entity {uuid: $uuid})
        SET doc.deleted_at = timestamp($now),
            doc.status = 'replaced'
    """, {
        "uuid": uuid,
        "now": now,
    })


def delete_entities_from_source(db, source_uuid):
    """Delete all entities extracted from this source."""
    from datetime import datetime
    now = datetime.now().isoformat()
    try:
        db.conn.execute("""
            MATCH (e:Entity)-[:EXTRACTED_FROM]->(doc:Entity {uuid: $source_uuid})
            SET e.deleted_at = timestamp($now)
        """, {
            "source_uuid": source_uuid,
            "now": now,
        })
    except Exception as e:
        # Relationship might not exist yet if no extraction was done
        if "does not exist" in str(e):
            pass  # No entities to delete
        else:
            raise


def import_document(project_name: str, file_path: str, name: str = None, summary: str = '',
                   extract: bool = False, force: bool = False):
    """Import document into knowledge graph with version tracking."""

    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Use filename as name if not provided
    if not name:
        name = file_path.stem

    safe_print(f"\n{'='*80}")
    safe_print(f"IMPORTING DOCUMENT: {name}")
    safe_print(f"{'='*80}\n")

    # Calculate file hash
    safe_print("[1/6] Calculating file hash...")
    file_hash = hash_file(file_path)
    safe_print(f"   File hash: {file_hash[:16]}...")

    # Get file info
    file_size = file_path.stat().st_size
    file_type = file_path.suffix.lower()

    # Check for existing versions
    safe_print(f"\n[2/6] Checking for existing versions...")
    db_path = load_config(project_name=project_name).get_graph_db_path(project_name)
    db = GraphDatabase(db_path)

    try:
        latest = find_latest_version(db, project_name, name)

        if latest:
            # Document exists
            if latest['file_hash'] == file_hash and not force:
                # Unchanged, skip
                safe_print(f"   Document unchanged (hash matches version {latest['version']})")
                safe_print(f"   Skipping import (use --force to re-extract)")
                return latest['uuid']
            else:
                # Changed or forced
                if force:
                    safe_print(f"   Force reload: re-extracting version {latest['version']}")
                    new_version = latest['version']
                    # Delete old entities
                    delete_entities_from_source(db, latest['uuid'])
                else:
                    safe_print(f"   File changed, creating version {latest['version'] + 1}")
                    new_version = latest['version'] + 1
                    # Mark old version as replaced
                    mark_as_replaced(db, latest['uuid'])
                    # Delete old entities
                    delete_entities_from_source(db, latest['uuid'])

                version = new_version
                previous_uuid = latest['uuid']
        else:
            # First import
            safe_print(f"   First import, creating version 1")
            version = 1
            previous_uuid = None

    finally:
        db.close()

    # Extract text
    safe_print(f"\n[3/6] Extracting text from {file_type} file...")
    try:
        content = extract_text(file_path)
        content_preview = content[:200].replace('\n', ' ')
        safe_print(f"   Extracted {len(content)} characters")
        safe_print(f"   Preview: {content_preview}...")
    except Exception as e:
        safe_print(f"   ERROR: {e}")
        return None

    # Create timestamp proof
    safe_print(f"\n[4/6] Creating timestamp proof...")
    timestamp_proof_json = create_timestamp_proof(file_hash, submit_to_ots=True)
    safe_print(f"   OK Timestamp proof created")

    # Store in graph
    safe_print(f"\n[5/6] Storing in knowledge graph...")
    db = GraphDatabase(db_path)

    try:
        # Create ExternalSource entity
        entity_uuid = db.create_entity(
            name=name,
            summary=summary or f"{file_type.upper()} document with {len(content)} characters",
            labels=['ExternalSource', 'Document'],
            attributes={
                'file_type': file_type,
                'file_size': file_size,
                'file_hash': file_hash,
                'content_length': len(content),
                'file_path': str(file_path),
                'version': version,
                'status': 'active'
            },
            source_interactions=[],
            source_hashes=[],
            source_chain=[],
            group_id=project_name,
            extraction_version='import',
            extraction_commit='document-import',
            timestamp_proof=timestamp_proof_json,
            status='active'
        )

        # Link to project
        db.link_project_to_entity(project_name, entity_uuid)

        # Link to previous version if exists
        # TODO: Create UPDATED_TO relationship table in schema
        # if previous_uuid and not force:
        #     db.conn.execute(f"""
        #         MATCH (old:Entity {{uuid: '{previous_uuid}'}}),
        #               (new:Entity {{uuid: '{entity_uuid}'}})
        #         CREATE (old)-[:UPDATED_TO]->(new)
        #     """)
        #     safe_print(f"   Linked to previous version")

        safe_print(f"   OK Created ExternalSource entity (version {version})")
        safe_print(f"   UUID: {entity_uuid}")

    finally:
        db.close()

    # Save extracted content
    safe_print(f"\n[6/6] Saving extracted content...")
    content_file = Path(f"./tmp/{entity_uuid}_content.txt")
    content_file.parent.mkdir(exist_ok=True)
    with open(content_file, 'w', encoding='utf-8') as f:
        f.write(content)
    safe_print(f"   Saved to: {content_file}")

    safe_print(f"\n{'='*80}")
    safe_print(f"OK DOCUMENT IMPORTED SUCCESSFULLY!")
    safe_print(f"{'='*80}\n")

    # Extract if requested
    if extract:
        safe_print(f"Triggering automatic extraction...\n")
        import subprocess
        result = subprocess.run(
            [
                sys.executable,
                "scripts/extract_document.py",
                "--project", project_name,
                "--source-uuid", entity_uuid
            ],
            capture_output=False
        )
        if result.returncode != 0:
            safe_print(f"\nWARNING: Extraction failed")
    else:
        safe_print(f"Next steps:")
        safe_print(f"  1. Review extracted content: {content_file}")
        safe_print(f"  2. Extract knowledge: python scripts/extract_document.py --project {project_name} --source-uuid {entity_uuid}")
        safe_print(f"\n")

    return entity_uuid


if __name__ == "__main__":
    parser = ImportDocArgumentParser(
        description="Import external document",
        epilog=IMPORT_DOC_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--file", required=True, help="Path to document file")
    parser.add_argument("--name", nargs='+', help="Document name (use --name-file for names with spaces)")
    parser.add_argument("--name-file", help="File containing document name (RECOMMENDED)")
    parser.add_argument("--summary", nargs='*', help="Document summary (use --summary-file for summaries with spaces)")
    parser.add_argument("--summary-file", help="File containing document summary (RECOMMENDED)")
    parser.add_argument("--extract", action="store_true", help="Automatically extract knowledge after import")
    parser.add_argument("--force", action="store_true", help="Force re-import even if unchanged")

    args = parser.parse_args()

    # Read from files if provided
    name = None
    if args.name_file:
        with open(args.name_file, 'r', encoding='utf-8') as f:
            name = f.read().strip()
    elif args.name:
        name = ' '.join(args.name)

    summary = ''
    if args.summary_file:
        with open(args.summary_file, 'r', encoding='utf-8') as f:
            summary = f.read().strip()
    elif args.summary:
        summary = ' '.join(args.summary)

    try:
        import_document(args.project, args.file, name, summary, args.extract, args.force)
    except Exception as e:
        safe_print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
