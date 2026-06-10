"""
MCPClient — manages the lifecycle of the policies MCP server subprocess
and exposes its tools in Anthropic-compatible format.

Usage (in FastAPI lifespan):
    client = MCPClient(db_url=settings.policies_db_url)
    await client.start()
    app.state.mcp_client = client
    yield
    await client.stop()

All tool calls pass through the pre/post hook chain in hooks.py.
call_tool() now requires an AssessmentContext so hooks can write audit events.
"""
import asyncio
import copy
import os
import sys
import time
from pathlib import Path
from typing import Optional

from mcp import ClientSession
from mcp.client.stdio import stdio_client

try:
    from mcp.client.stdio import StdioServerParameters
except ImportError:
    from mcp import StdioServerParameters  # type: ignore[no-reattr]

from ..agents.base import AssessmentContext
from ..llm.base import ToolDefinition
from .hooks import HookChain, HookContext, build_default_hook_chain

# Directory that contains the 'app' package (i.e. server/)
_SERVER_ROOT = str(Path(__file__).resolve().parents[2])


class MCPClient:
    def __init__(
        self,
        db_url: str,
        python_executable: Optional[str] = None,
        hook_chain: Optional[HookChain] = None,
    ):
        self._db_url = db_url
        self._python = python_executable or sys.executable
        self._session: Optional[ClientSession] = None
        self._stdio_cm = None
        self._session_cm = None
        self._hook_chain = hook_chain or build_default_hook_chain()

    async def start(self, retries: int = 3) -> None:
        """Launch the MCP server subprocess and establish a session."""
        for attempt in range(retries):
            try:
                await self._connect()
                return
            except Exception as exc:
                if attempt == retries - 1:
                    raise RuntimeError(
                        f"MCPClient failed to connect after {retries} attempts: {exc}"
                    ) from exc
                await asyncio.sleep(1.0)

    async def stop(self) -> None:
        """Gracefully shut down the session and subprocess."""
        if self._session_cm is not None:
            try:
                await self._session_cm.__aexit__(None, None, None)
            except Exception:
                pass
        if self._stdio_cm is not None:
            try:
                await self._stdio_cm.__aexit__(None, None, None)
            except Exception:
                pass
        self._session = None
        self._stdio_cm = None
        self._session_cm = None

    async def list_tools_as_anthropic_format(self) -> list[ToolDefinition]:
        """Return all server tools in the format expected by AnthropicProvider."""
        self._ensure_connected()
        result = await self._session.list_tools()
        return [
            ToolDefinition(
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema,
            )
            for tool in result.tools
        ]

    async def call_tool(
        self, name: str, arguments: dict, ctx: AssessmentContext
    ) -> str:
        """
        Call a named MCP tool with full pre/post hook chain processing.

        Pre-hooks may normalize arguments or short-circuit with a cached or
        error result (e.g. invalid CSP, budget exceeded).
        Post-hooks normalize errors, detect empty results, limit payload size,
        enrich with metadata, and write audit events to ctx.audit_log.

        Returns a JSON string — either the tool's result or a structured hook
        response (error, warning, or truncated payload).
        """
        self._ensure_connected()

        hctx = HookContext(
            tool_name=name,
            args=copy.deepcopy(arguments),
            assessment_id=ctx.session_id,
        )

        # Run pre-hooks; a False return means a hook short-circuited the call.
        should_call = self._hook_chain.execute_pre(ctx, hctx)

        start = time.monotonic()
        if should_call:
            try:
                result = await self._session.call_tool(name, hctx.args)
                texts = [
                    c.text
                    for c in result.content
                    if hasattr(c, "text") and c.text
                ]
                hctx.result = "\n".join(texts)
            except Exception as exc:
                hctx.error = exc
        hctx.latency_ms = (time.monotonic() - start) * 1000

        # Post-hooks always run, even on short-circuit, for consistent audit coverage.
        self._hook_chain.execute_post(ctx, hctx)
        return hctx.result or ""

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _connect(self) -> None:
        params = StdioServerParameters(
            command=self._python,
            args=["-m", "app.mcp.server.server"],
            env={
                **os.environ,
                "PYTHONPATH": _SERVER_ROOT,
                "POLICIES_DB_URL": self._db_url,
            },
        )
        self._stdio_cm = stdio_client(params)
        read, write = await self._stdio_cm.__aenter__()
        self._session_cm = ClientSession(read, write)
        self._session = await self._session_cm.__aenter__()
        await self._session.initialize()

    def _ensure_connected(self) -> None:
        if self._session is None:
            raise RuntimeError("MCPClient is not connected. Call start() first.")
