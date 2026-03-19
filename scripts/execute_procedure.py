#!/usr/bin/env python3
"""
execute_procedure.py - CLI for ProcedureRun/StepRun management

This script provides the operational API for procedure execution telemetry.
It does NOT execute procedure steps - the agent performs actions and records outcomes.

Usage:
    # Start a procedure run
    python execute_procedure.py --start-run --procedure-uuid UUID --project NAME \
        --agent NAME --invocation-context procedure_md [--json]

    # Start a step run  
    python execute_procedure.py --start-step --run-uuid UUID --step-uuid UUID \
        --step-number N [--json]

    # Complete a step run (finalization)
    python execute_procedure.py --complete-step --step-run-uuid UUID \
        --status success|failure|skipped [--result-note NOTE] [--json]

    # Complete a procedure run (finalization)
    python execute_procedure.py --complete-run --run-uuid UUID \
        --status success|failure|cancelled [--result-note NOTE] [--json]

    # Create a run batch for audit
    python execute_procedure.py --batch-runs --run-uuids UUID,UUID,... \
        --project NAME --agent NAME [--json]
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.graph_db import GraphDatabase
from tools.config import Config


def output_result(data: dict, is_error: bool = False, json_mode: bool = False):
    """Output result in JSON or human-readable format."""
    if json_mode:
        print(json.dumps(data))
    else:
        if is_error:
            print(f"[ERROR] {data.get('error', 'Unknown error')}", file=sys.stderr)
        else:
            for key, value in data.items():
                print(f"{key}: {value}")
    
    if is_error:
        sys.exit(1)


def cmd_start_run(args, db: GraphDatabase):
    """Start a new ProcedureRun."""
    run_uuid = db.create_procedure_run(
        procedure_uuid=args.procedure_uuid,
        project_name=args.project,
        agent=args.agent,
        invocation_context=args.invocation_context,
        model=args.model or "",
        invocation_source=args.invocation_source,
    )
    
    if run_uuid:
        output_result({"run_uuid": run_uuid, "status": "created"}, json_mode=args.json)
    else:
        output_result({"error": "Failed to create ProcedureRun. Check procedure UUID, project, and invocation_context."}, 
                     is_error=True, json_mode=args.json)


def cmd_start_step(args, db: GraphDatabase):
    """Start a new StepRun."""
    step_run_uuid = db.create_step_run(
        procedure_run_uuid=args.run_uuid,
        procedure_step_uuid=args.step_uuid,
        step_number=args.step_number,
    )
    
    if step_run_uuid:
        output_result({"step_run_uuid": step_run_uuid, "status": "created"}, json_mode=args.json)
    else:
        output_result({"error": "Failed to create StepRun. Check run UUID and step UUID."}, 
                     is_error=True, json_mode=args.json)


def cmd_complete_step(args, db: GraphDatabase):
    """Complete (finalize) a StepRun."""
    result_note = args.result_note
    if args.result_note_file:
        with open(args.result_note_file, 'r', encoding='utf-8') as f:
            result_note = f.read().strip()
    
    success = db.complete_step_run(
        step_run_uuid=args.step_run_uuid,
        status=args.status,
        result_note=result_note,
    )
    
    if success:
        step_run = db.get_step_run(args.step_run_uuid)
        output_result({
            "step_run_uuid": args.step_run_uuid,
            "status": args.status,
            "step_hash": step_run.get("step_hash") if step_run else None,
        }, json_mode=args.json)
    else:
        output_result({"error": f"Failed to finalize StepRun '{args.step_run_uuid}'. May not exist or already finalized."}, 
                     is_error=True, json_mode=args.json)


def cmd_complete_run(args, db: GraphDatabase):
    """Complete (finalize) a ProcedureRun."""
    result_note = args.result_note
    if args.result_note_file:
        with open(args.result_note_file, 'r', encoding='utf-8') as f:
            result_note = f.read().strip()
    
    success = db.complete_procedure_run(
        run_uuid=args.run_uuid,
        status=args.status,
        result_note=result_note,
    )
    
    if success:
        run = db.get_procedure_run(args.run_uuid)
        output_result({
            "run_uuid": args.run_uuid,
            "status": args.status,
            "run_hash": run.get("run_hash") if run else None,
        }, json_mode=args.json)
    else:
        output_result({"error": f"Failed to finalize ProcedureRun '{args.run_uuid}'. May not exist, already finalized, or has incomplete steps."}, 
                     is_error=True, json_mode=args.json)


def cmd_batch_runs(args, db: GraphDatabase):
    """Create a RunBatch for audit."""
    # Parse run UUIDs from comma-separated string or file
    if args.run_uuids_file:
        with open(args.run_uuids_file, 'r', encoding='utf-8') as f:
            run_uuids = [line.strip() for line in f if line.strip()]
    else:
        run_uuids = [u.strip() for u in args.run_uuids.split(',') if u.strip()]
    
    if not run_uuids:
        output_result({"error": "No run UUIDs provided."}, is_error=True, json_mode=args.json)
        return
    
    batch_uuid = db.create_run_batch(
        project_name=args.project,
        run_uuids=run_uuids,
        agent=args.agent,
        model=args.model or "",
    )
    
    if batch_uuid:
        batch = db.get_run_batch(batch_uuid)
        result = {
            "batch_uuid": batch_uuid,
            "batch_hash": batch.get("batch_hash") if batch else None,
            "batch_index": batch.get("batch_index") if batch else None,
        }
        # Note about timestamp_proof in constrained environment
        if batch and not batch.get("timestamp_proof"):
            result["note"] = "timestamp_proof not submitted (constrained environment). Hash created locally."
        output_result(result, json_mode=args.json)
    else:
        output_result({"error": "Failed to create RunBatch. Runs may be incomplete, already batched, or not in project."},
                     is_error=True, json_mode=args.json)


# =============================================================================
# Phase 3: Compound Commands (Reduced Friction)
# =============================================================================

def cmd_start_run_with_steps(args, db: GraphDatabase):
    """Start a ProcedureRun and create all StepRuns upfront.

    This is a compound command that:
    1. Looks up the procedure and its steps
    2. Creates the ProcedureRun
    3. Creates all StepRuns in order
    4. Returns complete execution context
    """
    # Get procedure info
    procedure = db.get_entity(args.procedure_uuid)
    if not procedure:
        output_result({"error": f"Procedure '{args.procedure_uuid}' not found."},
                     is_error=True, json_mode=args.json)
        return

    # Check labels
    labels = procedure.get("labels", [])
    if isinstance(labels, str):
        try:
            labels = json.loads(labels)
        except:
            labels = []

    if "Procedure" not in labels:
        output_result({"error": f"Entity '{args.procedure_uuid}' is not a Procedure."},
                     is_error=True, json_mode=args.json)
        return

    # Check lifecycle status
    attrs = procedure.get("attributes", {})
    if isinstance(attrs, str):
        try:
            attrs = json.loads(attrs)
        except:
            attrs = {}

    lifecycle = attrs.get("lifecycle_status", "active")
    if lifecycle in ("deprecated", "superseded", "invalid"):
        output_result({"error": f"Procedure '{procedure.get('name')}' has lifecycle_status='{lifecycle}'. DO NOT EXECUTE."},
                     is_error=True, json_mode=args.json)
        return

    # Get procedure steps
    procedure_name = procedure.get("name", "")
    steps = db.get_procedure_steps(procedure_name, args.project)

    if not steps:
        output_result({"error": f"No steps found for procedure '{procedure_name}'."},
                     is_error=True, json_mode=args.json)
        return

    # Create ProcedureRun
    run_uuid = db.create_procedure_run(
        procedure_uuid=args.procedure_uuid,
        project_name=args.project,
        agent=args.agent,
        invocation_context=args.invocation_context,
        model=args.model or "",
        invocation_source=args.invocation_source,
    )

    if not run_uuid:
        output_result({"error": "Failed to create ProcedureRun."},
                     is_error=True, json_mode=args.json)
        return

    # Create all StepRuns
    step_runs = []
    for step in steps:
        step_attrs = step.get("attributes", {})
        if isinstance(step_attrs, str):
            try:
                step_attrs = json.loads(step_attrs)
            except:
                step_attrs = {}

        step_number = step_attrs.get("step_number", len(step_runs) + 1)
        step_action = step_attrs.get("action", step.get("summary", ""))

        step_run_uuid = db.create_step_run(
            procedure_run_uuid=run_uuid,
            procedure_step_uuid=step.get("uuid"),
            step_number=step_number,
        )

        if not step_run_uuid:
            # Cleanup: this is a problem - we created the run but failed on a step
            output_result({
                "error": f"Failed to create StepRun for step {step_number}. Run '{run_uuid}' created but incomplete.",
                "run_uuid": run_uuid,
                "steps_created": len(step_runs)
            }, is_error=True, json_mode=args.json)
            return

        step_runs.append({
            "step_run_uuid": step_run_uuid,
            "step_uuid": step.get("uuid"),
            "step_number": step_number,
            "action": step_action,
            "status": "pending"
        })

    # Return complete execution context
    output_result({
        "run_uuid": run_uuid,
        "procedure_name": procedure_name,
        "procedure_uuid": args.procedure_uuid,
        "total_steps": len(step_runs),
        "steps": step_runs,
        "current_step_index": 0,
        "status": "ready"
    }, json_mode=args.json)


def cmd_complete_step_and_advance(args, db: GraphDatabase):
    """Complete current step (success only) and return next step info.

    This is a compound command for the SUCCESS path that:
    1. Finalizes the current StepRun as success
    2. Returns info about the next step (or completion status if last)

    For failures, use --fail-step-and-run instead.
    """
    # Enforce success-only policy
    if args.status != "success":
        output_result({
            "error": f"--complete-step-and-advance only accepts --status success. For failures, use --fail-step-and-run."
        }, is_error=True, json_mode=args.json)
        return

    result_note = args.result_note
    if args.result_note_file:
        with open(args.result_note_file, 'r', encoding='utf-8') as f:
            result_note = f.read().strip()

    # Complete the current step
    success = db.complete_step_run(
        step_run_uuid=args.step_run_uuid,
        status=args.status,
        result_note=result_note,
    )

    if not success:
        output_result({"error": f"Failed to finalize StepRun '{args.step_run_uuid}'."},
                     is_error=True, json_mode=args.json)
        return

    # Get the completed step to find the run and step number
    completed_step = db.get_step_run(args.step_run_uuid)
    if not completed_step:
        output_result({"error": f"Could not retrieve completed StepRun."},
                     is_error=True, json_mode=args.json)
        return

    run_uuid = completed_step.get("procedure_run_uuid")
    completed_step_number = completed_step.get("step_number")

    # Find the next step in this run
    result = db.conn.execute("""
        MATCH (sr:StepRun {procedure_run_uuid: $run_uuid})
        WHERE sr.step_number > $current_step_number
        RETURN sr.uuid, sr.step_number, sr.procedure_step_uuid, sr.status
        ORDER BY sr.step_number
        LIMIT 1
    """, {"run_uuid": run_uuid, "current_step_number": completed_step_number})

    if result.has_next():
        row = result.get_next()
        next_step_run_uuid = row[0]
        next_step_number = row[1]
        next_step_uuid = row[2]

        # Get action from the ProcedureStep entity
        next_step_entity = db.get_entity(next_step_uuid)
        next_action = ""
        if next_step_entity:
            attrs = next_step_entity.get("attributes", {})
            if isinstance(attrs, str):
                try:
                    attrs = json.loads(attrs)
                except:
                    attrs = {}
            next_action = attrs.get("action", next_step_entity.get("summary", ""))

        output_result({
            "completed_step_run_uuid": args.step_run_uuid,
            "completed_step_number": completed_step_number,
            "completed_status": args.status,
            "completed_step_hash": completed_step.get("step_hash"),
            "next_step_run_uuid": next_step_run_uuid,
            "next_step_number": next_step_number,
            "next_action": next_action,
            "run_uuid": run_uuid,
            "run_complete": False
        }, json_mode=args.json)
    else:
        # No more steps - this was the last one
        output_result({
            "completed_step_run_uuid": args.step_run_uuid,
            "completed_step_number": completed_step_number,
            "completed_status": args.status,
            "completed_step_hash": completed_step.get("step_hash"),
            "next_step_run_uuid": None,
            "next_step_number": None,
            "next_action": None,
            "run_uuid": run_uuid,
            "run_complete": True,
            "note": "All steps complete. Call --complete-run to finalize the procedure run."
        }, json_mode=args.json)


def cmd_fail_step_and_run(args, db: GraphDatabase):
    """Mark current step as failed, skip remaining steps, and finalize the run as failed.

    This is a compound command for the failure path that:
    1. Finalizes the current StepRun as failed
    2. Auto-skips any remaining pending StepRuns
    3. Finalizes the ProcedureRun as failed
    """
    result_note = args.result_note
    if args.result_note_file:
        with open(args.result_note_file, 'r', encoding='utf-8') as f:
            result_note = f.read().strip()

    # Get step info first to find the run
    step = db.get_step_run(args.step_run_uuid)
    if not step:
        output_result({"error": f"StepRun '{args.step_run_uuid}' not found."},
                     is_error=True, json_mode=args.json)
        return

    run_uuid = step.get("procedure_run_uuid")
    failed_step_number = step.get("step_number")

    # Complete the step as failed
    step_success = db.complete_step_run(
        step_run_uuid=args.step_run_uuid,
        status="failure",
        result_note=result_note,
    )

    if not step_success:
        output_result({"error": f"Failed to finalize StepRun '{args.step_run_uuid}'."},
                     is_error=True, json_mode=args.json)
        return

    # Auto-skip any remaining pending steps (required for run finalization)
    skipped_steps = []
    pending_result = db.conn.execute("""
        MATCH (sr:StepRun {procedure_run_uuid: $run_uuid})
        WHERE sr.step_hash IS NULL AND sr.uuid <> $current_uuid
        RETURN sr.uuid, sr.step_number
        ORDER BY sr.step_number
    """, {"run_uuid": run_uuid, "current_uuid": args.step_run_uuid})

    while pending_result.has_next():
        row = pending_result.get_next()
        pending_uuid = row[0]
        pending_num = row[1]

        skip_success = db.complete_step_run(
            step_run_uuid=pending_uuid,
            status="skipped",
            result_note=f"Auto-skipped due to failure at step {failed_step_number}",
        )
        if skip_success:
            skipped_steps.append({"step_run_uuid": pending_uuid, "step_number": pending_num})

    # Now complete the run as failed
    run_success = db.complete_procedure_run(
        run_uuid=run_uuid,
        status="failure",
        result_note=result_note or f"Failed at step {failed_step_number}",
    )

    # Get final state
    final_step = db.get_step_run(args.step_run_uuid)
    final_run = db.get_procedure_run(run_uuid) if run_success else None

    output_result({
        "step_run_uuid": args.step_run_uuid,
        "step_status": "failure",
        "step_hash": final_step.get("step_hash") if final_step else None,
        "skipped_steps": skipped_steps,
        "run_uuid": run_uuid,
        "run_status": "failure" if run_success else "finalization_failed",
        "run_hash": final_run.get("run_hash") if final_run else None,
        "note": f"Step {failed_step_number} failed. {len(skipped_steps)} remaining steps auto-skipped. Run finalized as failed."
    }, json_mode=args.json)


def main():
    parser = argparse.ArgumentParser(
        description="CLI for ProcedureRun/StepRun management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start a procedure run
  python execute_procedure.py --start-run --procedure-uuid entity-abc123 \\
      --project myproject --agent auggie --invocation-context procedure_md --json

  # Start a step run
  python execute_procedure.py --start-step --run-uuid run-abc123 \\
      --step-uuid entity-def456 --step-number 1 --json

  # Complete a step run
  python execute_procedure.py --complete-step --step-run-uuid steprun-abc123 \\
      --status success --json

  # Complete a procedure run
  python execute_procedure.py --complete-run --run-uuid run-abc123 \\
      --status success --json

  # Create a run batch
  python execute_procedure.py --batch-runs --run-uuids run-abc123,run-def456 \\
      --project myproject --agent auggie --json
"""
    )

    # Command selection
    cmd_group = parser.add_mutually_exclusive_group(required=True)
    cmd_group.add_argument('--start-run', action='store_true',
                          help='Start a new ProcedureRun')
    cmd_group.add_argument('--start-step', action='store_true',
                          help='Start a new StepRun')
    cmd_group.add_argument('--complete-step', action='store_true',
                          help='Complete (finalize) a StepRun')
    cmd_group.add_argument('--complete-run', action='store_true',
                          help='Complete (finalize) a ProcedureRun')
    cmd_group.add_argument('--batch-runs', action='store_true',
                          help='Create a RunBatch for audit')
    # Phase 3: Compound commands
    cmd_group.add_argument('--start-run-with-steps', action='store_true',
                          help='Start ProcedureRun and create all StepRuns upfront')
    cmd_group.add_argument('--complete-step-and-advance', action='store_true',
                          help='Complete current step and return next step info')
    cmd_group.add_argument('--fail-step-and-run', action='store_true',
                          help='Mark step failed and finalize run as failed')

    # Common options
    parser.add_argument('--json', action='store_true',
                       help='Output in JSON format')
    parser.add_argument('--db', help='Path to graph database (default: from config)')

    # --start-run options
    parser.add_argument('--procedure-uuid', help='UUID of procedure to run')
    parser.add_argument('--procedure-uuid-file', help='File containing procedure UUID')
    parser.add_argument('--project', help='Project name')
    parser.add_argument('--agent', help='Agent/user initiating the run')
    parser.add_argument('--model', help='Model name (optional)')
    parser.add_argument('--invocation-context',
                       choices=['procedure_md', 'manual', 'script', 'conversation', 'api'],
                       help='How the run was invoked')
    parser.add_argument('--invocation-source', help='Source identifier (conversation UUID, script path)')
    parser.add_argument('--invocation-source-file', help='File containing invocation source')

    # --start-step options
    parser.add_argument('--run-uuid', help='UUID of the ProcedureRun')
    parser.add_argument('--run-uuid-file', help='File containing run UUID')
    parser.add_argument('--step-uuid', help='UUID of the ProcedureStep entity')
    parser.add_argument('--step-uuid-file', help='File containing step UUID')
    parser.add_argument('--step-number', type=int, help='Step number')

    # --complete-step options
    parser.add_argument('--step-run-uuid', help='UUID of the StepRun to complete')
    parser.add_argument('--step-run-uuid-file', help='File containing step run UUID')
    parser.add_argument('--status', choices=['success', 'failure', 'skipped', 'cancelled'],
                       help='Final status')
    parser.add_argument('--result-note', help='Note about the result')
    parser.add_argument('--result-note-file', help='File containing result note')

    # --batch-runs options
    parser.add_argument('--run-uuids', help='Comma-separated list of run UUIDs')
    parser.add_argument('--run-uuids-file', help='File with run UUIDs (one per line)')

    # Universal JSON input (all parameters in one file)
    parser.add_argument('--input-file', help='JSON file with all parameters (RECOMMENDED)')

    args = parser.parse_args()

    # Load from JSON input file if provided (overrides individual args)
    if args.input_file:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            data = json.loads(f.read())
        # Map JSON keys to args (use kebab-case in JSON, convert to snake_case)
        key_mapping = {
            'procedure-uuid': 'procedure_uuid',
            'procedure_uuid': 'procedure_uuid',
            'project': 'project',
            'agent': 'agent',
            'model': 'model',
            'invocation-context': 'invocation_context',
            'invocation_context': 'invocation_context',
            'invocation-source': 'invocation_source',
            'invocation_source': 'invocation_source',
            'run-uuid': 'run_uuid',
            'run_uuid': 'run_uuid',
            'step-uuid': 'step_uuid',
            'step_uuid': 'step_uuid',
            'step-number': 'step_number',
            'step_number': 'step_number',
            'step-run-uuid': 'step_run_uuid',
            'step_run_uuid': 'step_run_uuid',
            'status': 'status',
            'result-note': 'result_note',
            'result_note': 'result_note',
            'run-uuids': 'run_uuids',
            'run_uuids': 'run_uuids',
        }
        for json_key, attr_name in key_mapping.items():
            if json_key in data and not getattr(args, attr_name, None):
                setattr(args, attr_name, data[json_key])

    # Read from individual files where applicable (fallback)
    if args.procedure_uuid_file and not args.procedure_uuid:
        with open(args.procedure_uuid_file, 'r', encoding='utf-8') as f:
            args.procedure_uuid = f.read().strip()
    if args.run_uuid_file and not args.run_uuid:
        with open(args.run_uuid_file, 'r', encoding='utf-8') as f:
            args.run_uuid = f.read().strip()
    if args.step_uuid_file and not args.step_uuid:
        with open(args.step_uuid_file, 'r', encoding='utf-8') as f:
            args.step_uuid = f.read().strip()
    if args.step_run_uuid_file and not args.step_run_uuid:
        with open(args.step_run_uuid_file, 'r', encoding='utf-8') as f:
            args.step_run_uuid = f.read().strip()
    if args.invocation_source_file and not args.invocation_source:
        with open(args.invocation_source_file, 'r', encoding='utf-8') as f:
            args.invocation_source = f.read().strip()

    # Load config and database using shared config loader
    config = Config()
    db_path = args.db or config.get_graph_db_path(args.project)
    db = GraphDatabase(db_path)

    try:
        if args.start_run:
            if not all([args.procedure_uuid, args.project, args.agent, args.invocation_context]):
                output_result({"error": "--start-run requires --procedure-uuid, --project, --agent, --invocation-context"},
                             is_error=True, json_mode=args.json)
            cmd_start_run(args, db)

        elif args.start_step:
            if not all([args.run_uuid, args.step_uuid, args.step_number is not None]):
                output_result({"error": "--start-step requires --run-uuid, --step-uuid, --step-number"},
                             is_error=True, json_mode=args.json)
            cmd_start_step(args, db)

        elif args.complete_step:
            if not all([args.step_run_uuid, args.status]):
                output_result({"error": "--complete-step requires --step-run-uuid, --status"},
                             is_error=True, json_mode=args.json)
            cmd_complete_step(args, db)

        elif args.complete_run:
            if not all([args.run_uuid, args.status]):
                output_result({"error": "--complete-run requires --run-uuid, --status"},
                             is_error=True, json_mode=args.json)
            cmd_complete_run(args, db)

        elif args.batch_runs:
            if not all([args.project, args.agent]) or not (args.run_uuids or args.run_uuids_file):
                output_result({"error": "--batch-runs requires --project, --agent, and --run-uuids or --run-uuids-file"},
                             is_error=True, json_mode=args.json)
            cmd_batch_runs(args, db)

        # Phase 3: Compound commands
        elif args.start_run_with_steps:
            if not all([args.procedure_uuid, args.project, args.agent, args.invocation_context]):
                output_result({"error": "--start-run-with-steps requires --procedure-uuid, --project, --agent, --invocation-context"},
                             is_error=True, json_mode=args.json)
            cmd_start_run_with_steps(args, db)

        elif args.complete_step_and_advance:
            if not all([args.step_run_uuid, args.status]):
                output_result({"error": "--complete-step-and-advance requires --step-run-uuid, --status"},
                             is_error=True, json_mode=args.json)
            cmd_complete_step_and_advance(args, db)

        elif args.fail_step_and_run:
            if not args.step_run_uuid:
                output_result({"error": "--fail-step-and-run requires --step-run-uuid"},
                             is_error=True, json_mode=args.json)
            cmd_fail_step_and_run(args, db)

    finally:
        db.close()


if __name__ == "__main__":
    main()

