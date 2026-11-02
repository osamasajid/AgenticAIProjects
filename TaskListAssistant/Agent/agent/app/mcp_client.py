"""MCP client: connect to the weather + booking MCP servers, discover their tools,
and adapt them into the ReAct loop's Tool interface.

This is what makes the agent an MCP CLIENT: it launches each server over stdio,
calls list_tools() to DISCOVER schemas (not hardcoded), and call_tool() to execute.

Task model (important): MCP's stdio sessions use anyio task groups that MUST be
entered and exited within the SAME task. So ONE long-lived coroutine (`_serve`)
owns each session's full lifecycle — it opens the contexts, then loops handling
call/close requests delivered over an asyncio.Queue, and only unwinds the contexts
when asked to stop. A background thread runs the loop; sync callers marshal via
run_coroutine_threadsafe. This avoids the "cancel scope in a different task" error.
"""
from __future__ import annotations

import asyncio
import sys
import threading
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .agent_tools import Tool

_SERVERS = {
    "weather": "mcp_servers.weather_server",
    "booking": "mcp_servers.booking_server",
}


class MCPToolProvider:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._requests: asyncio.Queue | None = None
        self._ready = threading.Event()
        self._tools: list[Tool] = []
        self._tool_server: dict[str, str] = {}
        # start the long-lived server coroutine
        asyncio.run_coroutine_threadsafe(self._serve(), self._loop)

    async def _serve(self) -> None:
        """Own the full lifecycle of all sessions in ONE task."""
        self._requests = asyncio.Queue()
        sessions: dict[str, ClientSession] = {}
        # AsyncExitStack-free: nest the async-with contexts by recursion via a helper
        async with _open_all(_SERVERS) as opened:
            for name, session in opened.items():
                sessions[name] = session
                listed = await session.list_tools()
                for t in listed.tools:
                    self._tool_server[t.name] = name
                    self._tools.append(Tool(
                        name=t.name,
                        description=t.description or t.name,
                        parameters=t.inputSchema or {"type": "object", "properties": {}},
                        fn=self._make_dispatch(t.name),
                    ))
            self._ready.set()
            # handle requests until told to stop
            while True:
                req = await self._requests.get()
                if req is None:
                    break
                tool_name, args, fut = req
                try:
                    result = await sessions[self._tool_server[tool_name]].call_tool(tool_name, args)
                    parts = [getattr(c, "text", None) for c in result.content]
                    text = "\n".join(p for p in parts if p) or "(no result)"
                    self._loop.call_soon_threadsafe(fut.set_result, text)
                except Exception as e:  # noqa: BLE001
                    self._loop.call_soon_threadsafe(fut.set_result, f"error: {e}")

    def load(self) -> list[Tool]:
        self._ready.wait(timeout=30)
        return self._tools

    def _make_dispatch(self, tool_name: str):
        def _call(**kwargs: Any) -> str:
            assert self._requests is not None
            fut: asyncio.Future = self._loop.create_future()
            self._loop.call_soon_threadsafe(self._requests.put_nowait, (tool_name, kwargs, fut))
            return asyncio.run_coroutine_threadsafe(_await(fut), self._loop).result(timeout=60)
        return _call

    def close(self) -> None:
        if self._requests is not None:
            self._loop.call_soon_threadsafe(self._requests.put_nowait, None)
        self._loop.call_soon_threadsafe(self._loop.stop)


async def _await(fut: asyncio.Future) -> str:
    return await fut


class _open_all:
    """Async context manager that opens all MCP stdio sessions and yields
    {name: session}, unwinding them in the same task on exit."""

    def __init__(self, servers: dict[str, str]) -> None:
        self._servers = servers
        self._cms: list[Any] = []

    async def __aenter__(self) -> dict[str, ClientSession]:
        opened: dict[str, ClientSession] = {}
        for name, module in self._servers.items():
            params = StdioServerParameters(command=sys.executable, args=["-m", module])
            stdio_cm = stdio_client(params)
            read, write = await stdio_cm.__aenter__()
            self._cms.append(stdio_cm)
            sess_cm = ClientSession(read, write)
            session = await sess_cm.__aenter__()
            self._cms.append(sess_cm)
            await session.initialize()
            opened[name] = session
        return opened

    async def __aexit__(self, *exc: Any) -> None:
        for cm in reversed(self._cms):
            try:
                await cm.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
