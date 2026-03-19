"""
Console utilities for cross-platform output handling.
"""

import sys
import os


def safe_print(*args, **kwargs):
    """
    Print that handles encoding issues on Windows console.
    Falls back to ASCII-safe output if Unicode fails.
    """
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Windows console can't handle emojis, strip them
        safe_args = []
        for arg in args:
            if isinstance(arg, str):
                # Remove common emojis and replace with ASCII equivalents
                safe_arg = arg
                emoji_map = {
                    '[OK]': '[OK]',
                    '[ERROR]': '[ERROR]',
                    '[WARNING]': '[WARNING]',
                    '[SEARCH]': '[SEARCH]',
                    '[DATA]': '[DATA]',
                    '[NOTE]': '[NOTE]',
                    '[AI]': '[AI]',
                    '[SYNC]': '[SYNC]',
                    '[SAVE]': '[SAVE]',
                    '[START]': '[START]',
                    '[SKIP]': '[SKIP]',
                    '[LINK]': '[LINK]',
                }
                for emoji, replacement in emoji_map.items():
                    safe_arg = safe_arg.replace(emoji, replacement)
                safe_args.append(safe_arg)
            else:
                safe_args.append(arg)
        print(*safe_args, **kwargs)


def setup_console_encoding():
    """
    Attempt to set up UTF-8 encoding for console output.
    This is best-effort and may not work on all systems.
    """
    if sys.platform == 'win32':
        try:
            # Try to set console to UTF-8
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleCP(65001)
            kernel32.SetConsoleOutputCP(65001)
        except:
            pass  # Silently fail if we can't set it
        
        # Also try to reconfigure stdout/stderr
        try:
            import io
            if hasattr(sys.stdout, 'buffer'):
                sys.stdout = io.TextIOWrapper(
                    sys.stdout.buffer,
                    encoding='utf-8',
                    errors='replace',
                    line_buffering=True
                )
            if hasattr(sys.stderr, 'buffer'):
                sys.stderr = io.TextIOWrapper(
                    sys.stderr.buffer,
                    encoding='utf-8',
                    errors='replace',
                    line_buffering=True
                )
        except:
            pass  # Silently fail

