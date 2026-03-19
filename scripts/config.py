#!/usr/bin/env python3
"""
config.py - Unified configuration management for llm_memory.

View and edit settings from mem.config.json and SQL metadata.

Examples:
  python scripts/config.py --project llm_memory --show
  python scripts/config.py --project llm_memory --show-json
  python scripts/config.py --project llm_memory --get database.sql_path
  python scripts/config.py --set python_path "./venv/bin/python"
  python scripts/config.py --project llm_memory --set-sql backup_repo "github.com/user/repo"
  python scripts/config.py --project llm_memory --list-sql
"""

import argparse
import json
import os
import sys
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.config import load_config, Config as MemoryConfig


def safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('utf-8', errors='replace').decode('utf-8'))


def get_nested_value(d: dict, key_path: str):
    keys = key_path.split('.')
    value = d
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    return value


def set_nested_value(d: dict, key_path: str, value):
    keys = key_path.split('.')
    for key in keys[:-1]:
        if key not in d:
            d[key] = {}
        d = d[key]
    d[keys[-1]] = value


def load_sql_metadata(config: MemoryConfig) -> dict:
    metadata = {}
    sql_path = config.get_sql_db_path()
    if not Path(sql_path).exists():
        return metadata
    try:
        conn = sqlite3.connect(sql_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metadata'")
        if not cursor.fetchone():
            conn.close()
            return metadata
        cursor.execute("SELECT key, value FROM metadata")
        for row in cursor.fetchall():
            metadata[row[0]] = row[1]
        conn.close()
    except Exception as e:
        safe_print(f"[WARN] Could not load SQL metadata: {e}")
    return metadata


def set_sql_metadata(config: MemoryConfig, key: str, value: str):
    sql_path = config.get_sql_db_path()
    if not Path(sql_path).exists():
        safe_print(f"[ERROR] Database not found: {sql_path}")
        sys.exit(1)
    conn = sqlite3.connect(sql_path)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
    cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def show_config(config: MemoryConfig, as_json: bool = False):
    sql_metadata = load_sql_metadata(config)
    env_overrides = {}
    env_vars = {
        "MEM_PROJECT": "project_name",
        "MEM_PYTHON_PATH": "python_path",
        "MEM_SQL_DB": "database.sql_path",
        "MEM_GRAPH_DB": "database.graph_path",
        "LLM_AGENT_NAME": "agent_name"
    }
    for env_var in env_vars:
        if os.environ.get(env_var):
            env_overrides[env_var] = os.environ[env_var]

    output = {"json_config": config.config, "sql_metadata": sql_metadata, "env_overrides": env_overrides}

    if as_json:
        print(json.dumps(output, indent=2))
        return

    print("=" * 60)
    print("CONFIGURATION")
    print("=" * 60)
    print("\n[JSON CONFIG] mem.config.json")
    print("-" * 40)
    for key, value in config.config.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                if not k.startswith('_'):
                    print(f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")

    print("\n[SQL METADATA] Database")
    print("-" * 40)
    if sql_metadata:
        for key, value in sql_metadata.items():
            display = value[:30] + "..." if key == "backup_repo" and len(value) > 30 else value
            print(f"  {key}: {display}")
    else:
        print("  (none)")

    if env_overrides:
        print("\n[ENV OVERRIDES] Active")
        print("-" * 40)
        for key, value in env_overrides.items():
            print(f"  {key}: {value}")
    print()


def save_json_config(config_path: Path, config_data: dict):
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2)
        f.write('\n')


def main():
    parser = argparse.ArgumentParser(description="View and manage project configuration")
    parser.add_argument("--project", help="Project name")
    parser.add_argument("--show", action="store_true", help="Show all settings")
    parser.add_argument("--show-json", action="store_true", help="Show all settings as JSON")
    parser.add_argument("--get", metavar="KEY", help="Get specific setting (dot notation)")
    parser.add_argument("--set", nargs=2, metavar=("KEY", "VALUE"), help="Set JSON config value")
    parser.add_argument("--set-sql", nargs=2, metavar=("KEY", "VALUE"), help="Set SQL metadata value")
    parser.add_argument("--list-sql", action="store_true", help="List SQL metadata")
    args = parser.parse_args()

    config_path = Path("mem.config.json")
    if not config_path.exists():
        safe_print("[ERROR] mem.config.json not found. Run init.md first.")
        sys.exit(1)

    config = load_config(project_name=args.project)

    if args.show:
        show_config(config, as_json=False)
        return
    if args.show_json:
        show_config(config, as_json=True)
        return
    if args.get:
        value = get_nested_value(config.config, args.get)
        if value is not None:
            print(json.dumps(value, indent=2) if isinstance(value, dict) else value)
        else:
            sql_metadata = load_sql_metadata(config)
            if args.get in sql_metadata:
                print(sql_metadata[args.get])
            else:
                safe_print(f"[ERROR] Setting not found: {args.get}")
                sys.exit(1)
        return
    if args.set:
        key, value = args.set
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        try:
            parsed_value = json.loads(value)
        except json.JSONDecodeError:
            parsed_value = value
        set_nested_value(config_data, key, parsed_value)
        save_json_config(config_path, config_data)
        safe_print(f"[OK] Set {key} = {parsed_value}")
        return
    if args.set_sql:
        if not args.project:
            safe_print("[ERROR] --project required with --set-sql")
            sys.exit(1)
        key, value = args.set_sql
        set_sql_metadata(config, key, value)
        safe_print(f"[OK] Set SQL metadata: {key}")
        safe_print("  Stored in database (not config file)")
        return
    if args.list_sql:
        if not args.project:
            safe_print("[ERROR] --project required with --list-sql")
            sys.exit(1)
        sql_metadata = load_sql_metadata(config)
        if sql_metadata:
            print("\n[SQL METADATA]")
            print("-" * 40)
            for key, value in sql_metadata.items():
                print(f"  {key}: {value}")
            print()
        else:
            safe_print("[INFO] No SQL metadata found")
        return

    parser.print_help()


if __name__ == "__main__":
    main()

