"""
Unit tests for tools/mcp_network.py

Tests RFC1918 validation, bind host validation, TLS config,
network mode validation, and client allowlist checking.
"""

import sys
import os

# Python 3.10+ required for mcp package
if sys.version_info < (3, 10):
    sys.exit(
        "ERROR: MCP tests require Python 3.10+.\n"
        "Current: Python {}.{}\n"
        "Fix: Update mem.config.json python_path to python3.11".format(
            sys.version_info.major, sys.version_info.minor
        )
    )

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tools.mcp_network import (
    MCPNetworkConfig,
    RFC1918_NETWORKS,
    BANNED_BIND_ADDRESSES,
    is_rfc1918_subnet,
    is_loopback_address,
    is_private_address,
    validate_allowed_subnets,
    validate_bind_host,
    validate_tls_config,
    validate_network_mode,
    validate_port,
    validate_mcp_network_config,
    is_client_allowed,
    is_proxy_trusted,
    get_default_config,
    get_private_network_template,
)


class TestRFC1918Validation:
    """Test RFC1918 private subnet validation."""

    def test_rfc1918_10_network(self):
        """10.0.0.0/8 subnets are valid."""
        assert is_rfc1918_subnet("10.0.0.0/8")
        assert is_rfc1918_subnet("10.8.0.0/24")
        assert is_rfc1918_subnet("10.255.255.0/24")

    def test_rfc1918_172_network(self):
        """172.16.0.0/12 subnets are valid."""
        assert is_rfc1918_subnet("172.16.0.0/12")
        assert is_rfc1918_subnet("172.16.0.0/24")
        assert is_rfc1918_subnet("172.31.255.0/24")
        # 172.32.x.x is NOT in 172.16.0.0/12
        assert not is_rfc1918_subnet("172.32.0.0/24")

    def test_rfc1918_192_network(self):
        """192.168.0.0/16 subnets are valid."""
        assert is_rfc1918_subnet("192.168.0.0/16")
        assert is_rfc1918_subnet("192.168.1.0/24")
        assert is_rfc1918_subnet("192.168.50.0/24")

    def test_public_networks_invalid(self):
        """Public IP ranges are rejected."""
        assert not is_rfc1918_subnet("8.8.8.0/24")
        assert not is_rfc1918_subnet("1.1.1.0/24")
        assert not is_rfc1918_subnet("142.250.0.0/16")

    def test_invalid_subnet_format(self):
        """Invalid CIDR notation returns False."""
        assert not is_rfc1918_subnet("not-a-subnet")
        # IP without prefix is treated as /32 by ipaddress library (valid)
        assert is_rfc1918_subnet("192.168.1.0")  # Treated as /32
        assert not is_rfc1918_subnet("192.168.1.0/33")  # Invalid prefix


class TestAddressHelpers:
    """Test address helper functions."""

    def test_is_loopback(self):
        """Loopback addresses detected correctly."""
        assert is_loopback_address("127.0.0.1")
        assert is_loopback_address("127.0.0.2")
        assert not is_loopback_address("192.168.1.1")
        assert not is_loopback_address("10.0.0.1")

    def test_is_private(self):
        """Private addresses detected correctly."""
        assert is_private_address("127.0.0.1")  # loopback
        assert is_private_address("10.0.0.1")
        assert is_private_address("172.16.0.1")
        assert is_private_address("192.168.1.1")
        assert not is_private_address("8.8.8.8")


class TestValidateAllowedSubnets:
    """Test allowed_subnets validation."""

    def test_valid_subnets(self):
        """Valid RFC1918 subnets pass."""
        errors = validate_allowed_subnets(["192.168.1.0/24", "10.8.0.0/24"])
        assert errors == []

    def test_public_subnet_rejected(self):
        """Public subnets are rejected."""
        errors = validate_allowed_subnets(["8.8.8.0/24"])
        assert len(errors) == 1
        assert "RFC1918" in errors[0]

    def test_mixed_subnets(self):
        """Mix of valid and invalid subnets reports only invalid."""
        errors = validate_allowed_subnets(["192.168.1.0/24", "8.8.8.0/24"])
        assert len(errors) == 1
        assert "8.8.8.0/24" in errors[0]

    def test_invalid_format_rejected(self):
        """Invalid CIDR format is rejected."""
        errors = validate_allowed_subnets(["not-a-subnet"])
        assert len(errors) == 1
        assert "Invalid subnet" in errors[0]


class TestValidateBindHost:
    """Test bind host validation."""

    def test_localhost_mode_loopback(self):
        """Localhost mode accepts loopback."""
        errors = validate_bind_host("127.0.0.1", "localhost")
        assert errors == []

    def test_localhost_mode_rejects_private(self):
        """Localhost mode rejects non-loopback."""
        errors = validate_bind_host("192.168.1.1", "localhost")
        assert len(errors) == 1
        assert "loopback" in errors[0].lower()

    def test_private_mode_accepts_private(self):
        """Private mode accepts private IPs."""
        errors = validate_bind_host("10.8.0.2", "private")
        assert errors == []
        errors = validate_bind_host("192.168.1.1", "private")
        assert errors == []

    def test_private_mode_rejects_public(self):
        """Private mode rejects public IPs."""
        errors = validate_bind_host("8.8.8.8", "private")
        assert len(errors) == 1

    def test_wildcard_banned(self):
        """0.0.0.0 is always rejected."""
        errors = validate_bind_host("0.0.0.0", "localhost")
        assert len(errors) == 1
        assert "banned" in errors[0].lower()

        errors = validate_bind_host("0.0.0.0", "private")
        assert len(errors) == 1

    def test_invalid_ip_rejected(self):
        """Invalid IP address format rejected."""
        errors = validate_bind_host("not-an-ip", "localhost")
        assert len(errors) == 1
        assert "not a valid IP" in errors[0]


class TestValidateNetworkMode:
    """Test network mode validation."""

    def test_valid_modes(self):
        """Valid modes pass."""
        assert validate_network_mode("localhost") == []
        assert validate_network_mode("private") == []

    def test_invalid_mode(self):
        """Invalid mode fails."""
        errors = validate_network_mode("public")
        assert len(errors) == 1
        assert "Invalid network_mode" in errors[0]


class TestValidatePort:
    """Test port validation."""

    def test_valid_ports(self):
        """Valid ports pass."""
        assert validate_port(8765) == []
        assert validate_port(8080) == []
        assert validate_port(65535) == []

    def test_privileged_port_warning(self):
        """Privileged ports get warning."""
        errors = validate_port(80)
        assert len(errors) == 1
        assert "privileged" in errors[0].lower()

    def test_invalid_port_range(self):
        """Out-of-range ports fail."""
        errors = validate_port(0)
        assert len(errors) == 1
        errors = validate_port(70000)
        assert len(errors) == 1


class TestValidateTLSConfig:
    """Test TLS configuration validation."""

    def test_localhost_no_tls_ok(self):
        """Localhost mode doesn't require TLS."""
        config = MCPNetworkConfig(network_mode="localhost", tls_enabled=False)
        errors = validate_tls_config(config)
        assert errors == []

    def test_private_requires_tls(self):
        """Private mode requires TLS."""
        config = MCPNetworkConfig(network_mode="private", tls_enabled=False)
        errors = validate_tls_config(config)
        assert len(errors) == 1
        assert "TLS is required" in errors[0]

    def test_tls_requires_cert_paths(self):
        """TLS enabled requires cert and key paths."""
        config = MCPNetworkConfig(tls_enabled=True)
        errors = validate_tls_config(config)
        assert len(errors) == 2  # Missing cert and key

    def test_private_requires_mtls_ca(self, tmp_path):
        """Private mode with TLS still requires mTLS and a client CA."""
        cert = tmp_path / "server.crt"
        key = tmp_path / "server.key"
        cert.write_text("cert")
        key.write_text("key")
        config = MCPNetworkConfig(
            network_mode="private",
            bind_host="10.8.0.2",
            tls_enabled=True,
            tls_cert_path=str(cert),
            tls_key_path=str(key),
            allowed_subnets=["10.8.0.0/24"],
        )
        errors = validate_mcp_network_config(config)
        assert any("mTLS is required" in e for e in errors)


class TestValidateMCPNetworkConfig:
    """Test full config validation."""

    def test_default_config_valid(self):
        """Default localhost config is valid."""
        config = get_default_config()
        errors = validate_mcp_network_config(config)
        assert errors == []

    def test_private_config_needs_subnets(self, tmp_path):
        """Private mode requires allowed_subnets."""
        cert = tmp_path / "server.crt"
        key = tmp_path / "server.key"
        ca = tmp_path / "client-ca.crt"
        cert.write_text("cert")
        key.write_text("key")
        ca.write_text("ca")
        config = MCPNetworkConfig(
            network_mode="private",
            bind_host="10.8.0.2",
            tls_enabled=True,
            tls_cert_path=str(cert),
            tls_key_path=str(key),
            mtls_required=True,
            client_ca_cert_path=str(ca),
            allowed_subnets=[],  # Empty!
        )
        errors = validate_mcp_network_config(config)
        assert any("allowed_subnet" in e for e in errors)

    def test_proxy_header_trust_requires_trusted_proxy_subnets(self):
        config = MCPNetworkConfig(
            trust_client_cert_proxy_headers=True,
        )
        errors = validate_mcp_network_config(config)
        assert any("trusted_proxy_subnet" in e for e in errors)

    def test_from_dict_roundtrip(self):
        """Config survives dict roundtrip."""
        original = MCPNetworkConfig(
            network_mode="private",
            bind_host="10.8.0.2",
            bind_port=9000,
            mtls_required=True,
            client_ca_cert_path="/path/to/client-ca.crt",
            trust_client_cert_proxy_headers=True,
            trusted_proxy_subnets=["127.0.0.1/32"],
            allowed_subnets=["10.8.0.0/24"],
        )
        restored = MCPNetworkConfig.from_dict(original.to_dict())
        assert restored.network_mode == original.network_mode
        assert restored.bind_host == original.bind_host
        assert restored.bind_port == original.bind_port
        assert restored.mtls_required == original.mtls_required
        assert restored.client_ca_cert_path == original.client_ca_cert_path
        assert restored.trust_client_cert_proxy_headers == original.trust_client_cert_proxy_headers
        assert restored.trusted_proxy_subnets == original.trusted_proxy_subnets
        assert restored.allowed_subnets == original.allowed_subnets


class TestClientAllowed:
    """Test client IP allowlist checking."""

    def test_localhost_allows_loopback(self):
        """Localhost mode allows 127.x.x.x."""
        config = MCPNetworkConfig(network_mode="localhost")
        assert is_client_allowed("127.0.0.1", config)
        assert not is_client_allowed("192.168.1.5", config)

    def test_private_allows_listed_subnets(self):
        """Private mode allows IPs in allowed_subnets."""
        config = MCPNetworkConfig(
            network_mode="private",
            allowed_subnets=["10.8.0.0/24", "192.168.50.0/24"],
        )
        assert is_client_allowed("127.0.0.1", config)
        assert is_client_allowed("10.8.0.5", config)
        assert is_client_allowed("192.168.50.100", config)
        assert not is_client_allowed("192.168.1.5", config)
        assert not is_client_allowed("8.8.8.8", config)

    def test_invalid_client_ip(self):
        """Invalid client IP returns False."""
        config = MCPNetworkConfig(network_mode="localhost")
        assert not is_client_allowed("not-an-ip", config)

    def test_proxy_trust_requires_enabled_flag_and_matching_subnet(self):
        config = MCPNetworkConfig(
            trust_client_cert_proxy_headers=True,
            trusted_proxy_subnets=["127.0.0.1/32", "10.8.0.0/24"],
        )
        assert is_proxy_trusted("127.0.0.1", config)
        assert is_proxy_trusted("10.8.0.8", config)
        assert not is_proxy_trusted("192.168.1.1", config)

        disabled = MCPNetworkConfig(
            trust_client_cert_proxy_headers=False,
            trusted_proxy_subnets=["127.0.0.1/32"],
        )
        assert not is_proxy_trusted("127.0.0.1", disabled)


class TestHelpers:
    """Test helper functions."""

    def test_get_default_config(self):
        """Default config has expected values."""
        config = get_default_config()
        assert config.network_mode == "localhost"
        assert config.bind_host == "127.0.0.1"
        assert config.tls_enabled is False

    def test_get_private_network_template(self):
        """Private network template has required fields."""
        template = get_private_network_template()
        assert template["network_mode"] == "private"
        assert template["tls_enabled"] is True
        assert template["mtls_required"] is True
        assert template["client_ca_cert_path"]
        assert template["trust_client_cert_proxy_headers"] is False
        assert template["trusted_proxy_subnets"] == []
        assert len(template["allowed_subnets"]) > 0
