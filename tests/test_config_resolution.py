"""Tests for config, interpreter, and cwd resolution.

These tests verify that:
1. python_path from config is used for subprocess calls
2. MEM_CONFIG env var is respected
3. cwd resolution works from different directories
4. Fallback behavior when config is missing

These are regression tests for bugs we hit during MCP async sync implementation.
"""

import sys

# Python 3.10+ required for mcp package
if sys.version_info < (3, 10):
    sys.exit(
        "ERROR: These tests require Python 3.10+.\n"
        "Current: Python {}.{}\n"
        "Fix: Update mem.config.json python_path to python3.11".format(
            sys.version_info.major, sys.version_info.minor
        )
    )

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.config import load_config, Config


@pytest.fixture
def repo_root():
    """Return the repository root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory with a config file."""
    temp_dir = tempfile.mkdtemp()
    
    config = {
        "version": "1.0.0",
        "python_path": "/custom/python3.11",
        "data_dir": temp_dir,
        "projects": {
            "test_project": {"description": "Test"}
        }
    }
    
    config_path = os.path.join(temp_dir, "mem.config.json")
    with open(config_path, "w") as f:
        json.dump(config, f)
    
    yield temp_dir, config_path
    
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestPythonPathResolution:
    """Tests for python_path config resolution."""

    def test_get_python_path_returns_configured_value(self, temp_config_dir):
        """Test that get_python_path returns the configured interpreter."""
        temp_dir, config_path = temp_config_dir
        
        config = load_config(config_path=config_path)
        
        assert config.get_python_path() == "/custom/python3.11"

    def test_get_python_path_fallback_when_not_set(self, temp_config_dir):
        """Test fallback when python_path is not in config."""
        temp_dir, config_path = temp_config_dir
        
        # Remove python_path from config
        with open(config_path) as f:
            cfg = json.load(f)
        del cfg["python_path"]
        with open(config_path, "w") as f:
            json.dump(cfg, f)
        
        config = load_config(config_path=config_path)
        
        # Should fallback to "python3" or similar
        python_path = config.get_python_path()
        assert python_path is not None
        assert "python" in python_path.lower()

    def test_worker_get_python_path_uses_config(self):
        """Test that worker's get_python_path reads from config."""
        from scripts.process_sync_jobs import get_python_path
        
        mock_config = MagicMock()
        mock_config.get_python_path.return_value = "/usr/bin/python3.11"
        
        result = get_python_path(mock_config)
        
        assert result == "/usr/bin/python3.11"
        mock_config.get_python_path.assert_called_once()

    def test_worker_get_python_path_fallback(self):
        """Test that worker falls back to python3 if config method missing."""
        from scripts.process_sync_jobs import get_python_path
        
        # Config object without get_python_path method
        mock_config = MagicMock(spec=[])
        
        result = get_python_path(mock_config)
        
        assert result == "python3"


class TestMemConfigEnvVar:
    """Tests for MEM_CONFIG environment variable."""

    def test_load_config_respects_mem_config_env(self, temp_config_dir):
        """Test that MEM_CONFIG env var is used."""
        temp_dir, config_path = temp_config_dir
        
        original_env = os.environ.get("MEM_CONFIG")
        try:
            os.environ["MEM_CONFIG"] = config_path
            
            config = load_config()
            
            assert config.config_path == config_path
        finally:
            if original_env:
                os.environ["MEM_CONFIG"] = original_env
            else:
                os.environ.pop("MEM_CONFIG", None)

    def test_cli_config_overrides_env_var(self, temp_config_dir, repo_root):
        """Test that --config CLI arg overrides MEM_CONFIG env."""
        temp_dir, config_path = temp_config_dir
        
        # Create a second config
        other_dir = tempfile.mkdtemp()
        other_config = {
            "version": "1.0.0",
            "python_path": "/other/python",
            "data_dir": other_dir,
            "projects": {}
        }
        other_config_path = os.path.join(other_dir, "mem.config.json")
        with open(other_config_path, "w") as f:
            json.dump(other_config, f)
        
        try:
            # MEM_CONFIG points to temp_config, but we pass other_config via CLI
            original_env = os.environ.get("MEM_CONFIG")
            os.environ["MEM_CONFIG"] = config_path
            
            config = load_config(config_path=other_config_path)
            
            assert config.config_path == other_config_path
            assert config.get_python_path() == "/other/python"
        finally:
            if original_env:
                os.environ["MEM_CONFIG"] = original_env
            else:
                os.environ.pop("MEM_CONFIG", None)
            shutil.rmtree(other_dir, ignore_errors=True)

