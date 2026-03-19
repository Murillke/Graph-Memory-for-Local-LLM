#!/usr/bin/env python3
"""
Submit constrained-environment timestamp proofs to OpenTimestamps.

This recovers externally anchored proofs after a conversation was imported with
--constrained-environment. It:
1. Finds local-only SQL timestamp proofs for a project
2. Submits each distinct content hash to OpenTimestamps
3. Replaces the local-only proof with the OTS-backed proof in SQL
4. Propagates the updated proof into graph entities, relationships, and aliases

Usage:
    python scripts/submit_local_proofs_to_ots.py --project llm_memory
    python scripts/submit_local_proofs_to_ots.py --project llm_memory --dry-run
"""

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.graph_db import GraphDatabase
from tools.config import load_config
from tools.timestamp_proof_official import create_timestamp_proof_official


def get_local_only_proofs(sql_path, project_name):
    """Return distinct local-only proofs for a project from SQL."""
    conn = sqlite3.connect(sql_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp_proof, COUNT(*)
        FROM interactions
        WHERE project_name = ?
          AND timestamp_proof IS NOT NULL
          AND deleted_at IS NULL
        GROUP BY timestamp_proof
    """, (project_name,))
    rows = cursor.fetchall()
    conn.close()

    proofs = []
    for proof_json, interaction_count in rows:
        try:
            proof = json.loads(proof_json)
        except Exception:
            continue

        if proof.get('proof_mode') != 'local':
            continue
        if proof.get('attestation_status') != 'not_requested':
            continue
        if 'ots_data' in proof:
            continue

        proofs.append({
            'old_proof_json': proof_json,
            'content_hash': proof.get('content_hash'),
            'interaction_count': interaction_count,
            'constraint_reason': proof.get('constraint_reason'),
            'timestamp': proof.get('timestamp')
        })

    return proofs


def update_sql_proofs(sql_path, project_name, old_proof_json, new_proof_json):
    """Update matching SQL interactions with the new proof."""
    conn = sqlite3.connect(sql_path)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE interactions
        SET timestamp_proof = ?
        WHERE project_name = ?
          AND timestamp_proof = ?
          AND deleted_at IS NULL
    """, (new_proof_json, project_name, old_proof_json))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


def update_graph_proofs(graph_db, project_name, old_proof_json, new_proof_json):
    """Update matching graph proofs for the selected project."""
    updates = {}

    result = graph_db.conn.execute("""
        MATCH (e:Entity)
        WHERE e.group_id = $project_name
          AND e.timestamp_proof = $old_proof_json
        SET e.timestamp_proof = $new_proof_json
        RETURN count(e)
    """, {
        "project_name": project_name,
        "old_proof_json": old_proof_json,
        "new_proof_json": new_proof_json,
    })
    updates['entities'] = result.get_next()[0] if result.has_next() else 0

    result = graph_db.conn.execute("""
        MATCH (:Entity)-[r:RELATES_TO]->(:Entity)
        WHERE r.group_id = $project_name
          AND r.timestamp_proof = $old_proof_json
        SET r.timestamp_proof = $new_proof_json
        RETURN count(r)
    """, {
        "project_name": project_name,
        "old_proof_json": old_proof_json,
        "new_proof_json": new_proof_json,
    })
    updates['relationships'] = result.get_next()[0] if result.has_next() else 0

    result = graph_db.conn.execute("""
        MATCH (a:Alias)
        WHERE a.timestamp_proof = $old_proof_json
        SET a.timestamp_proof = $new_proof_json
        RETURN count(a)
    """, {
        "old_proof_json": old_proof_json,
        "new_proof_json": new_proof_json,
    })
    updates['aliases'] = result.get_next()[0] if result.has_next() else 0

    return updates


def main():
    parser = argparse.ArgumentParser(
        description='Submit constrained-environment proofs to OpenTimestamps'
    )
    parser.add_argument('--project', required=True, help='Project name')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without doing it')
    args = parser.parse_args()

    config = load_config(project_name=args.project)
    sql_path = config.get_sql_db_path()
    graph_path = config.get_graph_db_path(args.project)

    proofs = get_local_only_proofs(sql_path, args.project)

    print("=" * 70)
    print("Submit Local-Only Proofs to OpenTimestamps")
    print("=" * 70)
    print(f"Project: {args.project}")
    print(f"SQL DB:  {sql_path}")
    print(f"Graph:   {graph_path}")
    print(f"\nFound {len(proofs)} distinct local-only proof(s) eligible for recovery")

    if not proofs:
        print("[OK] No constrained-environment proofs need recovery.")
        return

    if args.dry_run:
        print("\n[DRY RUN] Recoverable proofs:")
        for index, item in enumerate(proofs, 1):
            reason = item['constraint_reason'] or 'n/a'
            print(
                f"  {index}. hash={item['content_hash'][:16]}... "
                f"interactions={item['interaction_count']} "
                f"timestamp={item['timestamp']} "
                f"reason={reason}"
            )
        return

    graph_db = GraphDatabase(graph_path)

    success_count = 0
    failure_count = 0

    for index, item in enumerate(proofs, 1):
        print(f"\n[{index}/{len(proofs)}] Recovering hash {item['content_hash'][:16]}...")

        try:
            new_proof_json = create_timestamp_proof_official(
                item['content_hash'],
                submit_to_ots=True,
                constrained_environment=False
            )
            new_proof = json.loads(new_proof_json)

            if 'ots_data' not in new_proof:
                print("  [WARN] Submission did not return ots_data; leaving old proof unchanged")
                failure_count += 1
                continue

            sql_updates = update_sql_proofs(
                sql_path,
                args.project,
                item['old_proof_json'],
                new_proof_json
            )
            graph_updates = update_graph_proofs(
                graph_db,
                args.project,
                item['old_proof_json'],
                new_proof_json
            )

            print(f"  [OK] Submitted to OpenTimestamps")
            print(f"       SQL interactions updated: {sql_updates}")
            print(f"       Graph entities updated:   {graph_updates['entities']}")
            print(f"       Graph facts updated:      {graph_updates['relationships']}")
            print(f"       Graph aliases updated:    {graph_updates['aliases']}")
            success_count += 1

        except Exception as e:
            print(f"  [ERROR] {e}")
            failure_count += 1

    graph_db.close()

    print("\n" + "=" * 70)
    print(f"SUMMARY: {success_count} recovered, {failure_count} failed")
    print("=" * 70)
    print("\nNext steps:")
    print("1. Wait 4-12 hours for Bitcoin confirmation")
    print(f"2. Run: python scripts/verify_graph_standalone.py --project {args.project} --upgrade")
    print("   to upgrade the recovered OTS proofs to Bitcoin attestations")


if __name__ == '__main__':
    main()
