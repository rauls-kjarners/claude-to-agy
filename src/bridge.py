"""Claude-to-Gemini MCP Bridge.

A zero-dependency MCP server that delegates tasks to the Gemini CLI
with automatic model fallback and configurable timeouts.
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

CONNECT_TIMEOUT = int(os.environ.get("GEMINI_CONNECT_TIMEOUT", "60"))
TOTAL_TIMEOUT = int(os.environ.get("GEMINI_TOTAL_TIMEOUT", "600"))
PRIMARY_MODEL = os.environ.get("GEMINI_PRIMARY_MODEL", "gemini-3.1-pro-preview")
FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3-flash-preview")

MODEL_ALIASES = {"flash": FALLBACK_MODEL, "pro": PRIMARY_MODEL}

TOOL_SCHEMA = {
    "name": "delegate_to_gemini",
    "description": "Delegate complex reasoning, large file analysis, or deep search to Gemini.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The detailed prompt/instructions for Gemini.",
            },
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of absolute file paths to include as context.",
            },
            "model": {
                "type": "string",
                "enum": ["flash", "pro"],
                "description": (
                    "Optional. 'flash' for fast simple tasks, "
                    "'pro' for complex reasoning. Defaults to pro."
                ),
            },
        },
        "required": ["prompt"],
    },
}


class GeminiResult(TypedDict, total=False):
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


async def spawn_gemini(prompt: str, model: str) -> asyncio.subprocess.Process:
    """Launch the gemini CLI as a subprocess."""
    return await asyncio.wait_for(
        asyncio.create_subprocess_exec(
            "gemini",
            "-p",
            prompt,
            "-m",
            model,
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


async def run_gemini(prompt: str, files: list[str], model: str) -> GeminiResult:
    """Send a prompt to the Gemini CLI and return the result."""
    full_prompt = format_file_context(files) + prompt

    try:
        process = await spawn_gemini(full_prompt, model)
    except asyncio.TimeoutError:
        return GeminiResult(
            success=False, error=f"Connect timeout ({CONNECT_TIMEOUT}s) exceeded."
        )
    except Exception as error:
        return GeminiResult(success=False, error=f"Failed to start gemini: {error}")

    try:
        stdout, stderr = await collect_output(process)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return GeminiResult(
            success=False, error=f"Total timeout ({TOTAL_TIMEOUT}s) exceeded."
        )

    if process.returncode != 0:
        return GeminiResult(
            success=False,
            error=f"Process exited with code {process.returncode}. Stderr: {stderr}",
        )

    return GeminiResult(success=True, response=stdout)


def resolve_model(requested: str) -> str:
    """Return the requested model if valid, otherwise the primary model."""
    if requested in (PRIMARY_MODEL, FALLBACK_MODEL):
        return requested
    return PRIMARY_MODEL


async def delegate(prompt: str, files: list[str], model: str = "") -> GeminiResult:
    """Run the prompt against Gemini, falling back to the secondary model on failure."""
    target = resolve_model(model)
    result = await run_gemini(prompt, files, target)

    if result["success"]:
        return result

    if FALLBACK_MODEL and target != FALLBACK_MODEL:
        logger.warning(
            "Model (%s) failed: %s. Retrying with fallback (%s).",
            target,
            result["error"],
            FALLBACK_MODEL,
        )
        return await run_gemini(prompt, files, FALLBACK_MODEL)

    logger.error("Model (%s) failed and no further fallback available.", target)
    return result


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
                "serverInfo": {"name": "claude-to-gemini", "version": "1.1.0"},
            },
        )

    def on_tools_list(self, request_id: int | str | None) -> None:
        """Return the list of available tools."""
        self.send_result(request_id, {"tools": [TOOL_SCHEMA]})

    async def on_tools_call(self, request_id: int | str | None, params: dict) -> None:
        """Execute a tool and return the result."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name != "delegate_to_gemini":
            self.send_error(request_id, -32601, f"Unknown tool: {tool_name}")
            return

        prompt = arguments.get("prompt", "")
        files = arguments.get("files", [])
        model_alias = arguments.get("model", "")
        model = MODEL_ALIASES.get(model_alias, "")

        result = await delegate(prompt, files, model)

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
