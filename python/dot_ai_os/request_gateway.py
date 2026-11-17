"""Optional request-scoped MCP endpoint; it records requests and executes nothing.

Run separately from the read-only gateway, with its own exact resource URL,
OAuth audience and merlin:research:request scope. The host derives the principal
from SDK-authenticated context. Tool arguments cannot select their own identity.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl

from merlin.project_registry import MerlinRegistry
from .http_gateway import (GatewayConfig, GatewayConfigurationError,
                           HTTPIntrospector, IntrospectionTokenVerifier)
from .job_inbox import ProductionJobInbox

REQUEST_SCOPE = "merlin:research:request"


def create_request_server(inbox: ProductionJobInbox, *, config: GatewayConfig,
                          token_verifier: IntrospectionTokenVerifier) -> FastMCP:
    if (not isinstance(config, GatewayConfig) or
            not isinstance(token_verifier, IntrospectionTokenVerifier) or token_verifier.config != config):
        raise GatewayConfigurationError("matching host-owned resource and token-verifier policy required")
    origin = urlsplit(config.resource_url)
    server = FastMCP("Merlin Research Requests", instructions=(
        "Record bounded research requests for operator review. Accepted is not executed, "
        "approved, independently verified or promoted. Reuse a request's idempotency key "
        "only for identical retries."), host="127.0.0.1", port=config.port,
        stateless_http=True, json_response=True, max_request_body_size=32768,
        token_verifier=token_verifier,
        auth=AuthSettings(issuer_url=AnyHttpUrl(config.issuer_url),
            resource_server_url=AnyHttpUrl(config.resource_url), required_scopes=[REQUEST_SCOPE]),
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,
            allowed_hosts=[origin.netloc, f"127.0.0.1:{config.port}"],
            allowed_origins=[f"https://{origin.netloc}"]))

    def principal() -> str:
        token = get_access_token()
        if token is None or not token.subject or REQUEST_SCOPE not in token.scopes:
            raise PermissionError("authenticated request-scoped identity required")
        return token.subject

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                                             idempotentHint=True, openWorldHint=False))
    def submit_research_request(idempotency_key: str, namespace: str, objective: str,
                                source_commit: str, source_refs: list[dict[str, Any]],
                                acceptance_criteria: list[str], max_cost_usd: int = 0) -> dict[str, Any]:
        """Save a bounded request for operator review; does not dispatch any work."""
        return inbox.submit(principal=principal(), idempotency_key=idempotency_key,
            request={"namespace": namespace, "objective": objective, "source_commit": source_commit,
                     "source_refs": source_refs, "acceptance_criteria": acceptance_criteria,
                     "max_cost_usd": max_cost_usd})

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False,
                                             idempotentHint=True, openWorldHint=False))
    def research_request_status(request_id: str) -> dict[str, Any]:
        """Read one request owned by the authenticated principal."""
        return inbox.status(principal=principal(), request_id=request_id)

    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--namespaces", required=True, nargs="+")
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    if not (args.root / "merlin.sqlite3").is_file():
        parser.error("operator must provision the canonical project before request intake")
    try:
        config = GatewayConfig.from_mapping(json.loads(args.config.read_text("utf-8")))
        introspect = HTTPIntrospector(config,
            client_id=os.environ.get("MERLIN_INTROSPECTION_CLIENT_ID"),
            client_secret=os.environ.get("MERLIN_INTROSPECTION_CLIENT_SECRET"))
        inbox = ProductionJobInbox(MerlinRegistry(args.root), namespaces=tuple(args.namespaces))
        server = create_request_server(inbox, config=config,
            token_verifier=IntrospectionTokenVerifier(config, introspect))
    except (OSError, ValueError, KeyError):
        parser.error("request gateway refused startup; check host-owned identity and registry configuration")
    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
