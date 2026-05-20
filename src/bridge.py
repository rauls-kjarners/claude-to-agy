"""Claude-to-Antigravity MCP Bridge.

A zero-dependency MCP server that delegates tasks to the Antigravity CLI (agy)
with configurable timeouts.
"""

import sys
import json
import asyncio
import os
import logging
from typing import IO, TypedDict

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

CONNECT_TIMEOUT = int(os.environ.get("AGY_CONNECT_TIMEOUT", "60"))
TOTAL_TIMEOUT = int(os.environ.get("AGY_TOTAL_TIMEOUT", "600"))

TOOL_SCHEMA = {
    "name": "delegate_to_agy",
    "description": "Delegate complex reasoning, large file analysis, or deep search to Antigravity CLI (agy).",
    "inputSchema": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The detailed prompt/instructions for Antigravity CLI.",
            },
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of absolute file paths to include as context.",
            },
        },
        "required": ["prompt"],
    },
}


class AgyResult(TypedDict, total=False):
    success: bool
    response: str
    error: str


def read_file(file_path: str) -> str:
    """Read a single file and return its content with a header, or an error marker."""
    if not os.path.exists(file_path):
        return f"--- File: {file_path} (File not found) ---\n"
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            content = handle.read()
        return f"--- File: {file_path} ---\n{content}\n"
    except Exception as error:
        return f"--- File: {file_path} (Error reading: {error}) ---\n"


def format_file_context(files: list[str]) -> str:
    """Read all files and join them into a single context string."""
    if not files:
        return ""
    return "\n".join(read_file(path) for path in files) + "\n"


async def spawn_agy(prompt: str) -> asyncio.subprocess.Process:
    """Launch the agy CLI as a subprocess."""
    return await asyncio.wait_for(
        asyncio.create_subprocess_exec(
            "agy", "-p", prompt,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        ),
        timeout=CONNECT_TIMEOUT,
    )


async def collect_output(process: asyncio.subprocess.Process) -> tuple[str, str]:
    """Wait for the process to finish and return decoded (stdout, stderr)."""
    stdout_bytes, stderr_bytes = await asyncio.wait_for(
        process.communicate(),
        timeout=TOTAL_TIMEOUT,
    )
    return (
        stdout_bytes.decode("utf-8", errors="replace"),
        stderr_bytes.decode("utf-8", errors="replace"),
    )


async def run_agy(prompt: str, files: list[str]) -> AgyResult:
    """Send a prompt to the Antigravity CLI and return the result."""
    full_prompt = format_file_context(files) + prompt

    try:
        process = await spawn_agy(full_prompt)
    except asyncio.TimeoutError:
        return AgyResult(
            success=False, error=f"Connect timeout ({CONNECT_TIMEOUT}s) exceeded."
        )
    except Exception as error:
        return AgyResult(success=False, error=f"Failed to start agy: {error}")

    try:
        stdout, stderr = await collect_output(process)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return AgyResult(
            success=False, error=f"Total timeout ({TOTAL_TIMEOUT}s) exceeded."
        )

    if process.returncode != 0:
        return AgyResult(
            success=False,
            error=f"Process exited with code {process.returncode}. Stderr: {stderr}",
        )

    return AgyResult(success=True, response=stdout)


async def delegate(prompt: str, files: list[str]) -> AgyResult:
    """Run the prompt against Antigravity CLI. Thin wrapper for potential future extensibility."""
    return await run_agy(prompt, files)


class MCPServer:
    """Minimal MCP JSON-RPC server over stdio."""

    def __init__(self, reader: asyncio.StreamReader, writer: IO[str]):
        self.reader = reader
        self.writer = writer

    def send_json(self, payload: dict) -> None:
        """Serialize and write a JSON-RPC message."""
        self.writer.write(json.dumps(payload) + "\n")
        self.writer.flush()

    def send_result(self, request_id: int | str | None, result: dict) -> None:
        """Send a successful JSON-RPC response."""
        self.send_json({"jsonrpc": "2.0", "id": request_id, "result": result})

    def send_error(self, request_id: int | str | None, code: int, message: str) -> None:
        """Send a JSON-RPC error response."""
        self.send_json(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": code, "message": message},
            }
        )

    async def run(self) -> None:
        """Read JSON-RPC requests from stdin and dispatch them."""
        while True:
            try:
                line = await self.reader.readline()
                if not line:
                    break

                text = line.decode("utf-8").strip()
                if not text:
                    continue

                request = json.loads(text)
                await self._handle_request(request)

            except json.JSONDecodeError as error:
                logger.warning("Invalid JSON received: %s", error)
            except Exception as error:
                logger.error("Error handling request: %s", error)

    async def _handle_request(self, request: dict) -> None:
        """Route a JSON-RPC request to the appropriate handler."""
        method = request.get("method")
        request_id = request.get("id")

        if method == "ping":
            self.send_result(request_id, {})

        elif method == "initialize":
            self.on_initialize(request_id)

        elif method == "notifications/initialized":
            pass  # No response needed for notifications

        elif method == "tools/list":
            self.on_tools_list(request_id)

        elif method == "tools/call":
            await self.on_tools_call(request_id, request.get("params", {}))

        elif request_id is not None:
            self.send_error(request_id, -32601, f"Unknown method: {method}")

    def on_initialize(self, request_id: int | str | None) -> None:
        """Respond to the MCP initialize handshake."""
        self.send_result(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "claude-to-agy", "version": "2.0.0"},
            },
        )

    def on_tools_list(self, request_id: int | str | None) -> None:
        """Return the list of available tools."""
        self.send_result(request_id, {"tools": [TOOL_SCHEMA]})

    async def on_tools_call(self, request_id: int | str | None, params: dict) -> None:
        """Execute a tool and return the result."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name != "delegate_to_agy":
            self.send_error(request_id, -32601, f"Unknown tool: {tool_name}")
            return

        prompt = arguments.get("prompt", "")
        files = arguments.get("files", [])

        result = await delegate(prompt, files)

        self.send_result(
            request_id,
            {
                "content": [{"type": "text", "text": json.dumps(result)}],
            },
        )


async def main() -> None:
    """Set up stdio transport and start the MCP server."""
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    server = MCPServer(reader, sys.stdout)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
