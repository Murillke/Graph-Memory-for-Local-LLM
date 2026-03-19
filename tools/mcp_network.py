"""
MCP Network Validation Utilities.

Implements the network posture rules from docs/MCP-NETWORK-POSTURE.md:
- RFC1918 private subnet validation
- Bind host validation
- Network mode configuration
- TLS requirement enforcement

This module is used by the MCP server to validate configuration
before starting and to reject invalid network configurations.
"""

import ipaddress
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any


# RFC1918 private address ranges
RFC1918_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]

# Loopback
LOOPBACK_NETWORK = ipaddress.ip_network("127.0.0.0/8")

# Hard-banned bind addresses
BANNED_BIND_ADDRESSES = frozenset(["0.0.0.0", "::"])


@dataclass
class MCPNetworkConfig:
    """MCP server network configuration."""

    network_mode: str = "localhost"  # "localhost" or "private"
    bind_host: str = "127.0.0.1"
    bind_port: int = 8765
    tls_enabled: bool = False
    tls_cert_path: Optional[str] = None
    tls_key_path: Optional[str] = None
    mtls_required: bool = False
    client_ca_cert_path: Optional[str] = None
    tls_verify_client: bool = False
    trust_client_cert_proxy_headers: bool = False
    trusted_proxy_subnets: List[str] = field(default_factory=list)
    allowed_subnets: List[str] = field(default_factory=list)
    deny_public_ips: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPNetworkConfig":
        """Create config from dictionary (e.g., from JSON)."""
        return cls(
            network_mode=data.get("network_mode", "localhost"),
            bind_host=data.get("bind_host", "127.0.0.1"),
            bind_port=data.get("bind_port", 8765),
            tls_enabled=data.get("tls_enabled", False),
            tls_cert_path=data.get("tls_cert_path"),
            tls_key_path=data.get("tls_key_path"),
            mtls_required=data.get("mtls_required", data.get("tls_verify_client", False)),
            client_ca_cert_path=data.get("client_ca_cert_path"),
            tls_verify_client=data.get("tls_verify_client", data.get("mtls_required", False)),
            trust_client_cert_proxy_headers=data.get("trust_client_cert_proxy_headers", False),
            trusted_proxy_subnets=data.get("trusted_proxy_subnets", []),
            allowed_subnets=data.get("allowed_subnets", []),
            deny_public_ips=data.get("deny_public_ips", True),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "network_mode": self.network_mode,
            "bind_host": self.bind_host,
            "bind_port": self.bind_port,
            "tls_enabled": self.tls_enabled,
            "tls_cert_path": self.tls_cert_path,
            "tls_key_path": self.tls_key_path,
            "mtls_required": self.mtls_required,
            "client_ca_cert_path": self.client_ca_cert_path,
            "tls_verify_client": self.tls_verify_client,
            "trust_client_cert_proxy_headers": self.trust_client_cert_proxy_headers,
            "trusted_proxy_subnets": self.trusted_proxy_subnets,
            "allowed_subnets": self.allowed_subnets,
            "deny_public_ips": self.deny_public_ips,
        }


def is_rfc1918_subnet(subnet_str: str) -> bool:
    """
    Check if a subnet falls entirely within RFC1918 private space.
    
    Args:
        subnet_str: CIDR notation subnet (e.g., "192.168.1.0/24")
        
    Returns:
        True if subnet is within RFC1918 ranges
    """
    try:
        subnet = ipaddress.ip_network(subnet_str, strict=False)
    except ValueError:
        return False

    return any(subnet.subnet_of(rfc) for rfc in RFC1918_NETWORKS)


def is_loopback_address(addr_str: str) -> bool:
    """Check if an address is a loopback address."""
    try:
        addr = ipaddress.ip_address(addr_str)
        return addr.is_loopback
    except ValueError:
        return False


def is_private_address(addr_str: str) -> bool:
    """Check if an address is in RFC1918 private space or loopback."""
    try:
        addr = ipaddress.ip_address(addr_str)
        return addr.is_private or addr.is_loopback
    except ValueError:
        return False


def validate_allowed_subnets(subnets: List[str]) -> List[str]:
    """
    Validate that all subnets are within RFC1918 private ranges or loopback.

    Args:
        subnets: List of CIDR notation subnets

    Returns:
        List of error messages, empty if all valid
    """
    errors: List[str] = []

    for subnet_str in subnets:
        try:
            subnet = ipaddress.ip_network(subnet_str, strict=False)
        except ValueError as e:
            errors.append(f"Invalid subnet '{subnet_str}': {e}")
            continue

        # Allow loopback for local testing
        if subnet.is_loopback:
            continue

        if not any(subnet.subnet_of(rfc) for rfc in RFC1918_NETWORKS):
            errors.append(
                f"Subnet '{subnet_str}' is not within RFC1918 private ranges or loopback. "
                f"Allowed: 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16"
            )

    return errors


def validate_proxy_subnets(subnets: List[str]) -> List[str]:
    """Trusted proxy subnets may be RFC1918 private ranges or loopback."""
    errors: List[str] = []

    for subnet_str in subnets:
        try:
            subnet = ipaddress.ip_network(subnet_str, strict=False)
        except ValueError as e:
            errors.append(f"Invalid trusted proxy subnet '{subnet_str}': {e}")
            continue

        if subnet.is_loopback:
            continue

        if not any(subnet.subnet_of(rfc) for rfc in RFC1918_NETWORKS):
            errors.append(
                f"Trusted proxy subnet '{subnet_str}' is not loopback or RFC1918 private space. "
                f"Allowed: 127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16"
            )

    return errors


def validate_bind_host(host: str, network_mode: str) -> List[str]:
    """
    Validate bind host according to network mode.
    
    Args:
        host: IP address to bind to
        network_mode: "localhost" or "private"
        
    Returns:
        List of error messages, empty if valid
    """
    errors: List[str] = []

    # Hard ban on wildcard addresses
    if host in BANNED_BIND_ADDRESSES:
        errors.append(
            f"Bind address '{host}' is banned. "
            f"Use specific IP address instead of wildcard."
        )
        return errors

    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        errors.append(f"Invalid bind host '{host}': not a valid IP address")
        return errors

    if network_mode == "localhost":
        if not addr.is_loopback:
            errors.append(
                f"Bind host '{host}' is not loopback. "
                f"In localhost mode, must bind to 127.0.0.1 or ::1"
            )
    elif network_mode == "private":
        if not (addr.is_private or addr.is_loopback):
            errors.append(
                f"Bind host '{host}' is not a private IP address. "
                f"In private mode, must bind to RFC1918 or loopback address"
            )

    return errors


def validate_tls_config(config: MCPNetworkConfig) -> List[str]:
    """
    Validate TLS configuration.

    Args:
        config: MCP network configuration

    Returns:
        List of error messages, empty if valid
    """
    errors: List[str] = []

    # TLS is required for private network mode
    if config.network_mode == "private" and not config.tls_enabled:
        errors.append(
            "TLS is required for private network mode. "
            "Set tls_enabled=true and provide cert/key paths."
        )
        return errors

    # If TLS is enabled, cert and key paths are required
    if config.tls_enabled:
        if not config.tls_cert_path:
            errors.append("TLS enabled but tls_cert_path not specified")
        elif not Path(config.tls_cert_path).exists():
            errors.append(f"TLS certificate not found: {config.tls_cert_path}")

        if not config.tls_key_path:
            errors.append("TLS enabled but tls_key_path not specified")
        elif not Path(config.tls_key_path).exists():
            errors.append(f"TLS key not found: {config.tls_key_path}")

    effective_mtls = config.mtls_required or config.tls_verify_client
    if config.network_mode == "private":
        if not effective_mtls:
            errors.append(
                "mTLS is required for private network mode. "
                "Set mtls_required=true and provide client_ca_cert_path."
            )
        elif not config.client_ca_cert_path:
            errors.append("mTLS enabled but client_ca_cert_path not specified")
        elif not Path(config.client_ca_cert_path).exists():
            errors.append(f"Client CA certificate not found: {config.client_ca_cert_path}")

    return errors


def validate_network_mode(mode: str) -> List[str]:
    """Validate network mode value."""
    valid_modes = ("localhost", "private")
    if mode not in valid_modes:
        return [f"Invalid network_mode '{mode}'. Must be one of: {valid_modes}"]
    return []


def validate_port(port: int) -> List[str]:
    """Validate port number."""
    if not isinstance(port, int):
        return [f"Port must be integer, got {type(port).__name__}"]
    if port < 1 or port > 65535:
        return [f"Port {port} out of range. Must be 1-65535"]
    if port < 1024:
        return [f"Port {port} is privileged. Consider using port >= 1024"]
    return []


def validate_mcp_network_config(config: MCPNetworkConfig) -> List[str]:
    """
    Validate complete MCP network configuration.

    This is the main entry point for config validation.
    Call this before starting the MCP server.

    Args:
        config: MCP network configuration

    Returns:
        List of error messages, empty if configuration is valid
    """
    errors: List[str] = []

    # Validate network mode
    errors.extend(validate_network_mode(config.network_mode))

    # Validate bind host
    errors.extend(validate_bind_host(config.bind_host, config.network_mode))

    # Validate port
    errors.extend(validate_port(config.bind_port))

    # Validate TLS
    errors.extend(validate_tls_config(config))

    # Validate allowed subnets (only relevant for private mode)
    if config.network_mode == "private":
        if not config.allowed_subnets:
            errors.append(
                "Private network mode requires at least one allowed_subnet"
            )
        else:
            errors.extend(validate_allowed_subnets(config.allowed_subnets))

    if config.trust_client_cert_proxy_headers:
        if not config.trusted_proxy_subnets:
            errors.append(
                "trust_client_cert_proxy_headers=true requires at least one trusted_proxy_subnet"
            )
        else:
            errors.extend(validate_proxy_subnets(config.trusted_proxy_subnets))

    return errors


def is_client_allowed(client_ip: str, config: MCPNetworkConfig) -> bool:
    """
    Check if a client IP is allowed to connect.

    Args:
        client_ip: Client's IP address
        config: MCP network configuration

    Returns:
        True if client is allowed
    """
    if config.network_mode == "localhost":
        return is_loopback_address(client_ip)

    if config.network_mode == "private":
        try:
            client_addr = ipaddress.ip_address(client_ip)
        except ValueError:
            return False

        if client_addr.is_loopback:
            return True

        # Check against allowed subnets
        for subnet_str in config.allowed_subnets:
            try:
                subnet = ipaddress.ip_network(subnet_str, strict=False)
                if client_addr in subnet:
                    return True
            except ValueError:
                continue

        return False

    return False


def is_proxy_trusted(proxy_ip: str, config: MCPNetworkConfig) -> bool:
    """Return True when proxy header trust is enabled and source IP is trusted."""
    if not config.trust_client_cert_proxy_headers:
        return False

    try:
        proxy_addr = ipaddress.ip_address(proxy_ip)
    except ValueError:
        return False

    for subnet_str in config.trusted_proxy_subnets:
        try:
            subnet = ipaddress.ip_network(subnet_str, strict=False)
        except ValueError:
            continue
        if proxy_addr in subnet:
            return True

    return False


def get_default_config() -> MCPNetworkConfig:
    """Get secure default configuration (localhost only)."""
    return MCPNetworkConfig()


def get_private_network_template() -> Dict[str, Any]:
    """
    Get a template for private network configuration.

    This can be used to show users what a private network
    config should look like.
    """
    return {
        "_comment": "Private network MCP configuration template",
        "network_mode": "private",
        "bind_host": "10.8.0.2",
        "bind_port": 8765,
        "tls_enabled": True,
        "tls_cert_path": "/path/to/server.crt",
        "tls_key_path": "/path/to/server.key",
        "mtls_required": True,
        "client_ca_cert_path": "/path/to/client-ca.crt",
        "tls_verify_client": True,
        "trust_client_cert_proxy_headers": False,
        "trusted_proxy_subnets": [],
        "allowed_subnets": [
            "10.8.0.0/24",
            "192.168.50.0/24",
        ],
        "deny_public_ips": True,
    }
