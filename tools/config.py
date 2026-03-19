"""
Configuration management for LLM Memory System.

Loads configuration from multiple sources with priority:
1. Command-line arguments (highest priority)
2. Environment variables
3. Project config file (mem.config.json)
4. Global config file (~/.mem/config.json)
5. Defaults (lowest priority)
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any


class Config:
    """Configuration manager with layered loading."""
    
    def __init__(
        self,
        project_name: Optional[str] = None,
        cli_args: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None,
    ):
        """
        Initialize configuration.
        
        Args:
            project_name: Explicit project name (overrides all other sources)
            cli_args: Command-line arguments (highest priority)
            config_path: Explicit config file path
        """
        self.cli_args = cli_args or {}
        self.config_path = config_path or self.cli_args.get("config") or os.getenv("MEM_CONFIG")
        self.config = self._load_config(project_name)
    
    def _load_config(self, project_name: Optional[str]) -> Dict[str, Any]:
        """Load configuration from all sources in priority order."""
        # 1. Start with defaults
        config = self._get_defaults()
        
        # 2. Load global config (~/.mem/config.json)
        global_config = self._load_global_config()
        if global_config:
            config = self._merge_config(config, global_config)
        
        # 3. Load project config (explicit path or local mem.config.json)
        project_config = self._load_project_config()
        if project_config:
            config = self._merge_config(config, project_config)

        configured_project = project_config.get("project_name") if project_config else None
        requested_project = self.cli_args.get("project") or project_name
        self._fail_on_project_override(configured_project, requested_project)
        
        # 4. Override with environment variables
        config = self._apply_env_vars(config)
        
        # 5. Override with explicit project_name
        if project_name:
            config['project_name'] = project_name
        
        # 6. Override with CLI arguments (highest priority)
        config = self._apply_cli_args(config)
        
        return config

    def _fail_on_project_override(
        self,
        configured_project: Optional[str],
        requested_project: Optional[str],
    ) -> None:
        """Fail loudly when CLI/explicit project overrides local config."""
        if not configured_project or not requested_project:
            return
        if configured_project == requested_project:
            return

        command_name = Path(sys.argv[0]).name if sys.argv else "unknown-command"
        print(file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        print("PROJECT CONFIG MISMATCH - ABORTING", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        print(
            f"Command: {command_name}",
            file=sys.stderr,
        )
        print(
            f"Configured project in mem.config.json: {configured_project}",
            file=sys.stderr,
        )
        print(
            f"Requested project from CLI/runtime:   {requested_project}",
            file=sys.stderr,
        )
        print(file=sys.stderr)
        print(
            "Refusing to continue because the requested project conflicts with mem.config.json.",
            file=sys.stderr,
        )
        print(
            "Continuing here could read from or write to a different graph database than the file suggests.",
            file=sys.stderr,
        )
        print(
            "Fix mem.config.json or stop passing a conflicting --project value.",
            file=sys.stderr,
        )
        print("=" * 80, file=sys.stderr)
        print(file=sys.stderr)
        raise SystemExit(2)
    
    def _get_defaults(self) -> Dict[str, Any]:
        """Get default configuration values."""
        return {
            "project_name": None,
            "database": {
                "sql_path": "./memory/conversations.db",
                "graph_path": "./memory/{project_name}.graph"
            },
            "extraction": {
                "version": "v1.0.0",
                "skip_quality_check": False
            },
            "paths": {
                "tmp_dir": "./tmp",
                "memory_dir": "./memory"
            },
            "quality_check": {
                "questions_file": "quality-questions.json",
                "answers_file": "quality-answers.json"
            },
            "mcp": {
                "network_mode": "localhost",
                "bind_host": "127.0.0.1",
                "bind_port": 8765,
                "tls_enabled": False,
                "tls_cert_path": None,
                "tls_key_path": None,
                "mtls_required": False,
                "client_ca_cert_path": None,
                "tls_verify_client": False,
                "trust_client_cert_proxy_headers": False,
                "trusted_proxy_subnets": [],
                "allowed_subnets": [],
                "deny_public_ips": True
            }
        }
    
    def _load_global_config(self) -> Optional[Dict[str, Any]]:
        """Load global config from ~/.mem/config.json."""
        global_path = Path.home() / ".mem" / "config.json"
        if global_path.exists():
            try:
                with open(global_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"[WARNING] Failed to load global config: {e}")
        return None
    
    def _load_project_config(self) -> Optional[Dict[str, Any]]:
        """Load project config from explicit path or mem.config.json in current directory."""
        project_path = Path(self.config_path) if self.config_path else Path("mem.config.json")
        if project_path.exists():
            try:
                with open(project_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"[WARNING] Failed to load project config: {e}")
        return None
    
    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two configuration dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result
    
    def _apply_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides."""
        # Project name
        if os.getenv("MEM_PROJECT"):
            config["project_name"] = os.getenv("MEM_PROJECT")

        # Database paths
        if os.getenv("MEM_SQL_DB"):
            config["database"]["sql_path"] = os.getenv("MEM_SQL_DB")

        if os.getenv("MEM_GRAPH_DB"):
            config["database"]["graph_path"] = os.getenv("MEM_GRAPH_DB")

        # Extraction settings
        if os.getenv("MEM_EXTRACTION_VERSION"):
            config["extraction"]["version"] = os.getenv("MEM_EXTRACTION_VERSION")

        if os.getenv("MEM_SKIP_QUALITY_CHECK"):
            config["extraction"]["skip_quality_check"] = os.getenv("MEM_SKIP_QUALITY_CHECK").lower() == "true"

        return config

    def _apply_cli_args(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply command-line argument overrides."""
        if self.cli_args.get("project"):
            config["project_name"] = self.cli_args["project"]

        if self.cli_args.get("sql_db"):
            config["database"]["sql_path"] = self.cli_args["sql_db"]

        if self.cli_args.get("graph_db"):
            config["database"]["graph_path"] = self.cli_args["graph_db"]

        return config

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-notation key.

        Args:
            key: Dot-notation key (e.g., "database.sql_path")
            default: Default value if key not found

        Returns:
            Configuration value or default

        Examples:
            >>> config.get("project_name")
            "my-project"
            >>> config.get("database.sql_path")
            "./memory/conversations.db"
        """
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    def get_sql_db_path(self) -> str:
        """Get SQL database path."""
        return self.get("database.sql_path")

    def get_graph_db_path(self, project_name: Optional[str] = None) -> str:
        """
        Get graph database path.

        Resolves `{project_name}` placeholders and applies a compatibility
        fallback when the configured path is project-specific for the current
        repo but a different project name is requested.
        """
        graph_path = self.get("database.graph_path")
        requested_project = project_name or self.get_project_name()
        configured_project = self.get("project_name")

        if not graph_path:
            memory_dir = self.get("paths.memory_dir", "./memory")
            if requested_project:
                return str(Path(memory_dir) / f"{requested_project}.graph")
            return str(Path(memory_dir) / "knowledge.graph")

        if requested_project and "{project_name}" in graph_path:
            return graph_path.replace("{project_name}", requested_project)

        if requested_project and configured_project and requested_project != configured_project:
            graph_path_obj = Path(graph_path)
            suffix = "".join(graph_path_obj.suffixes)
            stem = graph_path_obj.name[:-len(suffix)] if suffix else graph_path_obj.name

            # Compatibility: if config is pinned to the repo's current project DB,
            # reuse the same directory/extension for other project names.
            if stem == configured_project:
                return str(graph_path_obj.with_name(f"{requested_project}{suffix}"))

        return graph_path

    def get_project_name(self) -> Optional[str]:
        """Get project name."""
        return self.get("project_name")

    def get_memory_dir(self) -> str:
        """Get memory directory."""
        return self.get("paths.memory_dir", "./memory")

    def get_tmp_dir(self) -> str:
        """Get temporary directory."""
        return self.get("paths.tmp_dir", "./tmp")

    def get_python_path(self) -> str:
        """Get configured Python interpreter path, with platform-aware fallback."""
        python_path = self.get("python_path")
        if python_path:
            return python_path
        if os.name == "nt":
            return ".\\python313\\python.exe"
        return "python3"

    def get_mcp_config(self) -> Dict[str, Any]:
        """Get MCP server configuration section."""
        return self.get("mcp", {
            "network_mode": "localhost",
            "bind_host": "127.0.0.1",
            "bind_port": 8765,
            "tls_enabled": False,
            "tls_cert_path": None,
            "tls_key_path": None,
            "mtls_required": False,
            "client_ca_cert_path": None,
            "tls_verify_client": False,
            "trust_client_cert_proxy_headers": False,
            "trusted_proxy_subnets": [],
            "allowed_subnets": [],
            "deny_public_ips": True
        })

    def to_dict(self) -> Dict[str, Any]:
        """Get full configuration as dictionary."""
        return self.config.copy()

    def __repr__(self) -> str:
        """String representation."""
        return f"Config(project={self.get_project_name()}, sql={self.get_sql_db_path()}, graph={self.get_graph_db_path()})"


def load_config(
    project_name: Optional[str] = None,
    cli_args: Optional[Dict[str, Any]] = None,
    config_path: Optional[str] = None,
) -> Config:
    """
    Load configuration from all sources.

    Args:
        project_name: Explicit project name
        cli_args: Command-line arguments

    Returns:
        Config object

    Example:
        >>> config = load_config(project_name="my-project")
        >>> config.get("database.sql_path")
        "./memory/conversations.db"
    """
    return Config(project_name=project_name, cli_args=cli_args, config_path=config_path)
