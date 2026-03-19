"""MCP server entry point for the LLM memory system."""

from __future__ import annotations

import sys

# Python 3.10+ required for mcp package
if sys.version_info < (3, 10):
    sys.exit(
        "ERROR: MCP server requires Python 3.10+.\n"
        "Current: Python {}.{}\n"
        "Fix: Update mem.config.json python_path to python3.11".format(
            sys.version_info.major, sys.version_info.minor
        )
    )

import argparse
import os
import ssl
from pathlib import Path
from typing import Any, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.mcp_network import is_client_allowed, is_proxy_trusted

from mcp_server.handlers.context import memory_context
from mcp_server.handlers.recall import memory_recall
from mcp_server.handlers.search import memory_search
from mcp_server.handlers.store import memory_store
from mcp_server.handlers.sync import (
    memory_sync_list,
    memory_sync_result,
    memory_sync_status,
    memory_sync_submit,
    memory_sync_submit_quality_review,
    handle_claim_authorship,
    handle_get_authorship_claims,
)
from mcp_server.handlers.tasks import memory_tasks
from mcp_server.handlers.common import load_runtime_state, set_current_network_cert_metadata


def _import_mcp() -> Tuple[Any, Any, Any]:
    try:
        from mcp.server.fastmcp import Context, FastMCP
        from mcp.server.session import ServerSession
    except ImportError as exc:
        raise RuntimeError(
            "The 'mcp' package is not installed. Install requirements.txt to run the MCP server."
        ) from exc
    return FastMCP, Context, ServerSession


def build_server():
    """Construct the FastMCP server with all tools registered."""
    FastMCP, _Context, _ServerSession = _import_mcp()
    mcp = FastMCP(
        name="Memory",
        instructions="LLM Memory System - query and store conversation memories.",
    )

    mcp.tool()(memory_recall)
    mcp.tool()(memory_search)
    mcp.tool()(memory_store)
    mcp.tool()(memory_tasks)
    mcp.tool()(memory_context)
    mcp.tool()(memory_sync_submit)
    mcp.tool()(memory_sync_status)
    mcp.tool()(memory_sync_result)
    mcp.tool()(memory_sync_list)
    mcp.tool()(memory_sync_submit_quality_review)
    mcp.tool()(handle_claim_authorship)
    mcp.tool()(handle_get_authorship_claims)
    return mcp


def run_stdio_server() -> None:
    server = build_server()
    server.run()


def run_http_server() -> None:
    state = load_runtime_state()
    if state.mcp_config.network_mode != "private":
        raise SystemExit("HTTP transport requires mcp.network_mode='private'")

    server = build_server()
    streamable_http_factory = getattr(server, "streamable_http_app", None)
    if streamable_http_factory is None:
        raise RuntimeError(
            "Installed mcp version does not expose FastMCP.streamable_http_app() for HTTP transport"
        )

    app = streamable_http_factory()

    try:
        import uvicorn
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.responses import JSONResponse
    except ImportError as exc:
        raise RuntimeError("uvicorn and starlette are required for HTTP transport") from exc

    mcp_config = state.mcp_config

    class SubnetValidationMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            client_ip = request.client.host if request.client else ""
            if not is_client_allowed(client_ip, mcp_config):
                return JSONResponse(
                    {"error": f"Client IP {client_ip} not in allowed subnets"},
                    status_code=403,
                )
            return await call_next(request)

    class ClientCertMetadataMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            metadata = None
            client_ip = request.client.host if request.client else ""

            # Current runtime fallback: only trust proxy-forwarded certificate metadata
            # when explicitly enabled and the source IP is a trusted proxy subnet.
            if is_proxy_trusted(client_ip, mcp_config):
                fingerprint = request.headers.get("x-client-cert-fingerprint")
                subject = request.headers.get("x-client-cert-subject")
                serial = request.headers.get("x-client-cert-serial")
                issuer = request.headers.get("x-client-cert-issuer")
                not_before = request.headers.get("x-client-cert-not-before")
                not_after = request.headers.get("x-client-cert-not-after")

                if any([fingerprint, subject, serial, issuer, not_before, not_after]):
                    metadata = {
                        "fingerprint": fingerprint,
                        "subject": subject,
                        "serial": serial,
                        "issuer": issuer,
                        "not_before": not_before,
                        "not_after": not_after,
                    }

            set_current_network_cert_metadata(metadata)
            try:
                return await call_next(request)
            finally:
                set_current_network_cert_metadata(None)

    app.add_middleware(SubnetValidationMiddleware)
    app.add_middleware(ClientCertMetadataMiddleware)

    # Mount enrollment API if configured
    try:
        enrollment_config = config.raw.get("enrollment", {})
        if enrollment_config.get("enabled", False):
            from mcp_server.enrollment_routes import enrollment_routes
            for route in enrollment_routes:
                app.routes.append(route)
    except Exception:
        pass  # Enrollment not available, skip silently

    uvicorn_kwargs = {
        "host": mcp_config.bind_host,
        "port": mcp_config.bind_port,
    }
    if mcp_config.tls_enabled:
        uvicorn_kwargs["ssl_keyfile"] = mcp_config.tls_key_path
        uvicorn_kwargs["ssl_certfile"] = mcp_config.tls_cert_path
        effective_mtls = mcp_config.mtls_required or mcp_config.tls_verify_client
        if effective_mtls:
            uvicorn_kwargs["ssl_ca_certs"] = mcp_config.client_ca_cert_path
            uvicorn_kwargs["ssl_cert_reqs"] = ssl.CERT_REQUIRED

    uvicorn.run(app, **uvicorn_kwargs)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the MCP memory server")
    parser.add_argument("--http", action="store_true", help="Run with HTTP transport")
    args = parser.parse_args(argv)

    try:
        if args.http:
            run_http_server()
        else:
            run_stdio_server()
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"[MCP CONFIG ERROR] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
