"""Runtime TLS+mTLS end-to-end tests for network MCP."""

from __future__ import annotations

import asyncio
import json
import os
import socket
import ssl
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest

if sys.version_info < (3, 10):
    sys.exit(
        "ERROR: MCP tests require Python 3.10+.\n"
        "Current: Python {}.{}\n"
        "Fix: Update mem.config.json python_path to python3.11".format(
            sys.version_info.major, sys.version_info.minor
        )
    )

pytest.importorskip("mcp", reason="mcp package required for network MCP runtime tests")

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from tests.helpers.tls_certs import create_test_ca, issue_cert
from tools.graph_db import GraphDatabase
from tools.sql_db import SQLDatabase


SERVER_STARTUP_TIMEOUT = 15.0
SESSION_INIT_TIMEOUT = 15.0
TOOL_CALL_TIMEOUT = 15.0


def _free_port() -> int:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return sock.getsockname()[1]
    except PermissionError:
        pytest.skip("Local socket binding is not permitted in this environment")


def _canonical_payload_hash(payload: dict) -> str:
    import hashlib

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _tool_result_json(result) -> dict:
    assert getattr(result, "isError", False) is False
    assert getattr(result, "content", None), "Expected MCP tool content"
    first = result.content[0]
    return json.loads(first.text)


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def mtls_artifacts(tmp_path: Path) -> dict[str, dict[str, str]]:
    ca = create_test_ca(tmp_path)
    ca_cert = Path(ca["cert_path"])
    ca_key = Path(ca["key_path"])

    server = issue_cert(
        tmp_path,
        ca_cert,
        ca_key,
        common_name="127.0.0.1",
        cert_filename="server.crt",
        key_filename="server.key",
        is_client=False,
        san_ips=["127.0.0.1"],
        san_dns=["localhost"],
    )
    client = issue_cert(
        tmp_path,
        ca_cert,
        ca_key,
        common_name="valid-client",
        cert_filename="client-valid.crt",
        key_filename="client-valid.key",
        is_client=True,
    )

    other_ca = create_test_ca(tmp_path / "other-ca", common_name="other-ca")
    other_client = issue_cert(
        tmp_path / "other-ca",
        Path(other_ca["cert_path"]),
        Path(other_ca["key_path"]),
        common_name="invalid-client",
        cert_filename="client-invalid.crt",
        key_filename="client-invalid.key",
        is_client=True,
    )

    return {
        "ca": ca,
        "server": server,
        "client": client,
        "other_ca": other_ca,
        "other_client": other_client,
    }


def _write_network_config(
    config_path: Path,
    *,
    project_name: str,
    sql_path: Path,
    graph_path: Path,
    port: int,
    artifacts: dict[str, dict[str, str]],
    trust_proxy_headers: bool = False,
) -> None:
    config_path.write_text(
        json.dumps(
            {
                "project_name": project_name,
                "python_path": sys.executable,
                "database": {
                    "sql_path": str(sql_path),
                    "graph_path": str(graph_path),
                },
                "mcp": {
                    "network_mode": "private",
                    "bind_host": "127.0.0.1",
                    "bind_port": port,
                    "tls_enabled": True,
                    "tls_cert_path": artifacts["server"]["fullchain_path"],
                    "tls_key_path": artifacts["server"]["key_path"],
                    "mtls_required": True,
                    "client_ca_cert_path": artifacts["ca"]["cert_path"],
                    "tls_verify_client": True,
                    "trust_client_cert_proxy_headers": trust_proxy_headers,
                    "trusted_proxy_subnets": ["127.0.0.1/32"] if trust_proxy_headers else [],
                    "allowed_subnets": ["127.0.0.0/8", "10.8.0.0/24"],
                    "deny_public_ips": True,
                },
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def network_test_env(tmp_path: Path, repo_root: Path, mtls_artifacts: dict[str, dict[str, str]]) -> dict[str, str]:
    project_name = "test_mtls_runtime"
    sql_path = tmp_path / "network-test.db"
    graph_path = tmp_path / "network-test.graph"
    config_path = tmp_path / "mem.config.json"
    port = _free_port()

    GraphDatabase(str(graph_path))
    SQLDatabase(str(sql_path)).create_project(project_name, "Network mTLS runtime test project")
    _write_network_config(
        config_path,
        project_name=project_name,
        sql_path=sql_path,
        graph_path=graph_path,
        port=port,
        artifacts=mtls_artifacts,
        trust_proxy_headers=False,
    )

    return {
        "repo_root": str(repo_root),
        "config_path": str(config_path),
        "sql_path": str(sql_path),
        "graph_path": str(graph_path),
        "project_name": project_name,
        "port": str(port),
        "base_url": f"https://127.0.0.1:{port}",
        "mcp_url": f"https://127.0.0.1:{port}/mcp",
    }


@pytest.fixture
def proxy_header_env(tmp_path: Path, repo_root: Path, mtls_artifacts: dict[str, dict[str, str]]) -> dict[str, str]:
    project_name = "test_mtls_proxy_headers"
    sql_path = tmp_path / "network-test.db"
    graph_path = tmp_path / "network-test.graph"
    config_path = tmp_path / "mem.config.json"
    port = _free_port()

    GraphDatabase(str(graph_path))
    SQLDatabase(str(sql_path)).create_project(project_name, "Network proxy-header test project")
    _write_network_config(
        config_path,
        project_name=project_name,
        sql_path=sql_path,
        graph_path=graph_path,
        port=port,
        artifacts=mtls_artifacts,
        trust_proxy_headers=True,
    )

    return {
        "repo_root": str(repo_root),
        "config_path": str(config_path),
        "sql_path": str(sql_path),
        "graph_path": str(graph_path),
        "project_name": project_name,
        "port": str(port),
        "base_url": f"https://127.0.0.1:{port}",
        "mcp_url": f"https://127.0.0.1:{port}/mcp",
    }


@asynccontextmanager
async def run_network_server(env: dict[str, str]):
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "mcp_server.memory_mcp",
        "--http",
        cwd=env["repo_root"],
        env={**os.environ, "MEM_CONFIG": env["config_path"]},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        yield proc
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()


async def wait_for_server_ready(base_url: str, artifacts: dict[str, dict[str, str]]) -> None:
    import ssl
    deadline = asyncio.get_running_loop().time() + SERVER_STARTUP_TIMEOUT
    last_error: Exception | None = None

    # Create proper SSL context instead of deprecated string paths
    ssl_ctx = ssl.create_default_context(cafile=artifacts["ca"]["cert_path"])
    ssl_ctx.load_cert_chain(artifacts["client"]["cert_path"], artifacts["client"]["key_path"])

    while asyncio.get_running_loop().time() < deadline:
        try:
            async with httpx.AsyncClient(
                verify=ssl_ctx,
                timeout=2.0,
            ) as client:
                response = await client.get(f"{base_url}/mcp")
                if response.status_code in {200, 400, 404, 405, 406}:
                    return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        await asyncio.sleep(0.2)
    raise AssertionError(f"Server did not become ready: {last_error}")


@asynccontextmanager
async def open_streamable_http_session(
    mcp_url: str,
    artifacts: dict[str, dict[str, str]],
    *,
    headers: dict[str, str] | None = None,
):
    import ssl
    ssl_ctx = ssl.create_default_context(cafile=artifacts["ca"]["cert_path"])
    ssl_ctx.load_cert_chain(artifacts["client"]["cert_path"], artifacts["client"]["key_path"])

    async with httpx.AsyncClient(
        verify=ssl_ctx,
        timeout=httpx.Timeout(TOOL_CALL_TIMEOUT, read=TOOL_CALL_TIMEOUT),
        headers=headers,
    ) as client:
        async with streamable_http_client(mcp_url, http_client=client) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=SESSION_INIT_TIMEOUT)
                yield session


@pytest.mark.asyncio
class TestMCPNetworkMtlsRuntime:
    async def test_https_mtls_rejects_missing_client_cert(
        self, network_test_env: dict[str, str], mtls_artifacts: dict[str, dict[str, str]]
    ):
        async with run_network_server(network_test_env):
            await wait_for_server_ready(network_test_env["base_url"], mtls_artifacts)

            async with httpx.AsyncClient(
                verify=mtls_artifacts["ca"]["cert_path"],
                timeout=5.0,
            ) as client:
                with pytest.raises((httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError)):
                    await client.get(f"{network_test_env['base_url']}/mcp")

    async def test_https_mtls_rejects_untrusted_client_cert(
        self, network_test_env: dict[str, str], mtls_artifacts: dict[str, dict[str, str]]
    ):
        async with run_network_server(network_test_env):
            await wait_for_server_ready(network_test_env["base_url"], mtls_artifacts)

            async with httpx.AsyncClient(
                verify=mtls_artifacts["ca"]["cert_path"],
                cert=(mtls_artifacts["other_client"]["cert_path"], mtls_artifacts["other_client"]["key_path"]),
                timeout=5.0,
            ) as client:
                with pytest.raises((httpx.ConnectError, httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError)):
                    await client.get(f"{network_test_env['base_url']}/mcp")

    async def test_memory_context_succeeds_over_real_https_mtls(
        self, network_test_env: dict[str, str], mtls_artifacts: dict[str, dict[str, str]]
    ):
        async with run_network_server(network_test_env):
            await wait_for_server_ready(network_test_env["base_url"], mtls_artifacts)
            async with open_streamable_http_session(network_test_env["mcp_url"], mtls_artifacts) as session:
                result = await asyncio.wait_for(
                    session.call_tool("memory_context", {"last": 1}),
                    timeout=TOOL_CALL_TIMEOUT,
                )
                data = _tool_result_json(result)

        assert data["status"] == "ok"
        assert data["data"]["project"]["name"] == network_test_env["project_name"]

    async def test_forged_cert_headers_are_ignored_by_default(
        self, network_test_env: dict[str, str], mtls_artifacts: dict[str, dict[str, str]]
    ):
        payload = {
            "summary": {
                "session_id": "test-forged-headers",
                "timestamp": "2026-03-18T12:00:00Z",
                "intent": "Test forged header rejection",
                "work_attempted": ["Test"],
                "outcomes": [{"type": "success", "description": "Test"}],
                "fidelity": "summary",
            },
            "extraction": {"extractions": []},
            "options": {"skip_quality_check": True},
        }
        args = {"summary": payload["summary"], "extraction": payload["extraction"], "options": payload["options"], "payload_hash": _canonical_payload_hash(payload)}

        async with run_network_server(network_test_env):
            await wait_for_server_ready(network_test_env["base_url"], mtls_artifacts)
            async with open_streamable_http_session(
                network_test_env["mcp_url"],
                mtls_artifacts,
                headers={"x-client-cert-fingerprint": "sha256:forged"},
            ) as session:
                result = await asyncio.wait_for(
                    session.call_tool("memory_sync_submit", args),
                    timeout=TOOL_CALL_TIMEOUT,
                )
                data = _tool_result_json(result)

        assert data["status"] == "error"
        assert data["type"] == "validation"
        assert "client certificate metadata" in data["message"]
        sql_db = SQLDatabase(network_test_env["sql_path"])
        assert sql_db.list_sync_jobs(network_test_env["project_name"]) == []

    async def test_trusted_proxy_headers_are_accepted_when_enabled(
        self, proxy_header_env: dict[str, str], mtls_artifacts: dict[str, dict[str, str]]
    ):
        payload = {
            "summary": {
                "session_id": "test-trusted-proxy",
                "timestamp": "2026-03-18T12:00:00Z",
                "intent": "Test trusted proxy headers",
                "work_attempted": ["Test"],
                "outcomes": [{"type": "success", "description": "Test"}],
                "fidelity": "summary",
            },
            "extraction": {"extractions": []},
            "options": {"skip_quality_check": True},
        }
        args = {"summary": payload["summary"], "extraction": payload["extraction"], "options": payload["options"], "payload_hash": _canonical_payload_hash(payload)}

        proxy_headers = {
            "x-client-cert-fingerprint": mtls_artifacts["client"]["fingerprint"],
            "x-client-cert-subject": mtls_artifacts["client"]["subject"],
            "x-client-cert-serial": mtls_artifacts["client"]["serial"],
            "x-client-cert-issuer": mtls_artifacts["client"]["issuer"],
            "x-client-cert-not-before": mtls_artifacts["client"]["not_before"],
            "x-client-cert-not-after": mtls_artifacts["client"]["not_after"],
        }

        async with run_network_server(proxy_header_env):
            await wait_for_server_ready(proxy_header_env["base_url"], mtls_artifacts)
            async with open_streamable_http_session(
                proxy_header_env["mcp_url"],
                mtls_artifacts,
                headers=proxy_headers,
            ) as session:
                result = await asyncio.wait_for(
                    session.call_tool("memory_sync_submit", args),
                    timeout=TOOL_CALL_TIMEOUT,
                )
                data = _tool_result_json(result)

        assert data["status"] == "ok"
        job_id = data["data"]["job_id"]
        sql_db = SQLDatabase(proxy_header_env["sql_path"])
        job = sql_db.get_sync_job(job_id)
        assert job["client_cert_fingerprint"] == mtls_artifacts["client"]["fingerprint"]
