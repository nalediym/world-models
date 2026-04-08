"""LWM MCP server — stdio JSON-RPC transport.

Implements the Model Context Protocol (MCP) over stdio so any AI assistant
can query LWM's behavioral data.  Tries the ``mcp`` package first; falls
back to a minimal JSON-RPC/stdio implementation if that package is absent.
"""

from __future__ import annotations

import json
import sys

from life_world_model.mcp_server.handlers import (
    handle_get_experiments,
    handle_get_goals,
    handle_get_patterns,
    handle_get_score_history,
    handle_get_sources,
    handle_get_suggestions,
    handle_get_timeline,
    handle_get_today_score,
    handle_simulate,
)

# ---------------------------------------------------------------------------
# Tool definitions (shared between MCP-native and JSON-RPC fallback)
# ---------------------------------------------------------------------------

TOOL_DEFS: list[dict] = [
    {
        "name": "get_today_score",
        "description": (
            "Returns today's day score, grade, per-goal breakdown, trade-offs, "
            "and Pareto optimality check."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_patterns",
        "description": (
            "Returns discovered behavioral patterns from the last N days of "
            "activity data. Includes routines, correlations, circadian rhythm, "
            "context-switching costs, and time sinks."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to analyze (default: 30).",
                    "default": 30,
                },
            },
        },
    },
    {
        "name": "get_suggestions",
        "description": (
            "Returns ranked actionable suggestions derived from discovered "
            "patterns. Each suggestion includes impact prediction and score delta."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days of data to consider (default: 30).",
                    "default": 30,
                },
            },
        },
    },
    {
        "name": "get_timeline",
        "description": (
            "Returns the 15-minute bucketed activity timeline for a specific "
            "date, showing what you were doing in each time slot."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format (default: today).",
                },
            },
        },
    },
    {
        "name": "get_score_history",
        "description": (
            "Returns daily scores and grades for the last N days, showing "
            "how the day score has changed over time."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days of history (default: 30).",
                    "default": 30,
                },
            },
        },
    },
    {
        "name": "get_experiments",
        "description": (
            "Returns active, completed, and cancelled habit-change experiments "
            "with their results."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "simulate",
        "description": (
            "Runs a what-if simulation for a behavioral change. Accepts "
            "natural language like 'code from 8-10am', 'stop browsing after 9pm', "
            "'limit browsing to 1hr', 'add 30min walk at 12pm'. Returns baseline "
            "vs simulated score."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "intervention": {
                    "type": "string",
                    "description": (
                        "Natural language intervention, e.g. "
                        "'code from 8-10am before email'"
                    ),
                },
                "baseline_date": {
                    "type": "string",
                    "description": (
                        "Date to use as baseline in YYYY-MM-DD format "
                        "(default: best of last 7 days)."
                    ),
                },
            },
            "required": ["intervention"],
        },
    },
    {
        "name": "get_sources",
        "description": (
            "Returns which data collectors are installed and available "
            "(Chrome, Calendar, shell history, git, etc.)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_goals",
        "description": (
            "Returns the user's configured goals with names, descriptions, "
            "metrics, and weights."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


# Map tool names to handler functions
_HANDLERS: dict[str, object] = {
    "get_today_score": lambda args: handle_get_today_score(),
    "get_patterns": lambda args: handle_get_patterns(days=args.get("days", 30)),
    "get_suggestions": lambda args: handle_get_suggestions(days=args.get("days", 30)),
    "get_timeline": lambda args: handle_get_timeline(target_date=args.get("date")),
    "get_score_history": lambda args: handle_get_score_history(
        days=args.get("days", 30)
    ),
    "get_experiments": lambda args: handle_get_experiments(),
    "simulate": lambda args: handle_simulate(
        intervention=args.get("intervention", ""),
        baseline_date=args.get("baseline_date"),
    ),
    "get_sources": lambda args: handle_get_sources(),
    "get_goals": lambda args: handle_get_goals(),
}


# ---------------------------------------------------------------------------
# Attempt MCP-native server
# ---------------------------------------------------------------------------


def _try_mcp_server() -> bool:
    """Try to start a native MCP server using the ``mcp`` package.

    Returns True if the server was started (blocks), False if the package
    is not available.
    """
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
    except ImportError:
        return False

    server = FastMCP("life-world-model")

    # Register each tool dynamically
    @server.tool()
    def get_today_score() -> str:
        """Returns today's day score, grade, and breakdown."""
        return json.dumps(handle_get_today_score())

    @server.tool()
    def get_patterns(days: int = 30) -> str:
        """Returns discovered behavioral patterns from the last N days."""
        return json.dumps(handle_get_patterns(days=days))

    @server.tool()
    def get_suggestions(days: int = 30) -> str:
        """Returns ranked actionable suggestions with impact predictions."""
        return json.dumps(handle_get_suggestions(days=days))

    @server.tool()
    def get_timeline(date: str | None = None) -> str:
        """Returns the 15-min bucketed timeline for a specific date."""
        return json.dumps(handle_get_timeline(target_date=date))

    @server.tool()
    def get_score_history(days: int = 30) -> str:
        """Returns daily scores for the last N days."""
        return json.dumps(handle_get_score_history(days=days))

    @server.tool()
    def get_experiments() -> str:
        """Returns active and recent experiments with results."""
        return json.dumps(handle_get_experiments())

    @server.tool()
    def simulate(intervention: str, baseline_date: str | None = None) -> str:
        """Runs a what-if simulation and returns score delta."""
        return json.dumps(
            handle_simulate(intervention=intervention, baseline_date=baseline_date)
        )

    @server.tool()
    def get_sources() -> str:
        """Returns which data collectors are available and working."""
        return json.dumps(handle_get_sources())

    @server.tool()
    def get_goals() -> str:
        """Returns the user's configured goals and weights."""
        return json.dumps(handle_get_goals())

    server.run()
    return True


# ---------------------------------------------------------------------------
# Fallback: minimal JSON-RPC over stdio
# ---------------------------------------------------------------------------


def _jsonrpc_response(req_id: int | str | None, result: object) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_error(
    req_id: int | str | None, code: int, message: str
) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _handle_jsonrpc(request: dict) -> dict:
    """Dispatch a single JSON-RPC request."""
    req_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {})

    # MCP protocol methods
    if method == "initialize":
        return _jsonrpc_response(req_id, {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "life-world-model", "version": "0.1.0"},
            "capabilities": {"tools": {}},
        })

    if method == "notifications/initialized":
        # Client ack — no response needed, but send one to be safe
        return _jsonrpc_response(req_id, {})

    if method == "tools/list":
        return _jsonrpc_response(req_id, {"tools": TOOL_DEFS})

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        handler = _HANDLERS.get(tool_name)
        if handler is None:
            return _jsonrpc_error(req_id, -32601, f"Unknown tool: {tool_name}")
        try:
            result = handler(tool_args)
            return _jsonrpc_response(req_id, {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}],
            })
        except Exception as exc:
            return _jsonrpc_error(req_id, -32000, str(exc))

    return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")


def _run_stdio_server() -> None:
    """Run a minimal MCP-compatible JSON-RPC server over stdio."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            response = _jsonrpc_error(None, -32700, "Parse error")
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
            continue

        # Skip notification-style messages (no id)
        if "id" not in request:
            continue

        response = _handle_jsonrpc(request)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_server() -> None:
    """Start the LWM MCP server.

    Tries the native ``mcp`` package first.  If unavailable, falls back to a
    lightweight JSON-RPC/stdio implementation.
    """
    if not _try_mcp_server():
        _run_stdio_server()
