#!/usr/bin/env python3
"""
Secure backup - Create encrypted backups of memory databases.

Uses AES-256 encrypted zip (compatible with 7zip, WinRAR, etc.)
"""

import sys
import os
import json
import argparse
import getpass
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.config import load_config
from tools.console_utils import safe_print

try:
    import pyzipper
except ImportError:
    safe_print("[ERROR] pyzipper not installed. Run: pip install pyzipper")
    sys.exit(1)


BACKUP_EXAMPLES = """
Examples:
  # Backup with password prompt (user runs manually)
  python scripts/backup_secure.py --project llm_memory --output backups/backup.zip --prompt

  # Backup with password from file
  python scripts/backup_secure.py --project llm_memory --output backups/backup.zip --password-file tmp/pass.txt

  # Backup using commit hash from configured private repo
  python scripts/backup_secure.py --project llm_memory --output backups/backup.zip --use-commit-hash

  # Restore to staging directory (safe default)
  python scripts/backup_secure.py --restore backups/backup.zip --prompt

  # Restore with overwrite (explicit)
  python scripts/backup_secure.py --restore backups/backup.zip --restore-to memory/ --allow-overwrite --prompt

  # Configure backup repo (stored in SQL, not config file)
  python scripts/backup_secure.py --project llm_memory --set-repo github.com/username/private-repo

Status:
  --use-commit-hash requires private repo. Public repo commit hashes are NOT secure passwords.
"""


class BackupArgumentParser(argparse.ArgumentParser):
    """Custom parser that prints examples on error."""
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: error: {message}\n{BACKUP_EXAMPLES}")





def get_backup_repo_from_sql(config) -> str:
    """Get backup_repo URL from SQL metadata."""
    import sqlite3
    sql_path = config.get_sql_db_path()
    if not Path(sql_path).exists():
        return None

    conn = sqlite3.connect(sql_path)
    cursor = conn.cursor()

    # Check if metadata table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metadata'")
    if not cursor.fetchone():
        conn.close()
        return None

    cursor.execute("SELECT value FROM metadata WHERE key = 'backup_repo'")
    row = cursor.fetchone()
    conn.close()

    return row[0] if row else None


def set_backup_repo_in_sql(config, repo_url: str):
    """Store backup_repo URL in SQL metadata."""
    import sqlite3
    sql_path = config.get_sql_db_path()

    conn = sqlite3.connect(sql_path)
    cursor = conn.cursor()

    # Create metadata table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT
        )
    """)

    cursor.execute("""
        INSERT OR REPLACE INTO metadata (key, value, updated_at)
        VALUES ('backup_repo', ?, ?)
    """, (repo_url, datetime.now(timezone.utc).isoformat()))

    conn.commit()
    conn.close()


def fetch_commit_hash(repo_url: str) -> str:
    """Fetch latest commit hash from GitHub API."""
    import urllib.request
    import urllib.error

    # Parse repo URL: github.com/user/repo -> user/repo
    repo_url = repo_url.replace("https://", "").replace("http://", "")
    if repo_url.startswith("github.com/"):
        repo_path = repo_url[len("github.com/"):]
    else:
        repo_path = repo_url

    api_url = f"https://api.github.com/repos/{repo_path}/commits?per_page=1"

    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "backup_secure.py"})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            if data and len(data) > 0:
                return data[0]["sha"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            safe_print(f"[ERROR] Repository not found: {repo_path}")
        elif e.code == 403:
            safe_print(f"[ERROR] API rate limited or repo is private without auth")
        else:
            safe_print(f"[ERROR] GitHub API error: {e.code}")
        return None
    except Exception as e:
        safe_print(f"[ERROR] Failed to fetch commit hash: {e}")
        return None

    return None





def collect_backup_files(config, project_name: str) -> list:
    """Collect minimum files needed for backup."""
    files = []

    # SQL database
    sql_path = Path(config.get_sql_db_path())
    if sql_path.exists():
        files.append(sql_path)

    # Graph database directory
    graph_path = Path(config.get_graph_db_path())
    if graph_path.exists():
        for f in graph_path.rglob("*"):
            if f.is_file():
                files.append(f)

    return files


def create_backup(project_name: str, output_path: str, password: bytes,
                  password_source: str, repo_url: str = None, commit_sha: str = None):
    """Create encrypted backup archive."""
    config = load_config(project_name=project_name)

    files = collect_backup_files(config, project_name)
    if not files:
        safe_print("[ERROR] No files found to backup")
        sys.exit(1)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    safe_print(f"\n[BACKUP] Creating encrypted archive: {output}")
    safe_print(f"  Project: {project_name}")
    safe_print(f"  Password source: {password_source}")
    if commit_sha:
        safe_print(f"  Commit: {commit_sha[:12]}...")
    safe_print(f"  Files: {len(files)}")

    with pyzipper.AESZipFile(output, 'w', compression=pyzipper.ZIP_DEFLATED,
                              encryption=pyzipper.WZ_AES) as zf:
        zf.setpassword(password)

        # Add each file preserving relative paths
        base_path = Path(".")
        for filepath in files:
            arcname = str(filepath.relative_to(base_path) if filepath.is_relative_to(base_path) else filepath.name)
            safe_print(f"  + {arcname}")
            zf.write(filepath, arcname)

    safe_print(f"\n[SUCCESS] Backup created: {output}")
    safe_print(f"  Size: {output.stat().st_size:,} bytes")
    safe_print(f"  Encryption: AES-256")




def restore_backup(archive_path: str, password: bytes, restore_to: str = None,
                   allow_overwrite: bool = False):
    """Restore from encrypted backup archive."""
    archive = Path(archive_path)
    if not archive.exists():
        safe_print(f"[ERROR] Archive not found: {archive}")
        sys.exit(1)

    # Default to staging directory
    if restore_to is None:
        restore_to = f"restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    target = Path(restore_to)

    if target.exists() and not allow_overwrite:
        safe_print(f"[ERROR] Target directory exists: {target}")
        safe_print(f"  Use --allow-overwrite to overwrite, or choose different --restore-to")
        sys.exit(1)

    safe_print(f"\n[RESTORE] Extracting encrypted archive: {archive}")
    safe_print(f"  Target: {target}")

    target.mkdir(parents=True, exist_ok=True)

    try:
        with pyzipper.AESZipFile(archive, 'r') as zf:
            zf.setpassword(password)

            # Extract all files
            file_count = 0
            for info in zf.infolist():
                safe_print(f"  + {info.filename}")
                zf.extract(info, target)
                file_count += 1

        safe_print(f"\n[SUCCESS] Restored {file_count} files to: {target}")

    except RuntimeError as e:
        if "password" in str(e).lower() or "bad" in str(e).lower():
            safe_print("[ERROR] Incorrect password")
        else:
            safe_print(f"[ERROR] Failed to extract: {e}")
        sys.exit(1)


def main():
    parser = BackupArgumentParser(
        description="Secure backup - Create encrypted backups of memory databases",
        epilog=BACKUP_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Backup mode
    parser.add_argument("--project", help="Project name to backup")
    parser.add_argument("--output", help="Output path for encrypted archive")

    # Restore mode
    parser.add_argument("--restore", help="Path to archive to restore")
    parser.add_argument("--restore-to", help="Target directory (default: staging dir)")
    parser.add_argument("--allow-overwrite", action="store_true", help="Allow overwriting target")

    # Password sources (mutually exclusive)
    pw_group = parser.add_mutually_exclusive_group()
    pw_group.add_argument("--password-file", help="Read password from file")
    pw_group.add_argument("--use-commit-hash", action="store_true",
                          help="Use commit hash from configured private repo")
    pw_group.add_argument("--prompt", action="store_true", help="Prompt for password")

    # Configuration
    parser.add_argument("--set-repo", help="Configure backup repo (stored in SQL)")
    parser.add_argument("--show-repo", action="store_true", help="Show configured backup repo")

    args = parser.parse_args()

    # Handle repo configuration
    if args.set_repo:
        if not args.project:
            safe_print("[ERROR] --project required with --set-repo")
            sys.exit(1)
        config = load_config(project_name=args.project)
        set_backup_repo_in_sql(config, args.set_repo)
        safe_print(f"[OK] Backup repo set: {args.set_repo}")
        safe_print(f"  Stored in SQL metadata (not config file)")
        return

    if args.show_repo:
        if not args.project:
            safe_print("[ERROR] --project required with --show-repo")
            sys.exit(1)
        config = load_config(project_name=args.project)
        repo = get_backup_repo_from_sql(config)
        if repo:
            safe_print(f"Backup repo: {repo}")
        else:
            safe_print("No backup repo configured")
        return

    # Determine password
    password = None
    password_source = None
    repo_url = None
    commit_sha = None

    if args.password_file:
        pw_path = Path(args.password_file)
        if not pw_path.exists():
            safe_print(f"[ERROR] Password file not found: {pw_path}")
            sys.exit(1)
        password = pw_path.read_text().strip().encode('utf-8')
        password_source = "password-file"

    elif args.use_commit_hash:
        if not args.project:
            safe_print("[ERROR] --project required with --use-commit-hash")
            sys.exit(1)
        config = load_config(project_name=args.project)
        repo_url = get_backup_repo_from_sql(config)
        if not repo_url:
            safe_print("[ERROR] No backup repo configured")
            safe_print("  Use --set-repo to configure, or use --password-file / --prompt")
            sys.exit(1)
        safe_print(f"[INFO] Fetching commit hash from: {repo_url}")
        commit_sha = fetch_commit_hash(repo_url)
        if not commit_sha:
            safe_print("[ERROR] Failed to fetch commit hash")
            safe_print("  Use --password-file or --prompt instead")
            sys.exit(1)
        safe_print(f"[INFO] Using commit: {commit_sha[:12]}...")
        password = commit_sha.encode('utf-8')
        password_source = "commit-hash"

    elif args.prompt:
        if args.restore:
            password = getpass.getpass("Password: ").encode('utf-8')
        else:
            password = getpass.getpass("Password: ").encode('utf-8')
            confirm = getpass.getpass("Confirm password: ").encode('utf-8')
            if password != confirm:
                safe_print("[ERROR] Passwords do not match")
                sys.exit(1)
        password_source = "prompt"

    # Handle restore
    if args.restore:
        if not password:
            safe_print("[ERROR] Password required. Use --password-file, --prompt, or --use-commit-hash")
            sys.exit(1)
        restore_backup(args.restore, password, args.restore_to, args.allow_overwrite)
        return

    # Handle backup
    if args.project and args.output:
        if not password:
            safe_print("[ERROR] Password required. Use --password-file, --prompt, or --use-commit-hash")
            sys.exit(1)
        create_backup(args.project, args.output, password, password_source, repo_url, commit_sha)
        return

    # No valid action
    safe_print("[ERROR] Must specify backup (--project + --output) or restore (--restore)")
    safe_print("  Use --help for usage")
    sys.exit(1)


if __name__ == "__main__":
    main()