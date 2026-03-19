#!/usr/bin/env python3
"""
Install git post-commit hook for code graph tracking.

This creates a post-commit hook that automatically captures code changes.
"""

import os
import sys
import stat
import shutil


def install_hook():
    """Install the post-commit hook."""
    # Check if we're in a git repository
    if not os.path.exists('.git'):
        print("[ERROR] Not in a git repository!")
        print("Run this from the repository root.")
        return 1
    
    # Create hooks directory if it doesn't exist
    hooks_dir = '.git/hooks'
    os.makedirs(hooks_dir, exist_ok=True)
    
    # Path to hook file
    hook_path = os.path.join(hooks_dir, 'post-commit')
    
    # Check if hook already exists
    if os.path.exists(hook_path):
        response = input(f"Hook already exists at {hook_path}. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("[CANCELLED] Hook installation cancelled.")
            return 0
        
        # Backup existing hook
        backup_path = hook_path + '.backup'
        shutil.copy(hook_path, backup_path)
        print(f"[INFO] Backed up existing hook to {backup_path}")
    
    # Get Python executable path
    python_exe = sys.executable
    
    # Get absolute path to hook script
    script_path = os.path.abspath('scripts/git_post_commit_hook.py')
    
    # Create hook content
    if os.name == 'nt':  # Windows
        hook_content = f"""#!/bin/sh
# Auto-generated post-commit hook for LLM Memory code graph
"{python_exe}" "{script_path}"
"""
    else:  # Unix/Linux/Mac
        hook_content = f"""#!/bin/sh
# Auto-generated post-commit hook for LLM Memory code graph
"{python_exe}" "{script_path}"
"""
    
    # Write hook file
    with open(hook_path, 'w', newline='\n') as f:
        f.write(hook_content)
    
    # Make hook executable (Unix/Linux/Mac)
    if os.name != 'nt':
        st = os.stat(hook_path)
        os.chmod(hook_path, st.st_mode | stat.S_IEXEC)
    
    print(f"[SUCCESS] Post-commit hook installed at {hook_path}")
    print(f"[INFO] Python: {python_exe}")
    print(f"[INFO] Script: {script_path}")
    print()
    print("The hook will now run automatically after each commit.")
    print("It will capture:")
    print("  - Commit metadata (hash, message, author, timestamp)")
    print("  - Changed files")
    print("  - Lines added/removed")
    print()
    print("To disable the hook, delete or rename:")
    print(f"  {hook_path}")
    
    return 0


if __name__ == '__main__':
    sys.exit(install_hook())

